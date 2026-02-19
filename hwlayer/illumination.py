import os
import board
from threading import Thread, Event, Timer
from abc import ABC, abstractmethod
from settings import settings
from hwlayer.logging import logging

log = logging.getLogger('Illumination')
log.setLevel('DEBUG')
log.info("Starting illumination")

# load settings
config_file = os.environ.get('SETTLEPLATE_CONFIG','default')
if not settings.init(config_file, log):
	exit(1)

# LED strip configuration:
NEOPIXEL_ORDER = "GRB"

class Illumination(ABC):
	def __init__(self):
		self._logger = None
		self._timer = Timer(0, self.stop)

	@abstractmethod
	def set_status(self, value):
		pass

	@abstractmethod
	def set_top(self, value):
		pass

	@abstractmethod
	def set_ring(self, value):
		pass

	@abstractmethod
	def stop(self):
		pass

	def run(self):
		pass

	def clear(self):
		self.set_status(False)
		self.set_top(False)
		self.set_ring(False)

class IlluminationGPIO(Illumination):

	def __init__(self, pin_top, pin_ring):
		super().__init__()

		# Create gpiozero LED objects with appropriate configuration.
		from gpiozero import LED
		self._led_top = LED(pin_top)
		self._led_ring = LED(pin_ring)
		log.info(f"Top  : {pin_top}")
		log.info(f"Ring : {pin_ring}")

	def set_status(self, value):
		pass

	def set_top(self, value):
		if value:
			self._led_top.on()
		else:
			self._led_top.off()

	def set_ring(self, value):
		if value:
			self._led_ring.on()
		else:
			self._led_ring.off()
	
	def stop(self):
		self.clear()

class IlluminationNeopixel(Illumination):

	def __init__(self, leds_status, leds_top, leds_ring):
		super().__init__()
		# setup threading for animations
		self._thread = None
		self._thread_stop = Event()
		self._busy = False

		# Create NeoPixel object with appropriate configuration.
		from neopixel_spi import NeoPixel_SPI
		self.n_leds = leds_status+leds_ring+leds_top
		self.strip = NeoPixel_SPI(board.SPI(), self.n_leds, auto_write=False, bpp=len(NEOPIXEL_ORDER), pixel_order=NEOPIXEL_ORDER)
		self.segment = {
			'status': range(0,leds_status),
			'ring':   range(leds_status,leds_ring+leds_status),
			'top':	 range(leds_ring+leds_status,leds_status+leds_ring+leds_top)
		}
		log.info(f"Ring :{self.segment['ring'][0]}-{self.segment['ring'][-1]}")
		log.info(f"Top  :{self.segment['top'][0]}-{self.segment['top'][-1]}")

	def set_status(self, value):
		if value:
			color = [0,255,0]
		else:
			color = [0,0,0]

		for i in self.segment['status']:
			self.strip[i] = color

	def set_top(self, value):
		if value:
			color = settings['illumination']['neopixel']['color_top']
		else:
			color = [0,0,0]

		for i in self.segment['top']:
			self.strip[i] = color

	def set_ring(self, value):
		if value:
			color = settings['illumination']['neopixel']['color_ring']
		else:
			color = [0,0,0]
		
		for i in self.segment['ring']:
				self.strip[i] = color

	def clear():
		self.stop()
		super(self).clear()
		self.strip.show()

	# Define functions which animate LEDs in various ways.
	def wheel(pos):
		"""Generate rainbow colors across 0-255 positions."""
		pos = pos%255
		if pos < 85:
			color = [pos * 3, 255 - pos * 3, 0]
		elif pos < 170:
			pos -= 85
			color = [255 - pos * 3, 0, pos * 3]
		else:
			pos -= 170
			color = [0, pos * 3, 255 - pos * 3]
		return [int(round(x,0)) for x in color]
		

	def color_wipe(self, color, wait_ms=100):
		self.stop()
		self._thread = Thread(target=self._color_wipe, args=[color,wait_ms])
		self._thread.start()

	def _color_wipe(self, color, wait_ms):
		"""Wipe color across display a pixel at a time."""
		self.strip.fill([[0,0,0]])
		for i in self.segment['ring']:
			if self._thread_stop.is_set():
				return
			self.strip[i] = color
			self.strip.show()
			time.sleep(wait_ms / 1000.0)

	def rainbow(self, wait_ms=10, duration=0):
		self.stop()
		self._thread = Thread(target=self._rainbow, args=[wait_ms])
		self._thread.start()

	def _rainbow(self, wait_ms):
		"""Draw rainbow that uniformly distributes itself across all pixels."""
		self.strip.fill((0,0,0))
		while True:
			for j in range(256):
				for i in self.segment['ring']:
					self.strip[i] = self.wheel((i / LED_RING * 256) + j)
				self.strip.show()
				time.sleep(wait_ms / 1000.0)
				if self._thread_stop.is_set():
					print('stopping rainbow')
					return

	def run(self, duration:int = 0):
		self.strip.show()
		if duration > 0:
			self._timer.interval = duration
			self._timer.start()

	def stop(self):
		if self._timer.is_alive:
			self._timer.cancel()
		if type(self._thread) is Thread:
			if self._thread.is_alive():
				self._thread_stop.set()
				self._thread.join()
			self._thread = None
			self._thread_stop.clear()

illumination = None
illumination_type = settings['illumination']['type']
if illumination_type == "gpio":
	try:
		log.info("Starting GPIO leds")
		pin_top = settings['illumination']['gpio']['pin_top']
		pin_ring = settings['illumination']['gpio']['pin_ring']
		illumination = IlluminationGPIO(pin_top, pin_ring)
	except Exception as e:
		log.error(e)
		exit()
elif illumination_type == "neopixel":
	try:
		log.info("Starting NEOPIXEL leds")
		leds_status = settings['illumination']['neopixel']['n_status']
		leds_ring = settings['illumination']['neopixel']['n_ring']
		leds_top = settings['illumination']['neopixel']['n_top']
		illumination = IlluminationNeopixel(leds_status, leds_top, leds_ring)
	except Exception as e:
		log.error(e)
		exit()

if __name__ == "__main__":
	import time

	if illumination_type == "gpio":
		log.info('Testing top')
		illumination.set_top(True)
		time.sleep(5)
		illumination.set_top(False)
		log.info('Testing ring')
		illumination.set_ring(True)
		time.sleep(5)
		illumination.set_ring(False)

	elif illumination_type == "neopixel":
		#led.ring([255,196,92])
		log.info('Testing rainbow')
		illumination.rainbow();
		time.sleep(10)
		log.info('Testing wipe')
		illumination.color_wipe([92,0,12])
		time.sleep(5)
		log.info('Testing ring')
		illumination.ring([92,92,92])
		time.sleep(5)
		log.info('Testing top')
		illumination.top([92,92,92])
		time.sleep(5)
		log.info('Testing clear')
		illumination.clear()
