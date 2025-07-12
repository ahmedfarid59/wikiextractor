import time, html, json, logging, re
from sys import modules
from urllib.parse import urlencode
from wikiextractor import constents
from .Template import Template
from .Infix import Infix
from .MagicWords import MagicWords
from wikiextractor.utilities import dropNested, dropSpans, findBalanced, findMatchingBraces, get_url, lcfirst, normalizeNamespace, sharp_expr, sharp_if, sharp_switch, splitParts, ucfirst, unescape
def clean(extractor, text, expand_templates=False, html_safe=True):
	"""
	Transforms wiki markup. If the command line flag --escapedoc is set then the text is also escaped
	@see https://www.mediawiki.org/wiki/Help:Formatting
	:param extractor: the Extractor t use.
	:param text: the text to clean.
	:param expand_templates: whether to perform template expansion.
	:param html_safe: whether to convert reserved HTML characters to entities.
	@return: the cleaned text.
	"""
	if expand_templates:
		# expand templates
		# See: http://www.mediawiki.org/wiki/Help:Templates
		text = extractor.expandTemplates(text)
	else:
		# Drop transclusions (template, parser functions)
		text = dropNested(text, r'{{', r'}}')
	# Drop tables
	text = dropNested(text, r'{\|', r'\|}')
	# replace external links
	text = replaceExternalLinks(text)
	# replace internal links
	text = replaceInternalLinks(text)
	# drop MagicWords behavioral switches
	text = magicWordsRE.sub('', text)
	# ############### Process HTML ###############
	# turn into HTML, except for the content of <syntaxhighlight>
	res = ''
	cur = 0
	for m in constents.syntaxhighlight.finditer(text):
		end = m.end()
		res += unescape(text[cur:m.start()]) + m.group(1)
		cur = end
	text = res + unescape(text[cur:])
	# Handle bold/italic/quote
	if extractor.HtmlFormatting:
		text = bold_italic.sub(r'<b>\1</b>', text)
		text = bold.sub(r'<b>\1</b>', text)
		text = italic.sub(r'<i>\1</i>', text)
	else:
		text = bold_italic.sub(r'\1', text)
		text = bold.sub(r'\1', text)
		text = italic_quote.sub(r'"\1"', text)
		text = italic.sub(r'"\1"', text)
		text = quote_quote.sub(r'"\1"', text)
	# residuals of unbalanced quotes
	text = text.replace("'''", '').replace("''", '"')
	# Collect spans
	spans = []
	# Drop HTML comments
	for m in constents.comment.finditer(text):
		spans.append((m.start(), m.end()))
	# Drop self-closing tags
	for pattern in selfClosing_tag_patterns:
		for m in pattern.finditer(text):
			spans.append((m.start(), m.end()))
	# Drop ignored tags
	for left, right in ignored_tag_patterns:
		for m in left.finditer(text):
			spans.append((m.start(), m.end()))
		for m in right.finditer(text):
			spans.append((m.start(), m.end()))
	# Bulk remove all spans
	text = dropSpans(spans, text)
	# Drop discarded elements
	for tag in constents.discardElements:
		text = dropNested(text, r'<\s*%s\b[^>/]*>' % tag, r'<\s*/\s*%s>' % tag)
	if not extractor.HtmlFormatting:
		# Turn into text what is left (&amp;nbsp;) and <syntaxhighlight>
		text = unescape(text)
	# Expand placeholders
	for pattern, placeholder in placeholder_tag_patterns:
		index = 1
		for match in pattern.finditer(text):
			text = text.replace(match.group(), '%s_%d' % (placeholder, index))
			index += 1
	text = text.replace('<<', u'«').replace('>>', u'»')
	#############################################
	# Cleanup text
	text = text.replace('\t', ' ')
	text = spaces.sub(' ', text)
	text = dots.sub('...', text)
	text = re.sub(u' (,:\.\)\]»)', r'\1', text)
	text = re.sub(u'(\[\(«) ', r'\1', text)
	text = re.sub(r'\n\W+?\n', '\n', text, flags=re.U)  # lines with only punctuations
	text = text.replace(',,', ',').replace(',.', '.')
	if html_safe:
		text = html.escape(text, quote=False)
	return text
# skip level 1, it is page name level
section = re.compile(r'(==+)\s*(.*?)\s*\1')
listOpen = {'*': '<ul>', '#': '<ol>', ';': '<dl>', ':': '<dl>'}
listClose = {'*': '</ul>', '#': '</ol>', ';': '</dl>', ':': '</dl>'}
listItem = {'*': '<li>%s</li>', '#': '<li>%s</<li>', ';': '<dt>%s</dt>',
			':': '<dd>%s</dd>'}
def compact(text, mark_headers=False):
	"""Deal with headers, lists, empty sections, residuals of tables.
	:param text: convert to HTML
	"""
	page = []  # list of paragraph
	headers = {}  # Headers for unfilled sections
	emptySection = False  # empty sections are discarded
	listLevel = ''  # nesting of lists
	for line in text.split('\n'):
		if not line:
			if len(listLevel):    # implies Extractor.HtmlFormatting
				for c in reversed(listLevel):
					page.append(listClose[c])
					listLevel = ''
			continue
		# Handle section titles
		m = section.match(line)
		if m:
			title = m.group(2)
			lev = len(m.group(1))
			if Extractor.HtmlFormatting:
				page.append("<h%d>%s</h%d>" % (lev, title, lev))
			if title and title[-1] not in '!?':
				title += '.'
			if mark_headers:
				title = "## " + title
			headers[lev] = title
			# drop previous headers
			headers = { k:v for k,v in headers.items() if k <= lev }
			emptySection = True
			continue
		# Handle page title
		if line.startswith('++'):
			title = line[2:-2]
			if title:
				if title[-1] not in '!?':
					title += '.'
				page.append(title)
		# handle indents
		elif line[0] == ':':
			page.append(line.lstrip(':'))
		# handle lists
		# @see https://www.mediawiki.org/wiki/Help:Formatting
		elif line[0] in '*#;':
			if Extractor.HtmlFormatting:
				# close extra levels
				l = 0
				for c in listLevel:
					if l < len(line) and c != line[l]:
						for extra in reversed(listLevel[l:]):
							page.append(listClose[extra])
						listLevel = listLevel[:l]
						break
					l += 1
				if l < len(line) and line[l] in '*#;:':
					# add new level (only one, no jumps)
					# FIXME: handle jumping levels
					type = line[l]
					page.append(listOpen[type])
					listLevel += type
					line = line[l+1:].strip()
				else:
					# continue on same level
					type = line[l-1]
					line = line[l:].strip()
				page.append(listItem[type] % line)
			else:
				continue
		elif len(listLevel):    # implies Extractor.HtmlFormatting
			for c in reversed(listLevel):
				page.append(listClose[c])
			listLevel = []
		# Drop residuals of lists
		elif line[0] in '{|' or line[-1] == '}':
			continue
		# Drop irrelevant lines
		elif (line[0] == '(' and line[-1] == ')') or line.strip('.-') == '':
			continue
		elif len(headers):
			if Extractor.keepSections:
				items = sorted(headers.items())
				for (i, v) in items:
					page.append(v)
			headers.clear()
			page.append(line)  # first line
			emptySection = False
		elif not emptySection:
			page.append(line)
			# dangerous
			# # Drop preformatted
			# elif line[0] == ' ':
			#     continue
	return page
# ----------------------------------------------------------------------
# External links
# from: https://doc.wikimedia.org/mediawiki-core/master/php/DefaultSettings_8php_source.html
wgUrlProtocols = [
	'bitcoin:', 'ftp://', 'ftps://', 'geo:', 'git://', 'gopher://', 'http://',
	'https://', 'irc://', 'ircs://', 'magnet:', 'mailto:', 'mms://', 'news:',
	'nntp://', 'redis://', 'sftp://', 'sip:', 'sips:', 'sms:', 'ssh://',
	'svn://', 'tel:', 'telnet://', 'urn:', 'worldwind://', 'xmpp:', '//'
]
# from: https://doc.wikimedia.org/mediawiki-core/master/php/Parser_8php_source.html
# Constants needed for external link processing
# Everything except bracket, space, or control characters
# \p{Zs} is unicode 'separator, space' category. It covers the space 0x20
# as well as U+3000 is IDEOGRAPHIC SPACE for bug 19052
EXT_LINK_URL_CLASS = r'[^][<>"\x00-\x20\x7F\s]'
ExtLinkBracketedRegex = re.compile(
	r'\[((' + 'r|'.join(wgUrlProtocols) + ')' + EXT_LINK_URL_CLASS + r'+)\s*([^\]\x00-\x08\x0a-\x1F]*?)\]',
	re.S | re.U | re.IGNORECASE)
EXT_IMAGE_REGEX = re.compile(
	r"""^(http://|https://)([^][<>"\x00-\x20\x7F\s]+)
	/([A-Za-z0-9_.,~%\-+&;#*?!=()@\x80-\xFF]+)\.(gif|png|jpg|jpeg)$""",
	re.X | re.S | re.U|re.IGNORECASE)
def replaceExternalLinks(text):
	s = ''
	cur = 0
	for m in ExtLinkBracketedRegex.finditer(text):
		s += text[cur:m.start()]
		cur = m.end()
		url = m.group(1)
		label = m.group(3)
		# # The characters '<' and '>' (which were escaped by
		# # removeHTMLtags()) should not be included in
		# # URLs, per RFC 2396.
		# m2 = re.search('&(lt|gt);', url)
		# if m2:
		#     link = url[m2.end():] + ' ' + link
		#     url = url[0:m2.end()]
		# If the link text is an image URL, replace it with an <img> tag
		# This happened by accident in the original parser, but some people used it extensively
		m = EXT_IMAGE_REGEX.match(label)
		if m:
			label = makeExternalImage(label)
		# Use the encoded URL
		# This means that users can paste URLs directly into the text
		# Funny characters like ö aren't valid in URLs anyway
		# This was changed in August 2004
		s += makeExternalLink(url, label)  # + trail
	return s + text[cur:]
def makeExternalLink(url, anchor):
	"""Function applied to wikiLinks"""
	if Extractor.keepLinks:
		return '<a href="%s">%s</a>' % (urlencode(url), anchor)
	else:
		return anchor
def makeExternalImage(url, alt=''):
	if Extractor.keepLinks:
		return '<img src="%s" alt="%s">' % (url, alt)
	else:
		return alt
# ----------------------------------------------------------------------
# WikiLinks
# See https://www.mediawiki.org/wiki/Help:Links#Internal_links
# Can be nested [[File:..|..[[..]]..|..]], [[Category:...]], etc.
# Also: [[Help:IPA for Catalan|[andora]]]
def replaceInternalLinks(text):
	"""
	Replaces external links of the form:
	[[title |...|label]]trail
	with title concatenated with trail, when present, e.g. 's' for plural.
	"""
	# call this after removal of external links, so we need not worry about
	# triple closing ]]].
	cur = 0
	res = ''
	for s, e in findBalanced(text, ['[['], [']]']):
		m = constents.tailRE.match(text, e)
		if m:
			trail = m.group(0)
			end = m.end()
		else:
			trail = ''
			end = e
		inner = text[s + 2:e - 2]
		# find first |
		pipe = inner.find('|')
		if pipe < 0:
			title = inner
			label = title
		else:
			title = inner[:pipe].rstrip()
			# find last |
			curp = pipe + 1
			for s1, e1 in findBalanced(inner, ['[['], [']]']):
				last = inner.rfind('|', curp, s1)
				if last >= 0:
					pipe = last  # advance
				curp = e1
			label = inner[pipe + 1:].strip()
		res += text[cur:s] + makeInternalLink(title, label) + trail
		cur = end
	return res + text[cur:]
def makeInternalLink(title, label):
	colon = title.find(':')
	if colon > 0 and title[:colon] not in constents.acceptedNamespaces:
		return ''
	if colon == 0:
		# drop also :File:
		colon2 = title.find(':', colon + 1)
		if colon2 > 1 and title[colon + 1:colon2] not in constents.acceptedNamespaces:
			return ''
	if Extractor.keepLinks:
		return '<a href="%s">%s</a>' % (urlencode(title), label)
	else:
		return label
# ----------------------------------------------------------------------
# variables
magicWordsRE = re.compile('|'.join(MagicWords.switches))
# =========================================================================
#
# MediaWiki Markup Grammar
# https://www.mediawiki.org/wiki/Preprocessor_ABNF
# xml-char = %x9 / %xA / %xD / %x20-D7FF / %xE000-FFFD / %x10000-10FFFF
# sptab = SP / HTAB
# ; everything except ">" (%x3E)
# attr-char = %x9 / %xA / %xD / %x20-3D / %x3F-D7FF / %xE000-FFFD / %x10000-10FFFF
# literal         = *xml-char
# title           = wikitext-L3
# part-name       = wikitext-L3
# part-value      = wikitext-L3
# part            = ( part-name "=" part-value ) / ( part-value )
# parts           = [ title *( "|" part ) ]
# tplarg          = "{{{" parts "}}}"
# template        = "{{" parts "}}"
# link            = "[[" wikitext-L3 "]]"
# comment         = "<!--" literal "-->"
# unclosed-comment = "<!--" literal END
# ; the + in the line-eating-comment rule was absent between MW 1.12 and MW 1.22
# line-eating-comment = LF LINE-START *SP +( comment *SP ) LINE-END
# attr            = *attr-char
# nowiki-element  = "<nowiki" attr ( "/>" / ( ">" literal ( "</nowiki>" / END ) ) )
# wikitext-L2     = heading / wikitext-L3 / *wikitext-L2
# wikitext-L3     = literal / template / tplarg / link / comment /
#                   line-eating-comment / unclosed-comment / xmlish-element /
#                   *wikitext-L3
# ------------------------------------------------------------------------------
selfClosingTags = ('br', 'hr', 'nobr', 'ref', 'references', 'nowiki')
# These tags are dropped, keeping their content.
# handle 'a' separately, depending on keepLinks
ignoredTags = (
	'abbr', 'b', 'big', 'blockquote', 'center', 'cite', 'div', 'em',
	'font', 'h1', 'h2', 'h3', 'h4', 'hiero', 'i', 'kbd', 'nowiki',
	'p', 'plaintext', 's', 'span', 'strike', 'strong',
	'sub', 'sup', 'tt', 'u', 'var'
)
placeholder_tags = {'math': 'formula', 'code': 'codice'}
# Match ignored tags
ignored_tag_patterns = []
def ignoreTag(tag):
	left = re.compile(r'<%s\b.*?>' % tag, re.IGNORECASE | re.DOTALL)  # both <ref> and <reference>
	right = re.compile(r'</\s*%s>' % tag, re.IGNORECASE)
	ignored_tag_patterns.append((left, right))
def resetIgnoredTags():
	global ignored_tag_patterns
	ignored_tag_patterns = []
for tag in ignoredTags:
	ignoreTag(tag)
# Match selfClosing HTML tags
selfClosing_tag_patterns = [
	re.compile(r'<\s*%s\b[^>]*/\s*>' % tag, re.DOTALL | re.IGNORECASE) for tag in selfClosingTags
]
# Match HTML placeholder tags
placeholder_tag_patterns = [
	(re.compile(r'<\s*%s(\s*| [^>]+?)>.*?<\s*/\s*%s\s*>' % (tag, tag), re.DOTALL | re.IGNORECASE),
	 repl) for tag, repl in placeholder_tags.items()
]
# Match preformatted lines
preformatted = re.compile(r'^ .*?$')
# Match external links (space separates second optional parameter)
externalLink = re.compile(r'\[\w+[^ ]*? (.*?)]')
externalLinkNoAnchor = re.compile(r'\[\w+[&\]]*\]')
# Matches bold/italic
bold_italic = re.compile(r"'''''(.*?)'''''")
bold = re.compile(r"'''(.*?)'''")
italic_quote = re.compile(r"''\"([^\"]*?)\"''")
italic = re.compile(r"''(.*?)''")
quote_quote = re.compile(r'""([^"]*?)""')
# Matches space
spaces = re.compile(r' {2,}')
# Matches dots
dots = re.compile(r'\.{4,}')
# ======================================================================
substWords = 'subst:|safesubst:'
class Extractor():
	"""
	An extraction task on a article.
	"""
	##
	# Whether to preserve links in output
	keepLinks = False
	##
	# Whether to preserve section titles
	keepSections = True
	##
	# Whether to output text with HTML formatting elements in <doc> files.
	HtmlFormatting = False
	##
	# Whether to produce json instead of the default <doc> output format.
	toJson = False
	##
	# Obtained from TemplateNamespace
	templatePrefix = ''
# ===========================================================================
	def __init__(self, id, revid, urlbase, title, page):
		"""
		:param page: a list of lines.
		"""
		self.id = id
		self.revid = revid
		self.url = get_url(urlbase, id)
		self.title = title
		self.page = page
		self.magicWords = MagicWords()
		self.frame = []
		self.recursion_exceeded_1_errs = 0  # template recursion within expandTemplates()
		self.recursion_exceeded_2_errs = 0  # template recursion within expandTemplate()
		self.recursion_exceeded_3_errs = 0  # parameter recursion
		self.template_title_errs = 0
	def clean_text(self, text, mark_headers=False, expand_templates=True,
				   html_safe=True):
		"""
		:param mark_headers: True to distinguish headers from paragraphs
		  e.g. "## Section 1"
		"""
		self.magicWords['namespace'] = self.title[:max(0, self.title.find(":"))]
		#self.magicWords['namespacenumber'] = '0' # for article, 
		self.magicWords['pagename'] = self.title
		self.magicWords['fullpagename'] = self.title
		self.magicWords['currentyear'] = time.strftime('%Y')
		self.magicWords['currentmonth'] = time.strftime('%m')
		self.magicWords['currentday'] = time.strftime('%d')
		self.magicWords['currenthour'] = time.strftime('%H')
		self.magicWords['currenttime'] = time.strftime('%H:%M:%S')
		text = clean(self, text, expand_templates=expand_templates,
					 html_safe=html_safe)
		text = compact(text, mark_headers=mark_headers)
		return text
	def extract(self, out, html_safe=True):
		"""
		:param out: a memory file.
		:param html_safe: whether to escape HTML entities.
		"""
		logging.debug("%s\t%s", self.id, self.title)
		text = ''.join(self.page)
		text = self.clean_text(text, html_safe=html_safe)
		if self.to_json:
			json_data = {
		'id': self.id,
				'revid': self.revid,
				'url': self.url,
				'title': self.title,
				'text': "\n".join(text)
			}
			out_str = json.dumps(json_data)
			out.write(out_str)
			out.write('\n')
		else:
			header = '<doc id="%s" url="%s" title="%s">\n' % (self.id, self.url, self.title)
			# Separate header from text with a newline.
			header += self.title + '\n\n'
			footer = "\n</doc>\n"
			out.write(header)
			out.write('\n'.join(text))
			out.write('\n')
			out.write(footer)
		errs = (self.template_title_errs,
				self.recursion_exceeded_1_errs,
				self.recursion_exceeded_2_errs,
				self.recursion_exceeded_3_errs)
		if any(errs):
			logging.warn("Template errors in article '%s' (%s): title(%d) recursion(%d, %d, %d)",
						 self.title, self.id, *errs)
	# ----------------------------------------------------------------------
	# Expand templates
	maxTemplateRecursionLevels = 30
	maxParameterRecursionLevels = 16
	# check for template beginning
	reOpen = re.compile('(?<!{){{(?!{)', re.DOTALL)
	def expandTemplates(self, wikitext):
		"""
		:param wikitext: the text to be expanded.
		Templates are frequently nested. Occasionally, parsing mistakes may
		cause template insertion to enter an infinite loop, for instance when
		trying to instantiate Template:Country
		{{country_{{{1}}}|{{{2}}}|{{{2}}}|size={{{size|}}}|name={{{name|}}}}}
		which is repeatedly trying to insert template 'country_', which is
		again resolved to Template:Country. The straightforward solution of
		keeping track of templates that were already inserted for the current
		article would not work, because the same template may legally be used
		more than once, with different parameters in different parts of the
		article.  Therefore, we limit the number of iterations of nested
		template inclusion.
		"""
		# Test template expansion at:
		# https://en.wikipedia.org/wiki/Special:ExpandTemplates
		res = ''
		if len(self.frame) >= self.maxTemplateRecursionLevels:
			self.recursion_exceeded_1_errs += 1
			return res
		# logging.debug('<expandTemplates ' + str(len(self.frame)))
		cur = 0
		# look for matching {{...}}
		for s, e in findMatchingBraces(wikitext, 2):
			res += wikitext[cur:s] + self.expandTemplate(wikitext[s + 2:e - 2])
			cur = e
		# leftover
		res += wikitext[cur:]
		# logging.debug('   expandTemplates> %d %s', len(self.frame), res)
		return res
	def templateParams(self, parameters):
		"""
		Build a dictionary with positional or name key to expanded parameters.
		:param parameters: the parts[1:] of a template, i.e. all except the title.
		"""
		templateParams = {}
		if not parameters:
			return templateParams
		logging.debug('<templateParams: %s', '|'.join(parameters))
		# Parameters can be either named or unnamed. In the latter case, their
		# name is defined by their ordinal position (1, 2, 3, ...).
		unnamedParameterCounter = 0
		# It's legal for unnamed parameters to be skipped, in which case they
		# will get default values (if available) during actual instantiation.
		# That is {{template_name|a||c}} means parameter 1 gets
		# the value 'a', parameter 2 value is not defined, and parameter 3 gets
		# the value 'c'.  This case is correctly handled by function 'split',
		# and does not require any special handling.
		for param in parameters:
			# Spaces before or after a parameter value are normally ignored,
			# UNLESS the parameter contains a link (to prevent possible gluing
			# the link to the following text after template substitution)
			# Parameter values may contain "=" symbols, hence the parameter
			# name extends up to the first such symbol.
			# It is legal for a parameter to be specified several times, in
			# which case the last assignment takes precedence. Example:
			# "{{t|a|b|c|2=B}}" is equivalent to "{{t|a|B|c}}".
			# Therefore, we don't check if the parameter has been assigned a
			# value before, because anyway the last assignment should override
			# any previous ones.
			# FIXME: Don't use DOTALL here since parameters may be tags with
			# attributes, e.g. <div class="templatequotecite">
			# Parameters may span several lines, like:
			# {{Reflist|colwidth=30em|refs=
			# &lt;ref name=&quot;Goode&quot;&gt;Title&lt;/ref&gt;
			# The '=' might occurr within an HTML attribute:
			#   "&lt;ref name=value"
			# but we stop at first.
			# The '=' might occurr within quotes:
			# ''''<span lang="pt-pt" xml:lang="pt-pt">cénicas</span>'''
			m = re.match(" *([^=']*?) *=(.*)", param, re.DOTALL)
			if m:
				# This is a named parameter.  This case also handles parameter
				# assignments like "2=xxx", where the number of an unnamed
				# parameter ("2") is specified explicitly - this is handled
				# transparently.
				parameterName = m.group(1).strip()
				parameterValue = m.group(2)
				if ']]' not in parameterValue:  # if the value does not contain a link, trim whitespace
					parameterValue = parameterValue.strip()
				templateParams[parameterName] = parameterValue
			else:
				# this is an unnamed parameter
				unnamedParameterCounter += 1
				if ']]' not in param:  # if the value does not contain a link, trim whitespace
					param = param.strip()
				templateParams[str(unnamedParameterCounter)] = param
		logging.debug('   templateParams> %s', '|'.join(templateParams.values()))
		return templateParams
	def expandTemplate(self, body):
		"""Expands template invocation.
		:param body: the parts of a template.
		:see http://meta.wikimedia.org/wiki/Help:Expansion for an explanation
		of the process.
		See in particular: Expansion of names and values
		http://meta.wikimedia.org/wiki/Help:Expansion#Expansion_of_names_and_values
		For most parser functions all names and values are expanded,
		regardless of what is relevant for the result. The branching functions
		(#if, #ifeq, #iferror, #ifexist, #ifexpr, #switch) are exceptions.
		All names in a template call are expanded, and the titles of the
		tplargs in the template body, after which it is determined which
		values must be expanded, and for which tplargs in the template body
		the first part (default).
		In the case of a tplarg, any parts beyond the first are never
		expanded.  The possible name and the value of the first part is
		expanded if the title does not match a name in the template call.
		:see code for braceSubstitution at
		https://doc.wikimedia.org/mediawiki-core/master/php/html/Parser_8php_source.html#3397:
		"""
		# template        = "{{" parts "}}"
		# Templates and tplargs are decomposed in the same way, with pipes as
		# separator, even though eventually any parts in a tplarg after the first
		# (the parameter default) are ignored, and an equals sign in the first
		# part is treated as plain text.
		# Pipes inside inner templates and tplargs, or inside double rectangular
		# brackets within the template or tplargs are not taken into account in
		# this decomposition.
		# The first part is called title, the other parts are simply called parts.
		# If a part has one or more equals signs in it, the first equals sign
		# determines the division into name = value. Equals signs inside inner
		# templates and tplargs, or inside double rectangular brackets within the
		# part are not taken into account in this decomposition. Parts without
		# equals sign are indexed 1, 2, .., given as attribute in the <name> tag.
		if len(self.frame) >= self.maxTemplateRecursionLevels:
			self.recursion_exceeded_2_errs += 1
			# logging.debug('   INVOCATION> %d %s', len(self.frame), body)
			return ''
		logging.debug('INVOCATION %d %s', len(self.frame), body)
		parts = splitParts(body)
		# title is the portion before the first |
		logging.debug('TITLE %s', parts[0].strip())
		title = self.expandTemplates(parts[0].strip())
		# SUBST
		# Apply the template tag to parameters without
		# substituting into them, e.g.
		# {{subst:t|a{{{p|q}}}b}} gives the wikitext start-a{{{p|q}}}b-end
		# @see https://www.mediawiki.org/wiki/Manual:Substitution#Partial_substitution
		subst = False
		if re.match(substWords, title, re.IGNORECASE):
			title = re.sub(substWords, '', title, 1, re.IGNORECASE)
			subst = True
		if title.lower() in self.magicWords.values:
			return self.magicWords[title.lower()]
		# Parser functions
		# The first argument is everything after the first colon.
		# It has been evaluated above.
		colon = title.find(':')
		if colon > 1:
			funct = title[:colon]
			parts[0] = title[colon + 1:].strip()  # side-effect (parts[0] not used later)
			# arguments after first are not evaluated
			ret = callParserFunction(funct, parts, self.frame)
			return self.expandTemplates(ret)
		title = fullyQualifiedTemplateTitle(title)
		if not title:
			self.template_title_errs += 1
			return ''
		redirected = constents.redirects.get(title)
		if redirected:
			title = redirected
		# get the template
		if title in constents.templateCache:
			template = constents.templateCache[title]
		elif title in constents.templates:
			template = Template.parse(constents.templates[title])
			# add it to cache
			constents.templateCache[title] = template
			del constents.templates[title]
		else:
			# The page being included could not be identified
			return ''
		# logging.debug('TEMPLATE %s: %s', title, template)
		# tplarg          = "{{{" parts "}}}"
		# parts           = [ title *( "|" part ) ]
		# part            = ( part-name "=" part-value ) / ( part-value )
		# part-name       = wikitext-L3
		# part-value      = wikitext-L3
		# wikitext-L3     = literal / template / tplarg / link / comment /
		#                   line-eating-comment / unclosed-comment /
		#           	    xmlish-element / *wikitext-L3
		# A tplarg may contain other parameters as well as templates, e.g.:
		#   {{{text|{{{quote|{{{1|{{error|Error: No text given}}}}}}}}}}}
		# hence no simple RE like this would work:
		#   '{{{((?:(?!{{{).)*?)}}}'
		# We must use full CF parsing.
		# the parameter name itself might be computed, e.g.:
		#   {{{appointe{{#if:{{{appointer14|}}}|r|d}}14|}}}
		# Because of the multiple uses of double-brace and triple-brace
		# syntax, expressions can sometimes be ambiguous.
		# Precedence rules specifed here:
		# http://www.mediawiki.org/wiki/Preprocessor_ABNF#Ideal_precedence
		# resolve ambiguities like this:
		#   {{{{ }}}} -> { {{{ }}} }
		#   {{{{{ }}}}} -> {{ {{{ }}} }}
		#
		# :see: https://en.wikipedia.org/wiki/Help:Template#Handling_parameters
		params = parts[1:]
		if not subst:
			# Evaluate parameters, since they may contain templates, including
			# the symbol "=".
			# {{#ifexpr: {{{1}}} = 1 }}
			params = [self.expandTemplates(p) for p in params]
		# build a dict of name-values for the parameter values
		params = self.templateParams(params)
		# Perform parameter substitution
		# extend frame before subst, since there may be recursion in default
		# parameter value, e.g. {{OTRS|celebrative|date=April 2015}} in article
		# 21637542 in enwiki.
		self.frame.append((title, params))
		instantiated = template.subst(params, self)
		# logging.debug('instantiated %d %s', len(self.frame), instantiated)
		value = self.expandTemplates(instantiated)
		self.frame.pop()
		# logging.debug('   INVOCATION> %s %d %s', title, len(self.frame), value)
		return value
def fullyQualifiedTemplateTitle(templateTitle):
	"""
	Determine the namespace of the page being included through the template
	mechanism
	"""
	if templateTitle.startswith(':'):
		# Leading colon by itself implies main namespace, so strip this colon
		return ucfirst(templateTitle[1:])
	else:
		m = re.match('([^:]*)(:.*)', templateTitle)
		if m:
			# colon found but not in the first position - check if it
			# designates a known namespace
			prefix = normalizeNamespace(m.group(1))
			if prefix in constents.knownNamespaces:
				return prefix + ucfirst(m.group(2))
	# The title of the page being included is NOT in the main namespace and
	# lacks any other explicit designation of the namespace - therefore, it
	# is resolved to the Template namespace (that's the default for the
	# template inclusion mechanism).
	# This is a defense against pages whose title only contains UTF-8 chars
	# that are reduced to an empty string. Right now I can think of one such
	# case - <C2><A0> which represents the non-breaking space.
	# In this particular case, this page is a redirect to [[Non-nreaking
	# space]], but having in the system a redirect page with an empty title
	# causes numerous problems, so we'll live happier without it.
	if templateTitle:
		return Extractor.templatePrefix + ucfirst(templateTitle)
	else:
		return ''  # caller may log as error
# ----------------------------------------------------------------------
# Parser functions
# see http://www.mediawiki.org/wiki/Help:Extension:ParserFunctions
# https://github.com/Wikia/app/blob/dev/extensions/ParserFunctions/ParserFunctions_body.php
ROUND = Infix(lambda x, y: round(x, y))
def sharp_ifeq(lvalue, rvalue, valueIfTrue, valueIfFalse=None, *args):
	rvalue = rvalue.strip()
	if rvalue:
		# lvalue is always defined
		if lvalue.strip() == rvalue:
			# The {{#ifeq:}} function is an if-then-else construct. The
			# applied condition is "is rvalue equal to lvalue". Note that this
			# does only string comparison while MediaWiki implementation also
			# supports numerical comparissons.
			if valueIfTrue:
				return valueIfTrue.strip()
		else:
			if valueIfFalse:
				return valueIfFalse.strip()
	return ""
def sharp_iferror(test, then='', Else=None, *args):
	if re.match('<(?:strong|span|p|div)\s(?:[^\s>]*\s+)*?class="(?:[^"\s>]*\s+)*?error(?:\s[^">]*)?"', test):
		return then
	elif Else is None:
		return test.strip()
	else:
		return Else.strip()
# Extension Scribuntu
def sharp_invoke(module, function, frame):
	functions = modules.get(module)
	if functions:
		funct = functions.get(function)
		if funct:
			# find parameters in frame whose title is the one of the original
			# template invocation
			templateTitle = fullyQualifiedTemplateTitle(function)
			if not templateTitle:
				logging.warn("Template with empty title")
			pair = next((x for x in frame if x[0] == templateTitle), None)
			if pair:
				params = pair[1]
				# extract positional args
				params = [params.get(str(i + 1)) for i in range(len(params))]
				return funct(*params)
			else:
				return funct()
	return ''
parserFunctions = {
	'#expr': sharp_expr,
	'#if': sharp_if,
	'#ifeq': sharp_ifeq,
	'#iferror': sharp_iferror,
	'#ifexpr': lambda *args: '',  # not supported
	'#ifexist': lambda *args: '',  # not supported
	'#rel2abs': lambda *args: '',  # not supported
	'#switch': sharp_switch,
	'# language': lambda *args: '',  # not supported
	'#time': lambda *args: '',  # not supported
	'#timel': lambda *args: '',  # not supported
	'#titleparts': lambda *args: '',  # not supported
	# This function is used in some pages to construct links
	# http://meta.wikimedia.org/wiki/Help:URL
	'urlencode': lambda string, *rest: urlencode(string),
	'lc': lambda string, *rest: string.lower() if string else '',
	'lcfirst': lambda string, *rest: lcfirst(string),
	'uc': lambda string, *rest: string.upper() if string else '',
	'ucfirst': lambda string, *rest: ucfirst(string),
	'int': lambda string, *rest: str(int(string)),
	'padleft': lambda char, pad, string: string.ljust(char, int(pad)), # CHECK_ME
}
def callParserFunction(functionName, args, frame):
	"""
	Parser functions have similar syntax as templates, except that
	the first argument is everything after the first colon.
	:param functionName: nameof the parser function
	:param args: the arguments to the function
	:return: the result of the invocation, None in case of failure.
	http://meta.wikimedia.org/wiki/Help:ParserFunctions
	"""
	try:
		if functionName == '#invoke':
			# special handling of frame
			ret = sharp_invoke(args[0].strip(), args[1].strip(), frame)
			# logging.debug('parserFunction> %s %s', args[1], ret)
			return ret
		if functionName in parserFunctions:
			ret = parserFunctions[functionName](*args)
			# logging.debug('parserFunction> %s(%s) %s', functionName, args, ret)
			return ret
	except:
		return ""  # FIXME: fix errors
	return ""
# ----------------------------------------------------------------------
def define_template(title, page):
	"""
	Adds a template defined in the :param page:.
	@see https://en.wikipedia.org/wiki/Help:Template#Noinclude.2C_includeonly.2C_and_onlyinclude
	"""
	# title = normalizeTitle(title)
	# check for redirects
	m = re.match('#REDIRECT.*?\[\[([^\]]*)]]', page[0], re.IGNORECASE)
	if m:
		constents.redirects[title] = m.group(1)  # normalizeTitle(m.group(1))
		return
	text = unescape(''.join(page))
	# We're storing template text for future inclusion, therefore,
	# remove all <noinclude> text and keep all <includeonly> text
	# (but eliminate <includeonly> tags per se).
	# However, if <onlyinclude> ... </onlyinclude> parts are present,
	# then only keep them and discard the rest of the template body.
	# This is because using <onlyinclude> on a text fragment is
	# equivalent to enclosing it in <includeonly> tags **AND**
	# enclosing all the rest of the template body in <noinclude> tags.
	# remove comments
	text = constents.comment.sub('', text)
	# eliminate <noinclude> fragments
	text = constents.reNoinclude.sub('', text)
	# eliminate unterminated <noinclude> elements
	text = re.sub(r'<noinclude\s*>.*$', '', text, flags=re.DOTALL)
	text = re.sub(r'<noinclude/>', '', text)
	onlyincludeAccumulator = ''
	for m in re.finditer('<onlyinclude>(.*?)</onlyinclude>', text, re.DOTALL):
		onlyincludeAccumulator += m.group(1)
	if onlyincludeAccumulator:
		text = onlyincludeAccumulator
	else:
		text = constents.reIncludeonly.sub('', text)
	if text:
		if title in constents.templates and constents.templates[title] != text:
			logging.warn('Redefining: %s', title)
		constents.templates[title] = text
