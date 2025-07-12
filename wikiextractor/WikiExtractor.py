import bz2
import logging
import os.path
import re  # TODO use regex when it will be standard
import sys
from wikiextractor import constents
from wikiextractor.Multiprocess_support import extract_process, reduce_process
from wikiextractor.NextFile import NextFile
from wikiextractor.OutputSplitter import OutputSplitter
from wikiextractor.collect_pages import collect_pages
from wikiextractor.load_templates import load_templates
from wikiextractor.utilities import decode_open
from .parse_arguments import parse_arguments 
from multiprocessing import Queue, get_context
from timeit import default_timer
from .extract.extract import Extractor, ignoreTag, define_template

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
	# collect siteinfo
	for line in input:
		line = line #.decode('utf-8')
		m = constents.tagRE.search(line)
		if not m:
			continue
		tag = m.group(2)
		if tag == 'base':
			# discover urlbase from the xml dump file
			# /mediawiki/siteinfo/base
			base = m.group(3)
			constents.urlbase = base[:base.rfind("/")]
		elif tag == 'namespace':
			constents.knownNamespaces.add(m.group(3))
			if re.search('key="10"', line):
				constents.templateNamespace = m.group(3)
				Extractor.templatePrefix = constents.templateNamespace + ':'
			elif re.search('key="828"', line):
				constents.moduleNamespace = m.group(3)
				constents.modulePrefix = constents.moduleNamespace + ':'
		elif tag == '/siteinfo':
			break
	if expand_templates:
		# preprocess
		template_load_start = default_timer()
		if template_file and os.path.exists(template_file):
			logging.info("Preprocessing '%s' to collect template definitions: this may take some time.", template_file)
			file = decode_open(template_file)
			templates = load_templates(file)
			file.close()
		else:
			if input_file == '-':
				# can't scan then reset stdin; must error w/ suggestion to specify template_file
				raise ValueError("to use templates with stdin dump, must supply explicit template-file")
			logging.info("Preprocessing '%s' to collect template definitions: this may take some time.", input_file)
			templates = load_templates(input, template_file)
			input.close()
			input = decode_open(input_file)
		template_load_elapsed = default_timer() - template_load_start
		logging.info("Loaded %d templates in %.1fs", templates, template_load_elapsed)

	if out_file == '-':
		output = sys.stdout
		if file_compress:
			logging.warn("writing to stdout, so no output compression (use an external tool)")
	else:
		nextFile = NextFile(out_file)
		output = OutputSplitter(nextFile, file_size, file_compress)

	# process pages
	logging.info("Starting page extraction from %s.", input_file)
	extract_start = default_timer()
	# Parallel Map/Reduce:
	# - pages to be processed are dispatched to workers
	# - a reduce process collects the results, sort them and print them.
	# fixes MacOS error: TypeError: cannot pickle '_io.TextIOWrapper' object
	Process = get_context("fork").Process
	maxsize = 10 * process_count
	# output queue
	output_queue = Queue(maxsize=maxsize)

	# Reduce job that sorts and prints output
	reduce = Process(target=reduce_process, args=(output_queue, output))
	reduce.start()

	# initialize jobs queue
	jobs_queue = Queue(maxsize=maxsize)

	# start worker processes
	logging.info("Using %d extract processes.", process_count)
	workers = []
	for _ in range(max(1, process_count)):
		extractor = Process(target=extract_process,
							args=(jobs_queue, output_queue, html_safe))
		extractor.daemon = True  # only live while parent process lives
		extractor.start()
		workers.append(extractor)

	# Mapper process

	# we collect individual lines, since str.join() is significantly faster
	# than concatenation

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

	if output != sys.stdout:
		output.close()
	extract_duration = default_timer() - extract_start
	extract_rate = ordinal / extract_duration
	logging.info("Finished %d-process extraction of %d articles in %.1fs (%.1f art/s)",
				 process_count, ordinal, extract_duration, extract_rate)


# ----------------------------------------------------------------------




# ----------------------------------------------------------------------

# Minimum size of output files
minFileSize = 200 * 1024


def main():
	global templateCache
	args = parse_arguments()
	
	Extractor.keepLinks = args.links
	Extractor.HtmlFormatting = args.html
	if args.html:
		Extractor.keepLinks = True
	Extractor.to_json = args.json

	try:
		power = 'kmg'.find(args.bytes[-1].lower()) + 1
		# 0 bytes means put a single article per file.
		file_size = 0 if args.bytes == '0' else int(args.bytes[:-1]) * 1024 ** power
		if file_size and file_size < minFileSize:
			raise ValueError()
	except ValueError:
		logging.error('Insufficient or invalid size: %s', args.bytes)
		return

	if args.namespaces:
		constents.acceptedNamespaces = set(args.namespaces.split(','))

	FORMAT = '%(levelname)s: %(message)s'
	logging.basicConfig(format=FORMAT)

	logger = logging.getLogger()
	if not args.quiet:
		logger.setLevel(logging.INFO)
	if args.debug:
		logger.setLevel(logging.DEBUG)

	input_file = args.input

	if not Extractor.keepLinks:
		ignoreTag('a')

	# sharing cache of parser templates is too slow:
	# manager = Manager()
	# templateCache = manager.dict()

	if args.article:
		if args.templates:
			if os.path.exists(args.templates):
				with open(args.templates) as file:
					load_templates(file)
		with open(input_file) as input:
			for id, revid, title, page in collect_pages(input):
				Extractor(id, revid, constents.urlbase, title, page).extract(sys.stdout)
		return

	output_path = args.output
	if output_path != '-' and not os.path.isdir(output_path):
		try:
			os.makedirs(output_path)
		except:
			logging.error('Could not create: %s', output_path)
			return

	process_dump(input_file, args.templates, output_path, file_size,
				 args.compress, args.processes, args.html_safe, not args.no_templates)

if __name__ == '__main__':
	main()
