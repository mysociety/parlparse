#!/usr/bin/python2.6

import codecs
import sys
import re
import os

for f in sys.argv[1:]:

    backup = f + ".bak"

    fp = codecs.open( f, "r", "utf-8" )
    xml_text = fp.read()
    fp.close()

    xml_text = re.sub('(?s)[ \t\r\n]+<','<',xml_text)
    xml_text = re.sub('(?s)>[ \t\r\n]+','>',xml_text)

    fp = codecs.open( backup, "w", "utf-8" )
    fp.write( xml_text )
    fp.close()

    os.rename(backup,f)