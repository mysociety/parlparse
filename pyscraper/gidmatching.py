import sys
import re
import os
import xml.sax
import tempfile
import string
import miscfuncs

from xmlfilewrite import PrevParsedFile

toppath = miscfuncs.toppath
pwxmldirs = miscfuncs.pwxmldirs
tempfilename = miscfuncs.tempfilename

from miscfuncs import NextAlphaString, AlphaStringToOrder


def RunGidMatching(dname):
	daymap = { }
	pwxmldir = os.path.join(pwxmldirs, dname)

	for xfile in os.listdir(pwxmldir):
		mnums = re.search("(\d{4}-\d\d-\d\d)([a-z]*)\.xml", xfile)
		if mnums:
			daymap.setdefault(mnums.group(1), []).append((AlphaStringToOrder(mnums.group(2)), mnums.group(2), xfile))

	sdates = daymap.keys()
	sdates.sort()
	sdates.reverse()
	for sdate in sdates:
		lsfiles = daymap[sdate]
		lsfiles.sort()
		if len(lsfiles) == 1:
			continue
		filelatest = lsfiles[-1][2]
		ppflatest = PrevParsedFile(os.path.join(pwxmldir, filelatest))
		for lsfile in lsfiles[:-1]:
			ppf = PrevParsedFile(os.path.join(pwxmldir, lsfile[2]))
			print "Matching from", lsfile[2], "to", filelatest


