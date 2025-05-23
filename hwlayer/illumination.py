import time
from threading import Thread, Event, Timer
from enum import Enum
import board
from neopixel_spi import NeoPixel_SPI
#from neopixel import NeoPixel

# LED strip configuration:
LED_ORDER = "GRB"
LED_STATUS = 1
LED_RING = 24
LED_TOP = 45
LED_OFF = [0,0,0]

class Illumination():
	def __init__(self):

		self._logger = None
		# Create NeoPixel object with appropriate configuration.
		self.n_leds = LED_STATUS+LED_RING+LED_TOP
		
		self.strip = NeoPixel_SPI(board.SPI(), self.n_leds, auto_write=False, bpp=len(LED_ORDER), pixel_order=LED_ORDER)
		#self.strip = NeoPixel(board.D10, self.n_leds, auto_write=False, bpp=len(LED_ORDER), pixel_order=LED_ORDER)
		self.segment = {
			'status': range(0,LED_STATUS),
			'ring':   range(LED_STATUS,LED_RING+LED_STATUS),
			'top':	 range(LED_RING+LED_STATUS,LED_STATUS+LED_RING+LED_TOP)
		}
		self._logger.info(f"Ring :{self.segment['ring'][0]}-{self.segment['ring'][-1]}")
		self._logger.info(f"Top  :{self.segment['top'][0]}-{self.segment['top'][-1]}")

		self._thread = None
		self._thread_stop = Event()
		self._busy = False
		self._timer = Timer(0, self.stop)

		# ensure all leds are off
		self._logger.info("Clearing LEDs")
		self.clear()

	def set_status(self, color):
		for i in self.segment['status']:
			self.strip[i] = color

	def set_top(self, color):
		for i in self.segment['top']:
			self.strip[i] = color

	def set_ring(self, color):
		# if color is array same length as number of leds, assign seperate color per led
		if len(color) == len(self.segment['ring']):
			for j,i in enumerate(self.segment['ring']):
				self.strip[i] = color[j]
		# else set all leds to same color
		elif len(color) == 3:
			for i in self.segment['ring']:
				self.strip[i] = color

	def run(self, duration:int = 0):
		self.strip.show()
		if duration > 0:
			self._timer.interval = duration
			self._timer.start()

	# Define functions which animate LEDs in various ways.
	@staticmethod
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
		self.strip.fill(LED_OFF)
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

	def stop(self):
		if self._timer.is_alive:
			self._timer.cancel()
		if type(self._thread) is Thread:
			if self._thread.is_alive():
				self._thread_stop.set()
				self._thread.join()
			self._thread = None
			self._thread_stop.clear()
	
	def clear(self):
		self.stop()
		self.set_top(LED_OFF)
		self.set_ring(LED_OFF)
		self.strip.show()
		
illumination = Illumination()

if __name__ == "__main__":
	led = Illumination()
	#led.ring([255,196,92])
	print('test rainbow')
	led.rainbow();
	time.sleep(10)
	print('test wipe')
	led.color_wipe([92,0,12])
	time.sleep(5)
	print('test ring')
	led.ring([92,92,92])
	time.sleep(5)
	print('test top')
	led.top([92,92,92])
	time.sleep(5)
	print('test clear')
	led.clear()
	