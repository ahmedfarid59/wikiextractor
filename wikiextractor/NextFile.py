import os


class NextFile:

	"""
	Synchronous generation of next available file name.
	"""

	filesPerDir = 100

	def __init__(self, path_name):
		self.path_name = path_name
		self.dir_index = -1
		self.file_index = -1

	def next(self):
		self.file_index = (self.file_index + 1) % NextFile.filesPerDir
		if self.file_index == 0:
			self.dir_index += 1
		dirname = self._dirname()
		if not os.path.isdir(dirname):
			os.makedirs(dirname)
		return self._filepath()

	def _dirname(self):
		char1 = self.dir_index % 26
		char2 = int(self.dir_index / 26) % 26
		return os.path.join(self.path_name, '%c%c' % (ord('A') + char2, ord('A') + char1))

	def _filepath(self):
		return '%s/wiki_%02d' % (self._dirname(), self.file_index)
