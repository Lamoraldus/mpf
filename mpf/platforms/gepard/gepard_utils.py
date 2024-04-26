
class GepardUtils():

	@classmethod
	def indexFromDashedKey(self, aDashedKey, aPosition):
		return int(aDashedKey.split("-")[aPosition], 16)

