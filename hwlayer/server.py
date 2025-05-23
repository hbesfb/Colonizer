import sys
import logging
import logging.handlers
import zmq
import time
#from settings import settings
from hwlayer.illumination import illumination

# setup logging
log_root = logging.getLogger()
log_formatter = logging.Formatter("%(asctime)s | %(name)12s | %(levelname)8s : %(message)s")
#log_filehandler = logging.handlers.TimedRotatingFileHandler('log/ColonizerHW.log', when='midnight', backupCount=7)
#log_filehandler.setFormatter(log_formatter)
#log_filehandler.setLevel('DEBUG')
log_stdhandler = logging.StreamHandler(sys.stdout)
log_stdhandler.setFormatter(log_formatter)
log_stdhandler.setLevel('DEBUG')
#log_root.addHandler(log_filehandler)
log_root.addHandler(log_stdhandler)

log = logging.getLogger('Server')
log.setLevel('DEBUG')
log.info("Starting server")

# declare variables
camera = None
socket = None

def start_socket():
   global socket
   port = 3117
   context = zmq.Context()
   log.info('Creating ZeroMQ socket')
   try:
      socket = context.socket(zmq.REP)
      socket.bind("ipc:///tmp/settleplate_hw")
      #socket.bind(f"tcp://*:{port}")
   except Exception as e:
      log.error('Could not create ZeroMQ socket')

from hwlayer.picamera import PiHQCamera2
def start_camera():
   global camera
   log.info('Setting up camera')
   camera = PiHQCamera2()

def start_illumination():
   illumination.clear()
   illumination.set_status([255,0,0])
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
                  'msg:'  : 'ok',
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
               
      camera.update()

if __name__ == '__main__':
   # load settings
   start_illumination()
   start_socket()
   start_camera()
   try:
      main()
   except KeyboardInterrupt:
      log.info("Shutting down")