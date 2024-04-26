"""OPP serial communicator."""
import asyncio

from mpf.platforms.base_serial_communicator import BaseSerialCommunicator, HEX_FORMAT
from mpf.platforms.gepard.gepard_led_string import GepardLEDString
from mpf.platforms.gepard.gepard_utils import GepardUtils

MYPY = False
if MYPY:	# pragma: no cover
	from mpf.platforms.gepard.gepard import GepardHardwarePlatform   # pylint: disable-msg=cyclic-import,unused-import


class GepardBoard(BaseSerialCommunicator):

	"""Manages a Serial connection to a Gepard board."""

	__slots__ = ["idIsValid", "id", "receiveIndex", "receiveBuff", "devicesAreValid", "switchesAreValid", "portDevices"]

	# pylint: disable=too-many-arguments
	def __init__(self, platform: "GepardHardwarePlatform", tty, baud) -> None:
		"""initialize Serial Connection to Gepard Hardware."""

		super().__init__(platform, tty, baud)
		self.idIsValid		= False
		self.devicesAreValid  = False
		self.switchesAreValid = False

		self.platform = platform
		self.receiveIndex = 0
		self.receiveBuff = bytearray(1024)
		self.portDevices	  = [None] * 32 # type: Array[GepardPort]

	@classmethod
	def boardKeyFromDashedKey(self, aKey):
		aBoardIndex = GepardUtils.indexFromDashedKey(aKey, 0)
		return f"{aBoardIndex:02X}"

	def deviceAtPortOfDashedKey(self, aKey):
		try:
			anIndex = GepardUtils.indexFromDashedKey(aKey, 1)
			return self.portDevices[anIndex]
		except IndexError:
			raise IndexError(f"port index {anIndex} of key {aKey} out of range")

	def name(self):
		return f"Gepard board {self.id}"

	async def readAndProcess(self):
		resp = await self.read(128)
		if resp is not None:
			self._parse_msg(resp)

	def sendStr(self, aString):
		self.send(aString.encode('ascii'))


	async def _identify_connection(self):
		"""Identify which processor this serial connection is talking to."""

		self.send(b"\n\n")   # flush any older command aswers
		self.send(b"XI\n")   # get board id
		while not self.idIsValid:
			await self.readAndProcess()

		self.send(b"X?\n")   # get board setup
		while not self.devicesAreValid:
			await self.readAndProcess()

		self.send(b"S@\n")   # get switch states
		while not self.switchesAreValid:
			await self.readAndProcess()

		self.send(b"X@ 1\n") # set led to slow green blinking


	def _parse_msg(self, msg):
		
		anIndex = 0
		aLength = len(msg)
		while anIndex < aLength:
			inputByte = msg[anIndex] & 0xFF;
			anIndex += 1
			# is this the start of a new message?
			if self.receiveIndex == 0:
				# Look for an ascii major command or a length for a binary command
				if inputByte != 10 and inputByte != 13:
					# save major command byte
					# ascii message will end with \n, it has no known length
					self.receiveBuff[self.receiveIndex] = inputByte
					self.receiveIndex += 1
				else:
					# this is an empty line
					# look for the next message
					# printf("OK: received empty line\n");
					self.receiveIndex = 0
			else:
				# We are in the middle of receiving a message
				# Is message complete?
				if inputByte == 10 or inputByte == 13:
					self.processAnswer();
					self.receiveIndex = 0
				else:
					self.receiveBuff[self.receiveIndex] = inputByte
					self.receiveIndex += 1

	def injectDevice(self, aConfigName, aPort, anIndex=None):
		aDeviceDict = self.machine.config.get(aConfigName)
		if aDeviceDict is None:
			aDeviceDict = {}
			self.machine.config[aConfigName] = aDeviceDict

		if anIndex is None:
			aDeviceID = f"{self.id}-{aPort:02X}"
		else:
			aDeviceID = f"{self.id}-{aPort:02X}-{anIndex:02X}"

		# find out if this device number is already taken
		isDeviceDefined = False
		for aValueDict in aDeviceDict.values():
			if aValueDict["number"] == aDeviceID:
				isDeviceDefined = True
				return aValueDict
				break

		if not isDeviceDefined:
			aValueDict = {"number": aDeviceID}
			aDeviceDict[f"gpd_{aConfigName}_{aDeviceID}"] = aValueDict
			self.platform.info_log(f"injectDevice gpd_{aConfigName}_{aDeviceID}");
			return aValueDict


	def injectLEDStrip(self, aPort):

		if self.portDevices[aPort] is None:
			self.portDevices[aPort] = GepardLEDString(self, aPort, self.platform)

			aConfigName = "lights"
			for anIndex in range(0, 255):
				aValueDict = self.injectDevice(aConfigName, aPort, anIndex)
				aValueDict["type"] = "rgb"


#	def injectLEDStrip(self, aPort):
#		aConfigName = "light_stripes"
#		aDeviceDict = self.machine.config.get(aConfigName)
#		if aDeviceDict is None:
#			aDeviceDict = {}
#			self.machine.config[aConfigName] = aDeviceDict
#
#		aStripID = f"gpd_strip_{self.id}-{aPort:02X}"
#
#		isDeviceDefined = False
#		if aStripID in aDeviceDict:
#			isDeviceDefined = True
#		if not isDeviceDefined:
#			aDeviceDict[aStripID] = {"number_start": 0, "count": 256,
#				"number_template": f"{self.id}-{aPort:02X}-{{:02X}}",
#				"light_template": { "tags": aStripID, "type": "rgb" }}
#			self.portDevices[aPort] = GepardLEDString(self, aPort, self.platform)


	def processAnswer(self):

		if self.receiveIndex > 2:
			error = ""
			ack = True
			aCommandString = self.receiveBuff[0 : self.receiveIndex].decode('ASCII') # make it a string to make ascii matches work
			aMajorCommand  = aCommandString[0]
			aMinorCommand  = aCommandString[1]
			aCommandSignal = aCommandString[2]; # the ':'
			aDataString	= aCommandString[4 : self.receiveIndex] # remove the space after colon as well
			aDataArray	 = aDataString.split()

			match aMajorCommand:
				case 'A':
					match aMinorCommand:
						case '>': # ignore only the A>: prompt
							pass
						case 'O':
							match aMinorCommand:
								case 'K': # ignore the OK: prompt
									pass

				case 'S':
					# print(aDataString)  # SSSLCCCCCCSSSSCCSSSSSSSSSSSSSSAS
					match aMinorCommand:
						case '*':
							if len(aDataArray) == 2:
								aSwitchPort   = int(aDataArray[0], 16)
								aSwitchState  = int(aDataArray[1]) != 0
								aSwitchKey	= f"{self.id}-{aSwitchPort:02X}"
								aSwitch	   = self.portDevices[aSwitchPort]
								aSwitch.state = aSwitchState
								self.platform.switchStates[aSwitchKey] = aSwitchState
								self.platform.machine.switch_controller.process_switch_by_num(aSwitchKey, aSwitch.state, self.platform)

						case '@':
							aPort = 0
							for aPortChar in aDataString:
								aSwitch    = self.portDevices[aPort]
								aSwitchKey = f"{self.id}-{aPort:02X}"
								#print("S@ ", aPortChar, aSwitchKey)
								match aPortChar:
									case '0':
										self.platform.switchStates[aSwitchKey] = 0
										if aSwitch is not None:
											aSwitch.state = False
									case '1':
										self.platform.switchStates[aSwitchKey] = 1
										if aSwitch is not None:
											aSwitch.state = True
									case _: # if this port is not a switch (anymore) ...
										self.platform.switchStates[aSwitchKey] = None # ... delete it from the states list
								# print(f"{aSwitchKey} -> {self.platform.switchStates.get(aSwitchKey)}")
								aPort += 1
							self.switchesAreValid = True

				case 'X':
					match aMinorCommand:
						case '?':
							aPort = 0
							#print(aDataString)  # SSSLCCCCCCSSSSCCSSSSSSSSSSSSSSAS
							for aPortChar in aDataString:
								match aPortChar:
									case 'C':
										self.injectDevice("coils", aPort)
									case 'L':
										self.injectLEDStrip(aPort)
									case 'S':
										self.injectDevice("switches", aPort)
								aPort += 1
							self.devicesAreValid = True

						case 'I':
							if len(aDataArray) > 0:
								self.platform.connectBoardWithID(self, aDataArray[0])
								self.platform.info_log(f"set board type to {self.id} for {self}")
								self.idIsValid = True

						case '@':
							pass
			if not ack:
				self.platform.error_log("??")
			if len(error) > 0:
				self.platform.error_log(error)
		else:
			self.platform.error_log(f"!!: message too short: {self.receiveIndex:d}\n")


#	def start_tasks(self):
#		""" Schedule LED updates."""
#		self.tasks.append(self.platform.machine.clock.schedule_interval(self._update_leds, 1 / 10)) #board.config['led_hz']
#
#	def _update_leds(self):
#		# Called every tick to update the LEDs on this board
#		for breakout_address in self.breakouts_with_leds:
#			dirty_leds = {k:v.current_color for (k, v) in self.platform.fast_exp_leds.items() if (v.dirty and v.address == breakout_address)}
#
#			if dirty_leds:
#				# TODO add the pre-encoded address to the defines file?
#				msg_header = ''.join([f'{x:02X}' for x in f'RD@{breakout_address}:'.encode()])  # RD@<address>:, encode to binary then convert to hex chars
#				msg = f'{len(dirty_leds):02X}'
#
#				for led_num, color in dirty_leds.items():
#					msg += f'{led_num[3:]}{color}'
#
#				log_msg = f'RD@{breakout_address}:{msg}'  # pretty version of the message for the log
#
#				try:
#					self.communicator.send_bytes(b16decode(f'{msg_header}{msg}'), log_msg)
#				except Exception as e:
#					self.log.error(f"Error decoding the following message for board {breakout_address} : {msg_header}{msg}")
#					self.log.debug("Attempted update that caused this error: %s", dirty_leds)
#					raise e

	def updateLEDs(self):
		"""Update all connected LEDs."""
		for aDevice in self.portDevices:
			if type(aDevice) is GepardLEDString: # check if we have a led string
				aDevice.updateLEDs()


	def start_tasks(self):
		"""Start listening for commands and schedule watchdog."""
		print(f"start_tasks {self}")
		#self.reset()

#		if self.config['led_hz'] > 30:
#			self.config['led_hz'] = 30

		#self.tasks.append(self.machine.clock.schedule_interval(self.update_leds, 1 / 30))
