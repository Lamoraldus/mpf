# from mpf.platforms.interfaces.light_platform_interface import LightPlatformInterface
from mpf.core.platform import LightConfig, LightConfigColors
from mpf.core.platform_batch_light_system import PlatformBatchLight, PlatformBatchLightSystem

from mpf.platforms.gepard.gepard_led import GepardLED
from mpf.platforms.gepard.gepard_utils import GepardUtils

class GepardLEDChannel(PlatformBatchLight):
	"""Interface for a light in hardware platforms."""

	__slots__ = ["config", "index", "led", "number", "_brightness"]

	def __init__(self, led:GepardLED, number:str, config:LightConfig, light_system:PlatformBatchLightSystem) -> None:
		super().__init__(config.name, light_system)
		"""initialize light."""
		self.led    = led
		self.config = config
		self.number = number
		self.index  = GepardUtils.indexFromDashedKey(self.number, 3)
		self._brightness = 0.0
		self.led.channels[self.index] = self
		#self.led.string.board.platform.info_log(f"GepardLEDChannel({config})");

	@property
	def brightness(self):
		return self._brightness

	@brightness.setter
	def brightness(self, value):
		self._brightness = value
		self.led.needsUpdate = True

	def get_max_fade_ms(self):
		"""Return max fade ms."""
		return 254

	def get_board_name(self):
		"""Return the name of the board of this light."""
		return led.string.board.name()

	def __lt__(self, other):
		return self.number < other.number

	def is_successor_of(self, other):
		"""Return true if the other light has the previous pixel_num and is on the same chain and addr."""
		isSuccessor = (self.number[:-2] == other.number[:-2]) and (int(self.number[-1:]) == int(other.number[-1:])+1)
		# print("is_successor_of", self.number[:-2], other.number[:-2], int(self.number[-1:]), int(other.number[-1:])+1, isSuccessor)
		return isSuccessor
		
