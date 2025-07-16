import os

class NextFile:

	"""
	Synchronous generation of next available file name.
	"""

	def __init__(self, path_name,ext="xml"):
		self.path_name = path_name
		self.file_index = 0
		self.ext=ext

	def next(self):
		self.file_index +=  1 
		return self._filepath()

	def _filepath(self):
		return os.path.join(self.path_name, f"{self.file_index}.{self.ext}")