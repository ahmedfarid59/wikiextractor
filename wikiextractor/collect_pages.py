from wikiextractor import constents

def  collect_pages(text):
	"""param text: the text of a wikipedia file dump."""
	# we collect individual lines, since str.join() is significantly faster
	# than concatenation
	page = []
	id = ''
	revid = ''
	last_id = ''
	inText = False
	redirect = False
	for line in text:
		if '<' not in line:     # faster than doing re.search()
			if inText:
				page.append(line)
			continue
		m = constents.tagRE.search(line)
		if not m:
			continue
		tag = m.group(2)
		if tag == 'page':
			page = []
			redirect = False
		elif tag == 'id' and not id:
			id = m.group(3)
		elif tag == 'id' and id: # <revision> <id></id> </revision>
			revid = m.group(3)
		elif tag == 'title':
			title = m.group(3)
		elif tag == 'redirect':
			redirect = True
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
			colon = title.find(':')
			if (colon < 0 or (title[:colon] in constents.acceptedNamespaces) and id != last_id and
					not redirect and not title.startswith(constents.templateNamespace)):
				yield (id, revid, title, page)
				last_id = id
			id = ''
			revid = ''
			page = []
			inText = False
			redirect = False
