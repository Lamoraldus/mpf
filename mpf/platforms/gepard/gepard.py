# pylint: disable-msg=too-many-lines
"""Gepard Hardware interface.

Contains the hardware interface and drivers for the Gepard
platform hardware, including the solenoid, input, and neopixel
boards.
"""
import asyncio, os
from collections import defaultdict
from typing import Dict, List, Set, Union, Tuple, Optional  # pylint: disable-msg=cyclic-import,unused-import

from mpf.core.utility_functions import Util
from mpf.platforms.base_serial_communicator import HEX_FORMAT

from mpf.platforms.interfaces.driver_platform_interface import PulseSettings, HoldSettings

from mpf.platforms.gepard.gepard_board import GepardBoard
from mpf.platforms.gepard.gepard_switch import GepardSwitch
from mpf.platforms.gepard.gepard_coil import GepardCoil

from mpf.platforms.gepard.gepard_led import GepardLED
from mpf.platforms.gepard.gepard_led_channel import GepardLEDChannel
from mpf.platforms.gepard.gepard_led_string import GepardLEDString
from mpf.platforms.gepard.gepard_utils import GepardUtils

from mpf.core.platform import \
	DriverPlatform, DriverSettings, DriverConfig, \
	LightsPlatform, LightConfig, \
	ServoPlatform, \
	SwitchPlatform, SwitchSettings, SwitchConfig, \
	RepulseSettings
from mpf.core.platform_batch_light_system import PlatformBatchLight, PlatformBatchLightSystem

#MYPY = False
#if MYPY:   # pragma: no cover
#	from mpf.platforms.opp.opp_coil import OPPSolenoid  # pylint: disable-msg=cyclic-import,unused-import
#	from mpf.platforms.opp.opp_incand import OPPIncand  # pylint: disable-msg=cyclic-import,unused-import
#	from mpf.platforms.opp.opp_switch import OPPSwitch  # pylint: disable-msg=cyclic-import,unused-import


# pylint: disable-msg=too-many-instance-attributes
# class GepardHardwarePlatform(LightsPlatform, SwitchPlatform, DriverPlatform, ServoPlatform):
class GepardHardwarePlatform(DriverPlatform, SwitchPlatform, LightsPlatform):

	"""Platform class for the Gepard hardware.

	Args:
	----
		machine: The main ``MachineController`` instance.

	"""

	__slots__ = ["boardDict", "boardSet", "config", "switchStates", "_light_system"]

	def __init__(self, machine) -> None:
		"""initialize Gepard platform."""
		super().__init__(machine)
		self.boardDict = {}    # type: Dict[str, GepardBoard]
		self.boardSet  = set() # type: Set[GepardBoard]
		self.switchStates = dict()

		self.features['tickless'] = True

		self.config = self.machine.config_validator.validate_config("gepard", self.machine.config.get('gepard', {}))
		self._configure_device_logging_and_debug("gepard", self.config)
		# self._poll_response_received = {}   # type: Dict[str, asyncio.Event]
		assert self.log is not None


	async def initialize(self):
		"""initialize connections to Gepard hardware."""
		await self._connect_to_hardware()
		self.machine.events.add_handler('init_phase_3', self._start_communicator_tasks)
		self._light_system = PlatformBatchLightSystem(self.machine.clock, self._send_multiple_light_update, self.machine.config['mpf']['default_light_hw_update_hz'], 64)

	def _start_communicator_tasks(self, **kwargs):  # init_phase_3
		del kwargs
		for aBoard in self.boardSet:
			# comm.start_watchdog()
			aBoard.start_tasks()

	async def start(self):
		"""Start polling and listening for commands."""
		self.debug_log(f"GepardHardwarePlatform start {self}")

		# start polling
#		for chain_serial in self.read_input_msg:
#			self._poll_task[chain_serial] = asyncio.create_task(self._poll_sender(chain_serial))
#			self._poll_task[chain_serial].add_done_callback(Util.raise_exceptions)

		# start listening for commands
		for aBoard in self.boardSet:
			await aBoard.start_read_loop()

		self._light_system.start()

	def stop(self):
		"""Stop hardware and close connections."""
#		if self._light_system:
#			self._light_system.stop()

#		for task in self._poll_task.values():
#			task.cancel()
#		self._poll_task = {}

#		if self._incand_task:
#			self._incand_task.cancel()
#			self._incand_task = None

		for aBoard in self.boardSet:
			aBoard.stop()

		self.boardSet = []

	def __repr__(self):
		"""Return string representation."""
		return '<Platform.Gepard>'

	def get_info_string(self):
		"""Dump infos about boards."""
		if not self.boardSet:
			return "No connection to any CPU board."

		infos = "Connected CPUs:\n"
		for connection in sorted(self.boardSet, key=lambda x: x.chain_serial):
			infos += " - Port: {} at {} baud. Chain Serial: {}\n".format(connection.port, connection.baud,
																		 connection.chain_serial)

		return infos

	async def _connect_to_hardware(self):
		"""Connect to each port by scanning the /dev directory.
		"""
		self.debug_log(f"GepardHardwarePlatform _connect_to_hardware {self}")

		devicePath = self.config['dev_path']
		if not devicePath:
			devicePath = "/dev"
		
		aPrefix = self.config['prefix']
		if not aPrefix:
			aPrefix = "cu.usbmodem"

		for aFile in os.listdir(path=devicePath):
			if aFile.startswith(aPrefix):
				self.info_log(f"GepardHardwarePlatform found {aFile}")
				aPath = devicePath + "/" + aFile
				aBoard = GepardBoard(platform=self, tty=aPath, baud=self.config['baud'])
				aBoard.log = self.log
				await aBoard.connect()
				self.boardSet.add(aBoard)


	def boardFromDashedKey(self, aKey):
		aBoardIDString = GepardBoard.boardKeyFromDashedKey(aKey)
		aBoardDict = self.boardDict.get(aBoardIDString)
		if aBoardDict is None:
			raise KeyError(f"Gepard Board for key {aKey} is not connected! {self.boardDict}")
		return aBoardDict

	def connectBoardWithID(self, aBoard, anID):
		"""Register the processors to the platform.

		Args:
		----
			serial_number: Serial number of chain.
			communicator: Instance of OPPSerialCommunicator
		"""
		self.debug_log(f"GepardHardwarePlatform connectBoardWithID {aBoard} {anID}")
		aBoard.id = GepardBoard.boardKeyFromDashedKey(anID)
		self.boardDict[aBoard.id] = aBoard

	def send_to_processor(self, anID, msg):
		"""Send message to processor with specific serial number.

		Args:
		----
			chain_serial: Serial of the processor.
			msg: Message to send.
		"""
		self.boardFromDashedKey(anID).send(msg)

### SwitchPlatform
	def configure_switch(self, number: str, config: SwitchConfig, platform_config: dict) -> GepardSwitch:
		aBoard  = self.boardFromDashedKey(number)
		aDevice = aBoard.deviceAtPortOfDashedKey(number)
		if aDevice is None:
			self.info_log(f"configure_switch {number} {config} {platform_config}")
			aDevice = GepardSwitch(aBoard, number, self)
		else:
			self.info_log(f"configure_switch {number} {config} DUPLICATE")
		aDevice.state = self.switchStates[f"{number}"] # set the initial state we retrieved on boot
		aBoard.portDevices[aDevice.port] = aDevice
		return aDevice

	async def get_hw_switch_states(self) -> Dict[str, bool]:
		return self.switchStates;

### DriverPlatform
	def configure_driver(self, config:DriverConfig, number:str, platform_config:dict) -> GepardCoil:
		self.info_log(f"configure_driver {config} {platform_config}")
		aBoard  = self.boardFromDashedKey(number)
		aDevice = GepardCoil(aBoard, number, self)
		aBoard.portDevices[aDevice.port] = aDevice
		return aDevice

	def clear_hw_rule(self, switch: SwitchSettings, coil: DriverSettings):
		"""Subclass this method in a platform module to clear a hardware switch rule for this switch.

		Clearing a hardware rule means actions on this switch will no longer
		affect coils.

		Another way to think of this is that it 'disables' a hardware rule.
		This is what you'd use to disable flippers and autofire_coils during
		tilt, game over, etc.

		"""
		raise NotImplementedError

	def _switchCoilControl(self, enable_switch:SwitchSettings, coil:DriverSettings, onstate, startStop):
		aSwitchBoard = self.boardFromDashedKey(enable_switch.hw_switch.number)
		aCoilBoard   = self.boardFromDashedKey(coil.hw_driver.number)
		if aSwitchBoard == aCoilBoard:
			aSwitch = aSwitchBoard.deviceAtPortOfDashedKey(enable_switch.hw_switch.number)
			aCoil = aCoilBoard.deviceAtPortOfDashedKey(coil.hw_driver.number)
			aCoil._updateSettings(coil.pulse_settings, coil.hold_settings, 0) # update the coil settings
			aCoilBoard.sendStr(f"C~ {aCoil.port:02X} {aSwitch.port:02X} {onstate} {startStop}\n")

	def set_pulse_on_hit_rule(self, enable_switch: SwitchSettings, coil: DriverSettings):
		"""Set pulse on hit rule on driver.

		Pulses a driver when a switch is hit. When the switch is released the pulse continues. Typically used for
		autofire coils such as pop bumpers.
		"""
		self._switchCoilControl(enable_switch, coil, 1, 1)

	def set_pulse_on_hit_and_release_rule(self, enable_switch: SwitchSettings, coil: DriverSettings):
		"""Set pulse on hit and release rule to driver.

		Pulses a driver when a switch is hit. When the switch is released the pulse is canceled. Typically used on
		the main coil for dual coil flippers without eos switch.
		"""
		self._switchCoilControl(enable_switch, coil, 1, 1)
		self._switchCoilControl(enable_switch, coil, 0, 0)

	def set_pulse_on_hit_and_enable_and_release_rule(self, enable_switch: SwitchSettings, coil: DriverSettings):
		"""Set pulse on hit and enable and release rule on driver.

		Pulses a driver when a switch is hit. Then enables the driver (may be with pwm). When the switch is released
		the pulse is canceled and the driver gets disabled. Typically used for single coil flippers.
		"""
		self._switchCoilControl(enable_switch, coil, 1, 1)
		self._switchCoilControl(enable_switch, coil, 0, 0)

	def set_pulse_on_hit_and_release_and_disable_rule(self, enable_switch: SwitchSettings,
													  eos_switch: SwitchSettings, coil: DriverSettings,
													  repulse_settings: Optional[RepulseSettings]):
		"""Set pulse on hit and enable and release and disable rule on driver.

		Pulses a driver when a switch is hit. When the switch is released
		the pulse is canceled and the driver gets disabled. When the eos_switch is hit the pulse is canceled
		and the driver becomes disabled. Typically used on the main coil for dual-wound coil flippers with eos switch.
		"""
		raise NotImplementedError

	def set_pulse_on_hit_and_enable_and_release_and_disable_rule(self, enable_switch: SwitchSettings,
																 eos_switch: SwitchSettings, coil: DriverSettings,
																 repulse_settings: Optional[RepulseSettings]):
		"""Set pulse on hit and enable and release and disable rule on driver.

		Pulses a driver when a switch is hit. Then enables the driver (may be with pwm). When the switch is released
		the pulse is canceled and the driver becomes disabled. When the eos_switch is hit the pulse is canceled
		and the driver becomes enabled (likely with PWM).
		Typically used on the coil for single-wound coil flippers with eos switch.
		"""
		raise NotImplementedError


###  LightsPlatform

	def configure_light(self, number:str, subtype:str, config:LightConfig, platform_config:dict) -> "LightPlatformInterface":
		"""Subclass this method in a platform module to configure a light.

		This method should return a reference to the light
		object which will be called to access the hardware.
		"""
		self.info_log(f"configure_light {number}");
		aBoard  = self.boardFromDashedKey(number)
		aDevice = aBoard.deviceAtPortOfDashedKey(number)
		if type(aDevice) is GepardLEDString: # check if we have a led string
			aLED	 = aDevice.ledForDashedKey(number, True)
			aChannel = GepardLEDChannel(aLED, number, config, self._light_system)
			return aChannel
		return None

	def parse_light_number_to_channels(self, number: str, subtype: str):
		"""Parse light number to a list of channels."""
		# self.info_log(f"parse_light_number_to_channels {number} {subtype}");
		return [{"number": f"{number}-{i}"} for i in range(3)]

#	def light_sync(self):
#		"""Update lights synchronously.
#
#		Called after channels of a light were updated. Can be used if multiple channels need to be flushed at once.
#		"""

	async def _send_multiple_light_update(self, sequential_brightness_list:List[Tuple[GepardLEDChannel, float, int]]):

		# self.info_log(f"_send_multiple_light_update {sequential_brightness_list}")

		for aChannel, brightness, fade_ms in sequential_brightness_list:
			aChannel.brightness = brightness # save the new channel value

		for aBoard in self.boardSet:
			aBoard.updateLEDs()
