import numpy as np
from abc import ABC, abstractmethod

class BaseSettings(ABC):
	@property
	def flip(self): return self.flip
	@flip.setter
	def flip(self, horizontal:bool, vertical:bool):
		self.flip = vertical
		if horizontal:
			self.flip = -self.flip

	@abstractmethod
	def load(self,json: dict) -> None:
		pass
	@abstractmethod
	def save(self) -> dict:
		pass

class BaseCamera(ABC):
	def __init__(self):
		pass

	@abstractmethod
	def capture_array(self) -> np.array:
		pass
	@abstractmethod
	def capture_jpeg(self) -> bytes:
		pass
	@abstractmethod
	def update(self) -> None:
		pass
	@abstractmethod
	def isReady(self) -> bool:
		pass
	@abstractmethod
	def set_exposure(self, exp: int) -> None:
		pass
	def set_gain(self, gain: float) -> None:
		pass
	@abstractmethod
	def set_whitebalance(self, wb_red: float, wb_blue:float) -> None:
		pass
	@abstractmethod
	def set_flip(self, horizontal:bool, vertical:bool) -> None:
		pass
	@abstractmethod
	def set_rotation(self, dir:str) -> None:
		pass