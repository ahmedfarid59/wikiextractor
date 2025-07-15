from multiprocessing import freeze_support
import logging
import os
import sys
from wikiextractor import constents
from wikiextractor.collect_pages import collect_pages
from wikiextractor.extract.extract import Extractor, ignoreTag
from wikiextractor.load_templates import load_templates
from wikiextractor.parse_arguments import parse_arguments
from wikiextractor.process_dump import process_dump
def main():
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
		if file_size and file_size < constents.minFileSize:
			raise ValueError()
	except ValueError:
		logging.error('Insufficient or invalid size: %s', args.bytes)
		exit()
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
		exit()

	output_path = args.output
	if output_path != '-' and not os.path.isdir(output_path):
		try:
			os.makedirs(output_path)
		except:
			logging.error('Could not create: %s', output_path)
			exit()

	process_dump(input_file, args.templates, output_path, file_size,
					args.compress, args.processes, args.html_safe, not args.no_templates)

if __name__ == "__main__":
	freeze_support()
	main()