from html.entities import name2codepoint
import bz2
import logging
import os
import re

from wikiextractor import constents


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

def get_url(urlbase, uid):
	return "%s?curid=%s" % (urlbase, uid)

def dropNested(text, openDelim, closeDelim):
	"""
	A matching function for nested expressions, e.g. namespaces and tables.
	"""
	openRE = re.compile(openDelim, re.IGNORECASE)
	closeRE = re.compile(closeDelim, re.IGNORECASE)
	# partition text in separate blocks { } { }
	spans = []  # pairs (s, e) for each partition
	nest = 0  # nesting level
	start = openRE.search(text, 0)
	if not start:
		return text
	end = closeRE.search(text, start.end())
	next = start
	while end:
		next = openRE.search(text, next.end())
		if not next:  # termination
			while nest:  # close all pending
				nest -= 1
				end0 = closeRE.search(text, end.end())
				if end0:
					end = end0
				else:
					break
			spans.append((start.start(), end.end()))
			break
		while end.end() < next.start():
			# { } {
			if nest:
				nest -= 1
				# try closing more
				last = end.end()
				end = closeRE.search(text, end.end())
				if not end:  # unbalanced
					if spans:
						span = (spans[0][0], last)
					else:
						span = (start.start(), last)
					spans = [span]
					break
			else:
				spans.append((start.start(), end.end()))
				# advance start, find next close
				start = next
				end = closeRE.search(text, next.end())
				break  # { }
		if next != start:
			# { { }
			nest += 1
	# collect text outside partitions
	return dropSpans(spans, text)


def dropSpans(spans, text):
	"""
	Drop from text the blocks identified in :param spans:, possibly nested.
	"""
	spans.sort()
	res = ''
	offset = 0
	for s, e in spans:
		if offset <= s:  # handle nesting
			if offset < s:
				res += text[offset:s]
			offset = e
	res += text[offset:]
	return res


# ----------------------------------------------------------------------
def sharp_switch(primary, *params):
	# FIXME: we don't support numeric expressions in primary
	# {{#switch: comparison string
	#  | case1 = result1
	#  | case2
	#  | case4 = result2
	#  | 1 | case5 = result3
	#  | #default = result4
	# }}

	primary = primary.strip()
	found = False  # for fall through cases
	default = None
	rvalue = None
	lvalue = ''
	for param in params:
		# handle cases like:
		#  #default = [http://www.perseus.tufts.edu/hopper/text?doc=Perseus...]
		pair = param.split('=', 1)
		lvalue = pair[0].strip()
		rvalue = None
		if len(pair) > 1:
			# got "="
			rvalue = pair[1].strip()
			# check for any of multiple values pipe separated
			if found or primary in [v.strip() for v in lvalue.split('|')]:
				# Found a match, return now
				return rvalue
			elif lvalue == '#default':
				default = rvalue
			rvalue = None  # avoid defaulting to last case
		elif lvalue == primary:
			# If the value matches, set a flag and continue
			found = True
	# Default case
	# Check if the last item had no = sign, thus specifying the default case
	if rvalue is not None:
		return lvalue
	elif default is not None:
		return default
	return ''

def findMatchingBraces(text, ldelim=0):
	"""
	:param ldelim: number of braces to match. 0 means match [[]], {{}} and {{{}}}.
	"""
	# Parsing is done with respect to pairs of double braces {{..}} delimiting
	# a template, and pairs of triple braces {{{..}}} delimiting a tplarg.
	# If double opening braces are followed by triple closing braces or
	# conversely, this is taken as delimiting a template, with one left-over
	# brace outside it, taken as plain text. For any pattern of braces this
	# defines a set of templates and tplargs such that any two are either
	# separate or nested (not overlapping).
	# Unmatched double rectangular closing brackets can be in a template or
	# tplarg, but unmatched double rectangular opening brackets cannot.
	# Unmatched double or triple closing braces inside a pair of
	# double rectangular brackets are treated as plain text.
	# Other formulation: in ambiguity between template or tplarg on one hand,
	# and a link on the other hand, the structure with the rightmost opening
	# takes precedence, even if this is the opening of a link without any
	# closing, so not producing an actual link.

	# In the case of more than three opening braces the last three are assumed
	# to belong to a tplarg, unless there is no matching triple of closing
	# braces, in which case the last two opening braces are are assumed to
	# belong to a template.

	# We must skip individual { like in:
	#   {{#ifeq: {{padleft:|1|}} | { | | &nbsp;}}
	# We must resolve ambiguities like this:
	#   {{{{ }}}} -> { {{{ }}} }
	#   {{{{{ }}}}} -> {{ {{{ }}} }}
	#   {{#if:{{{{{#if:{{{nominee|}}}|nominee|candidate}}|}}}|...}}
	# Handle:
	#   {{{{{|safesubst:}}}#Invoke:String|replace|{{{1|{{{{{|safesubst:}}}PAGENAME}}}}}|%s+%([^%(]-%)$||plain=false}}
	# as well as expressions with stray }:
	#   {{{link|{{ucfirst:{{{1}}}}}} interchange}}}

	if ldelim:  # 2-3
		reOpen = re.compile('[{]{%d,}' % ldelim)  # at least ldelim
		reNext = re.compile('[{]{2,}|}{2,}')  # at least 2 open or close bracces
	else:
		reOpen = re.compile('{{2,}|\[{2,}')
		reNext = re.compile('{{2,}|}{2,}|\[{2,}|]{2,}')  # at least 2

	cur = 0
	while True:
		m1 = reOpen.search(text, cur)
		if not m1:
			return
		lmatch = m1.end() - m1.start()
		if m1.group()[0] == '{':
			stack = [lmatch]  # stack of opening braces lengths
		else:
			stack = [-lmatch]  # negative means [
		end = m1.end()
		while True:
			m2 = reNext.search(text, end)
			if not m2:
				return  # unbalanced
			end = m2.end()
			brac = m2.group()[0]
			lmatch = m2.end() - m2.start()

			if brac == '{':
				stack.append(lmatch)
			elif brac == '}':
				while stack:
					openCount = stack.pop()  # opening span
					if openCount == 0:  # illegal unmatched [[
						continue
					if lmatch >= openCount:
						lmatch -= openCount
						if lmatch <= 1:  # either close or stray }
							break
					else:
						# put back unmatched
						stack.append(openCount - lmatch)
						break
				if not stack:
					yield m1.start(), end - lmatch
					cur = end
					break
				elif len(stack) == 1 and 0 < stack[0] < ldelim:
					# ambiguous {{{{{ }}} }}
					yield m1.start() + stack[0], end
					cur = end
					break
			elif brac == '[':  # [[
				stack.append(-lmatch)
			else:  # ]]
				while stack and stack[-1] < 0:  # matching [[
					openCount = -stack.pop()
					if lmatch >= openCount:
						lmatch -= openCount
						if lmatch <= 1:  # either close or stray ]
							break
					else:
						# put back unmatched (negative)
						stack.append(lmatch - openCount)
						break
				if not stack:
					yield m1.start(), end - lmatch
					cur = end
					break
				# unmatched ]] are discarded
				cur = end
# ----------------------------------------------------------------------
# parameter handling

def splitParts(paramsList):
	"""
	:param paramsList: the parts of a template or tplarg.

	Split template parameters at the separator "|".
	separator "=".

	Template parameters often contain URLs, internal links, text or even
	template expressions, since we evaluate templates outside in.
	This is required for cases like:
	  {{#if: {{{1}}} | {{lc:{{{1}}} | "parameter missing"}}
	Parameters are separated by "|" symbols. However, we
	cannot simply split the string on "|" symbols, since these
	also appear inside templates and internal links, e.g.

	 {{if:|
	  |{{#if:the president|
		   |{{#if:|
			   [[Category:Hatnote templates|A{{PAGENAME}}]]
			}}
	   }}
	 }}

	We split parts at the "|" symbols that are not inside any pair
	{{{...}}}, {{...}}, [[...]], {|...|}.
	"""

	# Must consider '[' as normal in expansion of Template:EMedicine2:
	# #ifeq: ped|article|[http://emedicine.medscape.com/article/180-overview|[http://www.emedicine.com/ped/topic180.htm#{{#if: |section~}}
	# as part of:
	# {{#ifeq: ped|article|[http://emedicine.medscape.com/article/180-overview|[http://www.emedicine.com/ped/topic180.htm#{{#if: |section~}}}} ped/180{{#if: |~}}]

	# should handle both tpl arg like:
	#    4|{{{{{subst|}}}CURRENTYEAR}}
	# and tpl parameters like:
	#    ||[[Category:People|{{#if:A|A|{{PAGENAME}}}}]]

	sep = '|'
	parameters = []
	cur = 0
	for s, e in findMatchingBraces(paramsList):
		par = paramsList[cur:s].split(sep)
		if par:
			if parameters:
				# portion before | belongs to previous parameter
				parameters[-1] += par[0]
				if len(par) > 1:
					# rest are new parameters
					parameters.extend(par[1:])
			else:
				parameters = par
		elif not parameters:
			parameters = ['']  # create first param
		# add span to last previous parameter
		parameters[-1] += paramsList[s:e]
		cur = e
	# leftover
	par = paramsList[cur:].split(sep)
	if par:
		if parameters:
			# portion before | belongs to previous parameter
			parameters[-1] += par[0]
			if len(par) > 1:
				# rest are new parameters
				parameters.extend(par[1:])
		else:
			parameters = par

	# logging.debug('splitParts %s %s\nparams: %s', sep, paramsList, str(parameters))
	return parameters



def sharp_expr(expr):
	try:
		expr = re.sub('=', '==', expr)
		expr = re.sub('mod', '%', expr)
		expr = re.sub('\bdiv\b', '/', expr)
		expr = re.sub('\bround\b', '|ROUND|', expr)
		return str(eval(expr))
	except:
		return '<span class="error"></span>'


def sharp_if(testValue, valueIfTrue, valueIfFalse=None, *args):
	# In theory, we should evaluate the first argument here,
	# but it was evaluated while evaluating part[0] in expandTemplate().
	if testValue.strip():
		# The {{#if:}} function is an if-then-else construct.
		# The applied condition is: "The condition string is non-empty".
		valueIfTrue = valueIfTrue.strip()
		if valueIfTrue:
			return valueIfTrue
	elif valueIfFalse:
		return valueIfFalse.strip()
	return ""

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

def unescape(text):
	"""
	Removes HTML or XML character references and entities from a text string.

	:param text The HTML (or XML) source text.
	:return The plain text, as a Unicode string, if necessary.
	"""

	def fixup(m):
		text = m.group(0)
		code = m.group(1)
		try:
			if text[1] == "#":  # character reference
				if text[2] == "x":
					return chr(int(code[1:], 16))
				else:
					return chr(int(code))
			else:  # named entity
				return chr(name2codepoint[code])
		except:
			return text  # leave as is

	return re.sub("&#?(\w+);", fixup, text)

def findBalanced(text, openDelim, closeDelim):
	"""
	Assuming that text contains a properly balanced expression using
	:param openDelim: as opening delimiters and
	:param closeDelim: as closing delimiters.
	:return: an iterator producing pairs (start, end) of start and end
	positions in text containing a balanced expression.
	"""
	openPat = '|'.join([re.escape(x) for x in openDelim])
	# patter for delimiters expected after each opening delimiter
	afterPat = {o: re.compile(openPat + '|' + c, re.DOTALL) for o, c in zip(openDelim, closeDelim)}
	stack = []
	start = 0
	cur = 0
	# end = len(text)
	startSet = False
	startPat = re.compile(openPat)
	nextPat = startPat
	while True:
		next = nextPat.search(text, cur)
		if not next:
			return
		if not startSet:
			start = next.start()
			startSet = True
		delim = next.group(0)
		if delim in openDelim:
			stack.append(delim)
			nextPat = afterPat[delim]
		else:
			opening = stack.pop()
			# assert opening == openDelim[closeDelim.index(next.group(0))]
			if stack:
				nextPat = afterPat[stack[-1]]
			else:
				yield start, next.end()
				nextPat = startPat
				start = next.end()
				startSet = False
		cur = next.end()

# ----------------------------------------------------------------------
# parser functions utilities


def ucfirst(string):
	""":return: a string with just its first character uppercase
	We can't use title() since it coverts all words.
	"""
	if string:
		if len(string) > 1:
			return string[0].upper() + string[1:]
		else:
			return string.upper()
	else:
		return ''

def lcfirst(string):
	""":return: a string with its first character lowercase"""
	if string:
		if len(string) > 1:
			return string[0].lower() + string[1:]
		else:
			return string.lower()
	else:
		return ''

def normalizeTitle(title):
	"""Normalize title"""
	# remove leading/trailing whitespace and underscores
	title = title.strip(' _')
	# replace sequences of whitespace and underscore chars with a single space
	title = re.sub(r'[\s_]+', ' ', title)

	m = re.match(r'([^:]*):(\s*)(\S(?:.*))', title)
	if m:
		prefix = m.group(1)
		if m.group(2):
			optionalWhitespace = ' '
		else:
			optionalWhitespace = ''
		rest = m.group(3)

		ns = normalizeNamespace(prefix)
		if ns in constents.knownNamespaces:
			# If the prefix designates a known namespace, then it might be
			# followed by optional whitespace that should be removed to get
			# the canonical page name
			# (e.g., "Category:  Births" should become "Category:Births").
			title = ns + ":" + ucfirst(rest)
		else:
			# No namespace, just capitalize first letter.
			# If the part before the colon is not a known namespace, then we
			# must not remove the space after the colon (if any), e.g.,
			# "3001: The_Final_Odyssey" != "3001:The_Final_Odyssey".
			# However, to get the canonical page name we must contract multiple
			# spaces into one, because
			# "3001:   The_Final_Odyssey" != "3001: The_Final_Odyssey".
			title = ucfirst(prefix) + ":" + optionalWhitespace + ucfirst(rest)
	else:
		# no namespace, just capitalize first letter
		title = ucfirst(title)
	return title

def normalizeNamespace(ns):
	return ucfirst(ns)
