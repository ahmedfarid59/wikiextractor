# Multiprocess support

from io import StringIO
import logging
from timeit import default_timer

from wikiextractor.NextFile import NextFile
from wikiextractor.OutputSplitter import OutputSplitter
from wikiextractor.extract.extract import Extractor


def extract_process(jobs_queue, output_queue, html_safe):
	"""Pull tuples of raw page content, do CPU/regex-heavy fixup, push finished text
	:param jobs_queue: where to get jobs.
	:param output_queue: where to queue extracted text for output.
	:html_safe: whether to convert entities in text to HTML.
	"""
	while True:
		job = jobs_queue.get()  # job is (id, revid, urlbase, title, page)
		if job:
			out = StringIO()  # memory buffer
			Extractor(*job[:-1]).extract(out, html_safe)  # (id, urlbase, title, page)
			text = out.getvalue()
			output_queue.put((job[-1], text))  # (ordinal, extracted_text)
			out.close()
		else:
			break

def reduce_process(output_queue, out_file, file_size, file_compress):
	"""
	Pull finished article text, write series of files (or stdout)
	:param output_queue: text to be output.
	:param output: file object where to print.
	"""
	nextFile = NextFile(out_file)
	output = OutputSplitter(nextFile, file_size, file_compress)
	interval_start = default_timer()
	period = 100000
	# FIXME: use a heap
	ordering_buffer = {}  # collected pages
	next_ordinal = 0  # sequence number of pages
	while True:
		if next_ordinal in ordering_buffer:
			output.write(ordering_buffer.pop(next_ordinal))
			next_ordinal += 1
			# progress report
			if next_ordinal % period == 0:
				interval_rate = period / (default_timer() - interval_start)
				logging.info("Extracted %d articles (%.1f art/s)",
							 next_ordinal, interval_rate)
				interval_start = default_timer()
		else:
			# mapper puts None to signal finish
			pair = output_queue.get()
			if not pair:
				break
			ordinal, text = pair
			ordering_buffer[ordinal] = text

