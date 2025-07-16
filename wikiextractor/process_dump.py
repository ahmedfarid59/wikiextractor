import logging, os , re , sys
from multiprocessing import get_context
from timeit import default_timer
from wikiextractor import constents
from wikiextractor.Multiprocess_support import extract_process, reduce_process
from wikiextractor.collect_pages import collect_pages
from wikiextractor.extract_info import extract_info
from wikiextractor.load_templates import load_templates
from wikiextractor.utilities import decode_open

def process_dump(input_file, template_file, out_file, file_size, file_compress,
				 process_count, html_safe, expand_templates=True):
	"""
	:param input_file: name of the wikipedia dump file; '-' to read from stdin
	:param template_file: optional file with template definitions.
	:param out_file: directory where to store extracted data, or '-' for stdout
	:param file_size: max size of each extracted file, or None for no max (one file)
	:param file_compress: whether to compress files with bzip.
	:param process_count: number of extraction processes to spawn.
	:html_safe: whether to convert entities in text to HTML.
	:param expand_templates: whether to expand templates.
	"""
	input = decode_open(input_file)
	extract_info(input)
	if expand_templates:
		# preprocess
		template_load_start = default_timer()
		if template_file and os.path.exists(template_file):
			logging.info("Preprocessing '%s' to collect template definitions: this may take some time.", template_file)
			file = decode_open(template_file)
			templates = load_templates(file)
			file.close()
		else:
			logging.info("Preprocessing '%s' to collect template definitions: this may take some time.", input_file)
			templates = load_templates(input, template_file)
			input.close()
			input = decode_open(input_file)
		template_load_elapsed = default_timer() - template_load_start
		logging.info("Loaded %d templates in %.1fs", templates, template_load_elapsed)
	# process pages
	logging.info("Starting page extraction from %s.", input_file)
	extract_start = default_timer()
	# Parallel Map/Reduce:
	# - pages to be processed are dispatched to workers - a reduce process collects the results, sort them and print them.
	ctx = get_context("spawn")
	Process =ctx.Process
	maxsize = 10 * process_count
	# output queue
	output_queue = ctx.Queue(maxsize=maxsize)
	# Reduce job that sorts and prints output
	reduce = Process(target=reduce_process, args=(output_queue, out_file,  file_size, file_compress))
	reduce.start()
	# initialize jobs queue
	jobs_queue = ctx.Queue(maxsize=maxsize)
	# start worker processes
	logging.info("Using %d extract processes.", process_count)
	workers = []
	for _ in range(max(1, process_count)):
		extractor = Process(target=extract_process,
								args=(jobs_queue, output_queue, html_safe))
		extractor.daemon = True  # only live while parent process lives
		extractor.start()
		workers.append(extractor)
	# we collect individual lines, since str.join() is significantly faster
	ordinal = 0  # page count
	for id, revid, title, page in collect_pages(input):
		job = (id, revid, constents.urlbase, title, page, ordinal)
		jobs_queue.put(job)  # goes to any available extract_process
		ordinal += 1
	input.close()
	# signal termination
	for _ in workers:
		jobs_queue.put(None)
	# wait for workers to terminate
	for w in workers:
		w.join()
	# signal end of work to reduce process
	output_queue.put(None)
	# wait for it to finish
	reduce.join()
	extract_duration = default_timer() - extract_start
	extract_rate = ordinal / extract_duration
	logging.info("Finished %d-process extraction of %d articles in %.1fs (%.1f art/s)",
				 process_count, ordinal, extract_duration, extract_rate)


# ----------------------------------------------------------------------




# ----------------------------------------------------------------------
