
class GepardLED:
	__slots__ = ["channels", "index", "string", "needsUpdate"]

	def __init__(self, string, index) -> None:
		super().__init__()
		"""initialize light."""
		self.string = string
		self.index  =  index # type:str
		self.needsUpdate = False
		self.channels = [None, None, None, None] # rgbw
		#self.string.board.platform.info_log(f"GepardLED({number})");

	# returns a string identifying the led’s index and it’s color
	def updateString(self) -> str:
		aCommandPart = f" {self.index:02X}"
		for aChannel in self.channels:
			if aChannel is not None:
				aCommandPart += f" {int(aChannel.brightness * 0xFF):02X}"
		return aCommandPart

	# sends a L= command to this led’s board, if led needs an update
	def updateLED(self):
		if self.needsUpdate:
			self.needsUpdate = False
			self.string.board.sendStr(f"L= {self.port:02X} {self.updateString()}\n")

