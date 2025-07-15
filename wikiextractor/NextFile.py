import os

class NextFile:

	"""
	Synchronous generation of next available file name.
	"""

	def __init__(self, path_name):
		self.path_name = path_name
		self.file_index = -1

	def next(self):
		self.file_index +=  1 
		return self._filepath()

	def _filepath(self):
		return os.path.join(self.path_name, str(self.file_index))