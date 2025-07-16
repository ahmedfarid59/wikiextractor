@echo off

python -m wikiextractor.main ^
 arwiki-latest-pages-articles.xml.bz2 ^
       --json ^
       --processes 10 ^
       --templates  templates ^
       --output arwiki-latest-pages-articles ^
       --bytes 0
       
