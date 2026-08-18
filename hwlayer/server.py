# server.py is the hardware daemon running on the Raspberry Pi,
   # it controls the camera and LED illumination, and 
   # exposes a ZeroMQ REP endpoint (ie the "server" side of the REQ-REP pattern) that serves requests from the client.py REQ client
   # returns captured images.
import os
import zmq
import time
import threading # needed for the status thread + camera lock
from hwlayer.logging import logging
from hwlayer.illumination import illumination
from hwlayer.picamera import PiHQCamera2
from settings import settings
import cv2
import json

log = logging.getLogger('Server')
log.setLevel('DEBUG')
log.info("Starting server")

# declare variables
camera = None
socket = None
last_jpeg = None #store last captured JPEG bytes on the Pi

# one shared context for all sockets
_context = zmq.Context.instance()

# lock protecting all direct hardware access to `camera`.
# Both the main loop (capture) and the new status thread (ready) touch
# the camera object, and camera/libcamera libraries are generally not
# thread-safe. Scope is kept tight around actual hardware calls only —
# around illumination/sleep/JPEG encoding — so a "ready" check can
# never be stuck waiting for a full capture cycle, only for the brief
# moment the lock is actually held.
camera_lock = threading.Lock()
def _resolve_bind_address():
   """ 
      Determine whether to bind IPC (local Pi) or TCP (Kubernetes remote access). 
      For TCP it binds to all network interfaces (ie the * tcp://*:{port}, 
      meaning it will accept connections on the given port regardless of which 
      interface they arrive on (eg wired ethernet, WiFi or 127.0.0.1)
   """
   transport = os.environ.get("HARDWARE_TRANSPORT", "ipc")
   if transport == "ipc":
      return "ipc:///tmp/settleplate_hw"
   if transport == "tcp":
      port = os.environ.get("HARDWARE_PORT", "3117")
      return f"tcp://*:{port}"
   raise ValueError(f"Unknown HARDWARE_TRANSPORT={transport}")

# second, independent bind address for lightweight status
# commands (ready/storage), so they never queue behind a slow capture
# on the main socket. Separate port for tcp; separate ipc path for local.
def _resolve_status_bind_address():
   transport = os.environ.get("HARDWARE_TRANSPORT", "ipc")
   if transport == "ipc":
      return "ipc:///tmp/settleplate_hw_status"
   if transport == "tcp":
      port = os.environ.get("HARDWARE_STATUS_PORT", "3118")
      return f"tcp://*:{port}"
   raise ValueError(f"Unknown HARDWARE_TRANSPORT={transport}")

def start_socket():
   global socket
   context = _context
   log.info('Creating ZeroMQ socket')

   # dynamic bind address
   bind_addr = _resolve_bind_address()
   log.info(f"Binding hardware server to address: {bind_addr}")

   try:
      socket = context.socket(zmq.REP)
      socket.bind(bind_addr)
   except Exception as e:
      log.error('Could not create ZeroMQ socket')

# dedicated thread + socket + loop for status commands.
# Runs independently of the main loop, so `ready`/`storage` are answered
# immediately even while a capture is in progress on the main socket.
def start_status_socket():
   def _run():
      context = _context
      status_socket = context.socket(zmq.REP)
      bind_addr = _resolve_status_bind_address()
      log.info(f"Binding status server to address: {bind_addr}")
      try:
         status_socket.bind(bind_addr)
         log.info(f"Status socket successfully bound: {bind_addr}")
      except Exception as e:
         log.error(f'Could not create status ZeroMQ socket: {e}')
         return

      while True:
         try:
            request = status_socket.recv_json()
            cmd = request.get('CMD')

            if cmd == 'ready':
               # lock held only for the actual hardware check, not for
               # anything slow — this is the whole point of this thread
               with camera_lock:
                  if camera is not None:
                     camera.ready_cam()
                     ready = camera.isReady()
                  else:
                     ready = False
               status_socket.send_json({'msg': ready})
               continue

            if cmd == 'storage':
               try:
                  ok = os.path.exists(settings['general']['savepath']) and \
                       os.access(settings['general']['savepath'], os.W_OK)
                  status_socket.send_json({'msg': ok})
               except Exception as e:
                  status_socket.send_json({'msg': False, 'error': str(e)})
               continue

            # unknown command on this socket
            status_socket.send_json({'msg': False, 'error': f"Unknown status CMD: {cmd}"})

         except Exception as e:
            log.error(f"Status socket error: {e}")
            try:
               status_socket.send_json({'msg': False, 'error': str(e)})
            except Exception:
               pass  # socket may be in a bad state; loop will retry on next recv

   t = threading.Thread(target=_run, daemon=True, name="status-socket")
   t.start()
   log.info("Status socket thread started")


def start_camera():
   global camera
   log.info('Setting up camera')
   camera = PiHQCamera2()

def start_illumination():
   illumination.clear()
   illumination.set_status(True)
   illumination.run()

# helper function that uses sorting to allow comparison of dicts in a deterministic way 
def _norm(obj):
    return json.dumps(obj, sort_keys=True)

def main():
   # time to wait for request before doing housekeeping
   timeout = 5000 # ms

   # This dict will be used in comparison after it has been normalised by _norm()
   prev_request = {}

   while True:
      if socket.poll(timeout):
         request = socket.recv_json()
         request.setdefault('cam_resolution', None)
         cmd = request.pop('CMD')

         if cmd == 'ready':
            # kept here too for ipc/local-dev callers still using
            # the main socket directly, but now also lock-protected for
            # consistency with the status thread.
            with camera_lock:
               camera.ready_cam()
               response = {'msg': camera.isReady()}
            socket.send_json(response)
            continue

         if cmd == 'status':
            illumination.set_status(request['led_status'])
            illumination.run()
            response = {
               'msg' : 'ok'
            }
            socket.send_json(response)
            continue

         #for key, value in settings['camera'].items():
         #    request.setdefault(key, value)

         # Let Pi report that savepath exists, is writable and is mounted (if its an external disk)
         if cmd == 'storage':
            try:
               ok = os.path.exists(settings['general']['savepath']) and os.access(settings['general']['savepath'], os.W_OK)
               socket.send_json({'msg': ok})
            except Exception as e:
               socket.send_json({'msg': False, 'error': str(e)})
            continue

         # if capturing, use the lock for different operations that
         # we dont want to run at the same time from 2 threads
         # but also keep the lock as short as possible so it does not 
         # become a bottleneck when other services need it
         if cmd == 'capture':
            # time capture
            t0 = time.time_ns()

            # check if settings changed
            if _norm(request) != _norm(prev_request):
               # lock while applying camera config changes
               with camera_lock:
                  camera.set_exposure(request['cam_exposure'])
                  camera.set_whitebalance(request['cam_wb'][0],request['cam_wb'][1])
                  camera.set_crop(request['cam_crop'])
                  camera.set_resolution(request['cam_resolution'])
                  camera.set_flip(request['cam_hflip'], request['cam_vflip'])
                  camera.set_rotation(request['cam_rotation'])
               #store normalized version to ensure stable comparisons
               prev_request = json.loads(_norm(request))

            try:
               log.debug(request)
               # lock when running illumination commands
               with camera_lock:
                  illumination.set_top(request['led_top'])
                  illumination.set_ring(request['led_ring'])
                  illumination.run()
                  time.sleep(request['led_wait']) # let lighting settle before capture

               # A Separate, short lock just for capturing. Kept minimal so
               # the camera is only "locked" for the instant we actually read it.
               with camera_lock:
                  image = camera.capture_array()

               #capture JPEG bytes for saving later
               #encode JPEG from array instead of calling capture_file()
               _, jpeg_bytes = cv2.imencode(".jpg", image)

               illumination.clear()
               response = {
                  'msg'  : 'ok',
                  'dtype' : str(image.dtype),
                  'shape' : image.shape
               }
               socket.send_json(response, flags=zmq.SNDMORE)
               socket.send(image, copy=True)

               t1 = time.time_ns()
               log.debug(f"Response time {(t1-t0)*1e-6:.0f} ms")
                  
            except Exception as e:
               logging.error(e)
               response = {
                  'msg'   : 'error',
                  'error' : f"Could not perform {cmd} command"
               }
               socket.send_json(response)
               log.error(response['error'])
            continue

         # support both new K8s client (multipart frames) AND old Pi client (JSON-embedded JPEG)
         # New K8s client sends JPEG in TWO frames:
         #   Frame 1: JSON {CMD:'save', filename:'...'}
         #   Frame 2: raw JPEG bytes
         # Old Pi client sends JPEG inside the JSON
         # We try to read Frame 2 first; if not present, fall back to JSON field.

         if cmd == 'save':
            filename = request['filename']
            savepath = os.path.join(settings['general']['savepath'], filename)

            # verify the resolved path is still inside savepath,even though the k8s side now sanitizes filenames.
            # gaurds against a future caller (or old Pi-local client) skipping sanitization.
            real_savepath = os.path.realpath(settings['general']['savepath'])
            real_target = os.path.realpath(savepath)
            if not real_target.startswith(real_savepath + os.sep):
               socket.send_json({'msg': 'error', 'error': 'Invalid filename'})
               continue

            try:
               # request from k8s: Check whether client sent the JPEG in the second ZMQ message frame
               try:
                  jpeg_bytes = socket.recv(copy=True)
               except Exception:
                  jpeg_bytes = None

               # Fallback(Assume request is old client that runs on the Pi): JSON-embedded bytes sent by old client
               if jpeg_bytes is None:
                  jpeg_bytes = request.get('jpeg_bytes')

               if jpeg_bytes is None:
                  socket.send_json({'msg': 'error', 'error': 'No processed JPEG provided'})
                  continue

               with open(savepath, 'wb') as f:
                     f.write(jpeg_bytes)

               socket.send_json({'msg': 'ok'})
            except Exception as e:
               socket.send_json({'msg': 'error', 'error': str(e)})
            continue

      # camera.update() also touches hardware state, lock it too
      with camera_lock:
         camera.update()

if __name__ == '__main__':
   # load settings
   start_illumination()
   start_camera()
   start_socket() #moved to below camera(): If PiHQCamera2() initialization is asynchronous or not complete when the status thread starts, ready could return false.
   start_status_socket()  # start the new independent status thread

   try:
      main()
   except KeyboardInterrupt:
      log.info("Shutting down")