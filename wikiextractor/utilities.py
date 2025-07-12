import bz2
import os


def decode_open(filename, mode='rt', encoding='utf-8'):
	"""
	Open a file, decode and decompress, depending on extension `gz`, or 'bz2`.
	:param filename: the file to open.
	"""
	ext = os.path.splitext(filename)[1]
	if ext == '.gz':
		import gzip
		return gzip.open(filename, mode, encoding=encoding)
	elif ext == '.bz2':
		return bz2.open(filename, mode=mode, encoding=encoding)
	else:
		return open(filename, mode, encoding=encoding)


