import logging
import time
from io import BytesIO
from picamera2 import Picamera2
#from libcamera import Transform
from hwlayer.base import BaseCamera

class PiHQCamera2(BaseCamera):
	def __init__(self):
		self.timeout = 180 # seconds
		self._logger = logging.getLogger('PiHQCamera')
		self._logger.setLevel('DEBUG')

		self._logger.info('Initializing camera')
		self._cam = Picamera2()
		self._config = self._cam.create_still_configuration(
			main={'format':'RGB888'},
			lores={'size':(512,512),'format':'YUV420'},
			buffer_count=2
		)
		self._config['controls'].update({
			'AnalogueGain': 1.0
		})
		self._cam.configure(self._config)
		self._last_active = 0
		self._config_changed = True
		self._control_changed = True
		self.rotation = 0
		super().__init__()
		
	def ready_cam(self):
		# check if configuration changed
		if self._config_changed:
			self._logger.debug('Config changed')
			self._stop_cam()
			self._cam.configure(self._config)
			self._config_changed = False
		if self._control_changed:
			self._logger.debug('Control changed')
			self._cam.set_controls(self._config['controls'])
			self._control_changed = False
		if not self._cam.started:
			self._cam.start()
		self._last_active = time.time()

	def _stop_cam(self):
		# turn off camera
		if self._cam.started:
			self._cam.stop()
	
	def update(self):
		if self._cam.started and time.time() - self._last_active > self.timeout:
			self._logger.info('Stopping camera after inactivty')
			self._stop_cam()
	
	def isReady(self):
		return self._cam.started
	
	def capture_array(self):
		self.ready_cam()
		self._logger.info(f"Capturing image {self._config['main']['size']}")
		image = self._cam.capture_array()
		if self.rotation:
			pass
			#image = np.rot90(np.copy(image,order='C'), k=self.rotation, axes=(0,1))
		return image

	def capture_jpeg(self):
		self.ready_cam()
		self._logger.info(f"Capturing image {self._config['main']['size']}")
		stream = BytesIO()
		self._cam.capture_file(stream, format='jpeg')        
		return stream.getbuffer().tobytes()
			
	def set_exposure(self, exp):
		if exp is None:
			return
		self._config['controls']['ExposureTime'] = exp
		self._logger.debug(f"Setting exposure to {exp}")
		self._control_changed = True

	def set_whitebalance(self, wb_red, wb_blue):
		if wb_red is None or wb_blue is None:
			return
		self._config['controls']['ColourGains'] = [wb_red, wb_blue]
		self._logger.debug(f"Setting white balance to {wb_red:0.2f} 1.00 {wb_blue:0.2f}")
		self._control_changed = True
	
	def set_flip(self, horizontal=False, vertical=False):
		self._logger.debug(f"Setting flip to {horizontal} {vertical}")
		#self._config['transform'] = Transform(hflip=horizontal, vflip=vertical)
		self._config_changed = True
	
	def set_rotation(self, dir:str):
		if dir == "cw":
			self.rotation = 1
		elif dir == "ccw":
			self.rotation = -1
		else:
			self.rotation = 0

	def set_crop(self, crop_rect):
		if crop_rect is None:
			# reset crop area to default
			crop_rect = self._cam.camera_properties['PixelArrayActiveAreas'][0] 
		x_offset, y_offset, width, height = crop_rect
		
		self._config['controls']['ScalerCrop'] = (x_offset, y_offset, width, height)
		self._config['main']['size'] = (width, height)
		self._cam.align_configuration(self._config)
		self._config_changed = True
		
	def set_resolution(self, resolution):
		if resolution is None:
			return
		self._config['main']['size'] = self._cam.sensor_resolution
		self._cam.align_configuration(self._config)
		self._config_changed = True
