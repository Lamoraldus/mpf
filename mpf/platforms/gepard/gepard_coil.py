"""Gepard Coil."""
import logging

from mpf.platforms.interfaces.driver_platform_interface import DriverPlatformInterface, PulseSettings, HoldSettings

class GepardCoil(DriverPlatformInterface):

	"""A Gepard Coil."""

	__slots__ = ["board", "port", "pulsePower", "pulseDuration", "holdPower", "holdDuration"]

	def __init__(self, board, number, platform):
		"""initialize input."""
		super().__init__({}, number)
		self.board = board
		self.port  = int(self.number.split("-")[-1], 16)
		self.pulsePower    = None
		self.pulseDuration = None
		self.holdPower     = None
		self.holdDuration  = None

	def get_board_name(self):
		"""Return Gepard board id."""
		return self.board.name()

	def _updateSettings(self, pulse_settings:PulseSettings, hold_settings:HoldSettings, ignoreEmergency):
		needsUpdate = False

		if pulse_settings is not None and pulse_settings.duration is not None:
			if int(pulse_settings.power * 255) != self.pulsePower:
				needsUpdate = True
				self.pulsePower = int(pulse_settings.power * 255)
			if pulse_settings.duration != self.pulseDuration:
				needsUpdate = True
				self.pulseDuration = pulse_settings.duration
		else:
			self.pulsePower    = 0
			self.pulseDuration = 0

		if hold_settings is not None:
			if int(hold_settings.power * 255) != self.holdPower:
				needsUpdate = True
				self.holdPower = int(hold_settings.power * 255)
			if hold_settings.duration is not None:
				if hold_settings.duration != self.holdDuration:
					needsUpdate = True
					self.holdDuration = hold_settings.duration
			else:
				if 0 != self.holdDuration:
					ignoreEmergency = 1
					self.holdDuration = 0
					needsUpdate = True
		else:
			self.holdPower    = 0
			self.holdDuration = 0

		if needsUpdate:
			print(f"_updateSettings {self.board.id}-{self.port:02X} pp:{self.pulsePower} pd:{self.pulseDuration} hp:{self.holdPower} hd:{self.holdDuration} ignore:{ignoreEmergency}")
			self.board.sendStr(f"C! {self.port:02X} {self.pulsePower:02X} {self.pulseDuration:02X} {self.holdPower:02X} {self.holdDuration:02X} {ignoreEmergency}\n")
		return needsUpdate

	def pulse(self, pulse_settings: PulseSettings):
		"""Pulse a driver.

		Pulse this driver for a pre-determined amount of time, after which
		this driver is turned off automatically. Note that on most platforms,
		pulse times are a max of 255ms. (Beyond that MPF will send separate
		enable() and disable() commands.
		"""
		self._updateSettings(pulse_settings, None, 0)
		self.board.sendStr(f"C1 {self.port:02X}\n")

	def enable(self, pulse_settings: PulseSettings, hold_settings: HoldSettings):
		"""Enable this driver, which means it's held "on" indefinitely until it's explicitly disabled."""
		self._updateSettings(pulse_settings, hold_settings, 1)
		self.board.sendStr(f"C1 {self.port:02X}\n")

	def disable(self):
		"""Disable the driver."""
		self.board.sendStr(f"C0 {self.port:02X}\n")

	def timed_enable(self, pulse_settings: PulseSettings, hold_settings: HoldSettings):
		"""Enable the driver for a pre-specified duration."""
		self._updateSettings(pulse_settings, hold_settings, 0)
		self.board.sendStr(f"C1 {self.port:02X}\n")
