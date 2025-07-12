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
