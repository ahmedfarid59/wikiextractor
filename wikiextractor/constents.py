# Program version
__version__ = '3.0.7'
import re


urlbase = ''                # This is obtained from <siteinfo>
##
# Recognize only these namespaces
# w: Internal links to the Wikipedia
# wiktionary: Wiki dictionary
# wikt: shortcut for Wiktionary
#
acceptedNamespaces = ['w', 'wiktionary', 'wikt']
# ----------------------------------------------------------------------
# Modules

# Only minimal support
# FIXME: import Lua modules.

modules = {
	'convert': {
		'convert': lambda x, u, *rest: x + ' ' + u,  # no conversion
	}
}

# ----------------------------------------------------------------------



# match tail after wikilink
tailRE = re.compile('\w+')
syntaxhighlight = re.compile('&lt;syntaxhighlight .*?&gt;(.*?)&lt;/syntaxhighlight&gt;', re.DOTALL)

## PARAMS ####################################################################

##
# Drop these elements from article text
#
discardElements = [
	'gallery', 'timeline', 'noinclude', 'pre',
	'table', 'tr', 'td', 'th', 'caption', 'div',
	'form', 'input', 'select', 'option', 'textarea',
	'ul', 'li', 'ol', 'dl', 'dt', 'dd', 'menu', 'dir',
	'ref', 'references', 'img', 'imagemap', 'source', 'small'
]

# ======================================================================
# Extract Template definition

reNoinclude = re.compile(r'<noinclude>(?:.*?)</noinclude>', re.DOTALL)
reIncludeonly = re.compile(r'<includeonly>|</includeonly>', re.DOTALL)

# These are built before spawning processes, hence they are shared.
templates = {}
redirects = {}
# cache of parser templates
# FIXME: sharing this with a Manager slows down.
templateCache = {}







# READER

tagRE = re.compile(r'(.*?)<(/?\w+)[^>]*>(?:([^<]*)(<.*?>)?)?')
#                    1     2               3      4
##
# The namespace used for template definitions
# It is the name associated with namespace key=10 in the siteinfo header.
templateNamespace = ''



##
# Defined in <siteinfo>
# We include as default Template, when loading external template file.
knownNamespaces = set(['Template'])


##
# The namespace used for module definitions
# It is the name associated with namespace key=828 in the siteinfo header.
moduleNamespace = ''

modulePrefix = moduleNamespace + ':'
# Match HTML comments
# The buggy template {{Template:T}} has a comment terminating with just "->"
comment = re.compile(r'<!--.*?-->', re.DOTALL)

# Minimum size of output files
minFileSize = 200 * 1024
