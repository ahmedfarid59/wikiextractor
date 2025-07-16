@echo off

python -m wikiextractor.main ^
 arwiki-latest-pages-articles.xml.bz2 ^
       --json ^
       --processes 1 ^
       --templates  templates ^
       --output arwiki-latest-pages-articles ^
       --bytes 10M ^
       
