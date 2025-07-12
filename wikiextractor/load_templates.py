import logging
from wikiextractor import constents
from wikiextractor.extract.extract import Extractor, define_template


def load_templates(file, output_file=None):
	"""
	Load templates from :param file:.
	:param output_file: file where to save templates and modules.
	:return: number of templates loaded.
	"""
	articles = 0
	templates = 0
	page = []
	inText = False
	if output_file:
		output = open(output_file, 'w')
	for line in file:
		#line = line.decode('utf-8')
		if '<' not in line:  # faster than doing re.search()
			if inText:
				page.append(line)
			continue
		m = constents.tagRE.search(line)
		if not m:
			continue
		tag = m.group(2)
		if tag == 'page':
			page = []
		elif tag == 'title':
			title = m.group(3)
			if not output_file and not constents.templateNamespace:  # do not know it yet
				# we reconstruct it from the first title
				colon = title.find(':')
				if colon > 1:
					constents.templateNamespace = title[:colon]
					Extractor.templatePrefix = title[:colon + 1]
			# FIXME: should reconstruct also moduleNamespace
		elif tag == 'text':
			inText = True
			line = line[m.start(3):m.end(3)]
			page.append(line)
			if m.lastindex == 4:  # open-close
				inText = False
		elif tag == '/text':
			if m.group(1):
				page.append(m.group(1))
			inText = False
		elif inText:
			page.append(line)
		elif tag == '/page':
			if title.startswith(Extractor.templatePrefix):
				define_template(title, page)
				templates += 1
			# save templates and modules to file
			if output_file and (title.startswith(Extractor.templatePrefix) or
								title.startswith(constents.modulePrefix)):
				output.write('<page>\n')
				output.write('   <title>%s</title>\n' % title)
				output.write('   <ns>10</ns>\n')
				output.write('   <text>')
				for line in page:
					output.write(line)
				output.write('   </text>\n')
				output.write('</page>\n')
			page = []
			articles += 1
			if articles % 100000 == 0:
				logging.info("Preprocessed %d pages", articles)
	if output_file:
		output.close()
		logging.info("Saved %d templates to '%s'", templates, output_file)
	return templates


