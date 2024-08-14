from typing import Any


from mpf.platforms.gepard.gepard_led import GepardLED
from mpf.platforms.gepard.gepard_utils import GepardUtils

class GepardLEDString:

	"""Manages a string of LEDs on one port."""

	__slots__ = ["board", "port", "ledDict"]

	def __init__(self, board, port, platform):
		"""initialize."""
		super().__init__()
		self.board  = board
		self.port   = port
		self.ledDict = {}

	def ledForDashedKey(self, aKey, createIfAbsent) -> GepardLED:
		aLedIndex = GepardUtils.indexFromDashedKey(aKey, 2)
		aLED = self.ledDict.get(aLedIndex)
		if aLED is None:
			aLED = GepardLED(self, aLedIndex)
			self.ledDict[aLedIndex] = aLED
			# self.board.platform.info_log(f"added LED for key {aKey}")
		return aLED

	def updateLEDs(self):
		needsUpdate = False
		aCommand = f"L= {self.port:02X}"
		for aLED in self.ledDict.values():
			if aLED.needsUpdate:
				aLED.needsUpdate = False
				aCommand += aLED.updateString()
				needsUpdate = True
		if needsUpdate:
			# self.board.platform.info_log(f"updateLEDs {aCommand}");
			aCommand += "\n"
			self.board.sendStr(aCommand)
