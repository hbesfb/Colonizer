# server.py is the hardware daemon running on the Raspberry Pi,
   # it controls the camera and LED illumination, and 
   # exposes a ZeroMQ REP endpoint (ie the "server" side of the REQ-REP pattern) that serves requests from the client.py REQ client
   # returns captured images.
import os
import zmq
import time
from hwlayer.logging import logging
from hwlayer.illumination import illumination
from hwlayer.picamera import PiHQCamera2
from settings import settings

log = logging.getLogger('Server')
log.setLevel('DEBUG')
log.info("Starting server")

# declare variables
camera = None
socket = None

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

def start_socket():
   global socket
   context = zmq.Context()
   log.info('Creating ZeroMQ socket')

   # dynamic bind address
   bind_addr = _resolve_bind_address()
   log.info(f"Binding hardware server to address: {bind_addr}")

   try:
      socket = context.socket(zmq.REP)
      socket.bind(bind_addr)
   except Exception as e:
      log.error('Could not create ZeroMQ socket')

def start_camera():
   global camera
   log.info('Setting up camera')
   camera = PiHQCamera2()

def start_illumination():
   illumination.clear()
   illumination.set_status(True)
   illumination.run()

def main():
   # time to wait for request before doing housekeeping
   timeout = 5000 # ms
   prev_request = None

   while True:
      if socket.poll(timeout):
         request = socket.recv_json()
         request.setdefault('cam_resolution', None)
         cmd = request.pop('CMD')

         if cmd == 'ready':
            camera.ready_cam()
            response = {
               'msg' : camera.isReady()
            }
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

         # if capturing array
         if cmd == 'capture':
            # time capture
            t0 = time.time_ns()

            # check if settings changed
            if request != prev_request:
               camera.set_exposure(request['cam_exposure'])
               camera.set_whitebalance(request['cam_wb'][0],request['cam_wb'][1])
               camera.set_crop(request['cam_crop'])
               camera.set_resolution(request['cam_resolution'])
               camera.set_flip(request['cam_hflip'], request['cam_vflip'])
               camera.set_rotation(request['cam_rotation'])
               prev_request = request

            try:
               log.debug(request)
               illumination.set_top(request['led_top'])
               illumination.set_ring(request['led_ring'])
               illumination.run()
               time.sleep(request['led_wait'])
               image = camera.capture_array()
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

         # support both new K8s client (multipart frames) AND old Pi client (JSON-embedded JPEG)
         # New K8s client sends JPEG in TWO frames:
         #   Frame 1: JSON {CMD:'save', filename:'...'}
         #   Frame 2: raw JPEG bytes
         # Old Pi client sends JPEG inside the JSON
         # We try to read Frame 2 first; if not present, fall back to JSON field.

         if cmd == 'save':
            filename = request['filename']
            savepath = os.path.join(settings['general']['savepath'], filename)

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