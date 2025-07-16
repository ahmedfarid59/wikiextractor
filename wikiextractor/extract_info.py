import re
from wikiextractor import constents
from wikiextractor.extract.extract import Extractor

def extract_info(input ):
	# collect siteinfo
	for line in input:
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
