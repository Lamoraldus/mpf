"""Gepard Switch."""
import logging

from mpf.platforms.interfaces.switch_platform_interface import SwitchPlatformInterface
from mpf.platforms.gepard.gepard_utils import GepardUtils

class GepardSwitch(SwitchPlatformInterface):

	"""A Gepard Switch."""

	__slots__ = ["board", "port", "state"]

	def __init__(self, board, number, platform):
		"""initialize input."""
		super().__init__({}, number, platform)
		self.board = board
		self.port  = GepardUtils.indexFromDashedKey(self.number, 1)
		self.state = False

	def get_board_name(self):
		"""Return Gepard board id."""
		return self.board.name()
