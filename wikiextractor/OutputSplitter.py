import bz2

class OutputSplitter:

	"""
	File-like object, that splits output to multiple files of a given max size.
	"""

	def __init__(self, nextFile, max_file_size=0, compress=True):
		"""
		:param nextFile: a NextFile object from which to obtain filenames
			to use.
		:param max_file_size: the maximum size of each file.
		:para compress: whether to write data with bzip compression.
		"""
		self.nextFile = nextFile
		self.compress = compress
		self.max_file_size = max_file_size
		self.file = self.open(self.nextFile.next())

	def reserve(self, size):
		if self.file.tell() + size > self.max_file_size:
			self.close()
			self.file = self.open(self.nextFile.next())

	def write(self, data):
		self.reserve(len(data))
		if self.compress:
			self.file.write(data.encode('utf-8'))
		else:
			self.file.write(data)

	def close(self):
		self.file.close()

	def open(self, filename):
		if self.compress:
			return bz2.BZ2File(filename + '.bz2', 'w')
		else:
			return open(filename, 'w',encoding='utf-8')
