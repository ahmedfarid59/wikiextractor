import logging

from wikiextractor.utilities import findMatchingBraces, splitParts

class Template(list):
	"""
	A Template is a list of TemplateText or TemplateArgs
	"""

	@classmethod
	def parse(cls, body):
		tpl = Template()
		# we must handle nesting, s.a.
		# {{{1|{{PAGENAME}}}
		# {{{italics|{{{italic|}}}
		# {{#if:{{{{{#if:{{{nominee|}}}|nominee|candidate}}|}}}|
		#
		start = 0
		for s,e in findMatchingBraces(body, 3):
			tpl.append(TemplateText(body[start:s]))
			tpl.append(TemplateArg(body[s+3:e-3]))
			start = e
		tpl.append(TemplateText(body[start:])) # leftover
		return tpl

	def subst(self, params, extractor, depth=0):
		# We perform parameter substitutions recursively.
		# We also limit the maximum number of iterations to avoid too long or
		# even endless loops (in case of malformed input).

		# :see: http://meta.wikimedia.org/wiki/Help:Expansion#Distinction_between_variables.2C_parser_functions.2C_and_templates
		#
		# Parameter values are assigned to parameters in two (?) passes.
		# Therefore a parameter name in a template can depend on the value of
		# another parameter of the same template, regardless of the order in
		# which they are specified in the template call, for example, using
		# Template:ppp containing "{{{{{{p}}}}}}", {{ppp|p=q|q=r}} and even
		# {{ppp|q=r|p=q}} gives r, but using Template:tvvv containing
		# "{{{{{{{{{p}}}}}}}}}", {{tvvv|p=q|q=r|r=s}} gives s.

		logging.debug('subst tpl (%d, %d) %s', len(extractor.frame), depth, self)

		if depth > extractor.maxParameterRecursionLevels:
			extractor.recursion_exceeded_3_errs += 1
			return ''

		return ''.join([tpl.subst(params, extractor, depth) for tpl in self])

	def __str__(self):
		return ''.join([str(x) for x in self])


class TemplateArg():
	"""
	parameter to a template.
	Has a name and a default value, both of which are Templates.
	"""
	def __init__(self, parameter):
		"""
		:param parameter: the parts of a tplarg.
		"""
		# the parameter name itself might contain templates, e.g.:
		#   appointe{{#if:{{{appointer14|}}}|r|d}}14|
		#   4|{{{{{subst|}}}CURRENTYEAR}}

		# any parts in a tplarg after the first (the parameter default) are
		# ignored, and an equals sign in the first part is treated as plain text.
		#logging.debug('TemplateArg %s', parameter)

		parts = splitParts(parameter)
		self.name = Template.parse(parts[0])
		if len(parts) > 1:
			# This parameter has a default value
			self.default = Template.parse(parts[1])
		else:
			self.default = None

	def __str__(self):
		if self.default:
			return '{{{%s|%s}}}' % (self.name, self.default)
		else:
			return '{{{%s}}}' % self.name

	def subst(self, params, extractor, depth):
		"""
		Substitute value for this argument from dict :param params:
		Use :param extractor: to evaluate expressions for name and default.
		Limit substitution to the maximun :param depth:.
		"""
		# the parameter name itself might contain templates, e.g.:
		# appointe{{#if:{{{appointer14|}}}|r|d}}14|
		paramName = self.name.subst(params, extractor, depth+1)
		paramName = extractor.expandTemplates(paramName)
		res = ''
		if paramName in params:
			res = params[paramName]  # use parameter value specified in template invocation
		elif self.default:            # use the default value
			defaultValue = self.default.subst(params, extractor, depth+1)
			res =  extractor.expandTemplates(defaultValue)
		#logging.debug('subst arg %d %s -> %s' % (depth, paramName, res))
		return res

# ======================================================================

class TemplateText(str):
	"""Fixed text of template"""

	def subst(self, params, extractor, depth):
		return self

