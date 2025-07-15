#!/bin/bash
#
# NOTES
#
# - Must expand templates to avoid a large loss of content.
# - Text will not (redundantly) contain the title string.
# - Keep sections. Section title will be marked by "Section::::".
# - Keep lists. List bullets will be marked by "BULLET::::".
# - Keep tables. They're mostly garbage but can be removed later (remove "^!*").
# - Remove disambiguation pages. Right now there is no use for them.

python3 -m wikiextractor.main \
 arwiki-latest-pages-articles.xml.bz2 \
       --json \
       --processes 9 \
       --templates  templates \
       --output arwiki-latest-pages-articles \
       --bytes 0 \
       --links 
