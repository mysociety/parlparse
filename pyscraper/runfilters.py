#! /usr/bin/python2.3
# vim:sw=8:ts=8:et:nowrap

import sys
import re
import os
import string
import cStringIO
import tempfile
import time
import shutil

import xml.sax
xmlvalidate = xml.sax.make_parser()

from filterwranscolnum import FilterWransColnum
from filterwransspeakers import FilterWransSpeakers
from filterwranssections import FilterWransSections

from filterwmscolnum import FilterWMSColnum
from filterwmsspeakers import FilterWMSSpeakers
from filterwmssections import FilterWMSSections

from filterdebatecoltime import FilterDebateColTime
from filterdebatespeakers import FilterDebateSpeakers
from filterdebatesections import FilterDebateSections

from lordsfiltercoltime import SplitLordsText
from lordsfiltercoltime import FilterLordsColtime
from lordsfilterspeakers import LordsFilterSpeakers
from lordsfiltersections import LordsFilterSections

from contextexception import ContextException
from patchtool import RunPatchTool

from xmlfilewrite import CreateGIDs, CreateWransGIDs, WriteXMLHeader, WriteXMLspeechrecord
from gidmatching import FactorChanges

from resolvemembernames import memberList

import miscfuncs
from miscfuncs import AlphaStringToOrder


toppath = miscfuncs.toppath
pwcmdirs = miscfuncs.pwcmdirs
pwxmldirs = miscfuncs.pwxmldirs
pwpatchesdirs = miscfuncs.pwpatchesdirs


# master function which carries the glued pages into the xml filtered pages

# outgoing directory of scaped pages directories
# file to store list of newly done dates
changedatesfile = "changedates.txt"

tempfilename = tempfile.mktemp(".xml", "pw-filtertemp-", miscfuncs.tmppath)

# create the output directory
if not os.path.isdir(pwxmldirs):
	os.mkdir(pwxmldirs)



def ApplyPatches(filein, fileout, patchfile):
        while True:
                # Apply the patch
                shutil.copyfile(filein, fileout)

                # delete temporary file that might have been created by a previous patch failure
                filoutorg = fileout + ".orig"
                if os.path.isfile(filoutorg):
                    os.remove(filoutorg)
                status = os.system("patch --quiet %s <%s" % (fileout, patchfile))

                if status == 0:
                        return True

                print "blanking out failed patch %s" % patchfile
                os.rename(patchfile, patchfile + ".old~")
                blankfile = open(patchfile, "w")
                blankfile.close()


# the operation on a single file
def RunFilterFile(FILTERfunction, xprev, sdate, sdatever, dname, jfin, patchfile, jfout, forcereparse, bquietc):

	# now apply patches and parse
	patchtempfilename = tempfile.mktemp("", "pw-applypatchtemp-", miscfuncs.tmppath)

	print "reading " + jfin
	# apply patch filter
	kfin = jfin
	if os.path.isfile(patchfile) and ApplyPatches(jfin, patchtempfilename, patchfile):
		kfin = patchtempfilename

	# read the text of the file
	ofin = open(kfin)
	text = ofin.read()
	ofin.close()

	# do the filtering according to the type.  Some stuff is being inlined here
	if dname == 'regmem':
		regmemout = open(tempfilename, 'w')
		FILTERfunction(regmemout, text, sdate)  # totally different filter function format
		regmemout.close()

	# wrans case has very special numbering which is stable, so doesn't do backwards matching
	elif dname == 'wrans':
		(flatb, gidname) = FILTERfunction(text, sdate)  # gidname is prefix in the gid "debates", "lords", etc; should be a map or the same thing
		CreateGIDs(gidname, sdate, sdatever, flatb)
		majblocks = CreateWransGIDs(flatb, sdate)
		bMakeOldWransGidsToNew = (sdate < "2005")

		fout = open(tempfilename, "w")
		WriteXMLHeader(fout);
		fout.write("<publicwhip>\n")

		# go through and output all the records into the file
		for majblock in majblocks:
			WriteXMLspeechrecord(fout, majblock[0], bMakeOldWransGidsToNew, True)
			for qblock in majblock[1]:
				qblock.WriteXMLrecords(fout, bMakeOldWransGidsToNew)

		fout.write("</publicwhip>\n\n")
		fout.close()

	# all other hansard types
	else:
		(flatb, gidname) = FILTERfunction(text, sdate)
		CreateGIDs(gidname, sdate, sdatever, flatb)

		fout = open(tempfilename, "w")
		WriteXMLHeader(fout);
		fout.write("<publicwhip>\n")

		# go through and output all the records into the file
		fout.write('<scrapeversion code="%s">\n' % sdatever)
		for qb in flatb:
			WriteXMLspeechrecord(fout, qb, False, False)
		fout.write('</scrapeversion>\n')

		# load in a previous file
		if xprev:
			xin = open(xprev[0], "r")
			xprevs = xin.read()
			xin.close()

			# separate out the scrape versions
			scrapeversions = re.findall('<scrapeversion code="([^"]*)">\n([\s\S]*?)</scrapeversion>', xprevs)
			assert scrapeversions[0][0] == xprev[1]
			xprevcompress = FactorChanges(flatb, scrapeversions[0][1])

			fout.write('\n\n<scrapeversion code="%s">\n' % xprev[1])
			fout.writelines(xprevcompress)
			fout.write('</scrapeversion>\n')

			# write out the earlier consolidated files
			for scrapeversion in scrapeversions[1:]:
				fout.write('\n\n<scrapeversion code="%s">\n' % scrapeversion[0])
				fout.write(scrapeversion[1])
				fout.write('</scrapeversion>\n')

		fout.write("</publicwhip>\n\n")
		fout.close()

	# in win32 this function leaves the file open and stops it being renamed
	if sys.platform != "win32":
		xmlvalidate.parse(tempfilename) # validate XML before renaming

	# in case of error, an exception is thrown, so this line would not be reached
	if os.path.isfile(jfout):
		os.remove(jfout)
	os.rename(tempfilename, jfout)

# hunt the patchfile
def findpatchfile(name, d1, d2):
        patchfile = os.path.join(d1, "%s.patch" % name)
        if not os.path.isfile(patchfile):
                patchfile = os.path.join(d2, "%s.patch" % name)
        return patchfile

# this works on triplets of directories all called dname
def RunFiltersDir(FILTERfunction, dname, options, forcereparse):
	# the in and out directories for the type
	pwcmdirin = os.path.join(pwcmdirs, dname)
	pwxmldirout = os.path.join(pwxmldirs, dname)
        # mirgating to patches files stored in parldata, rather than in parlparse
	pwpatchesdir = os.path.join(pwpatchesdirs, dname)
	newpwpatchesdir = os.path.join(toppath, "patches", dname)

	# create output directory
	if not os.path.isdir(pwxmldirout):
		os.mkdir(pwxmldirout)

	# build up the groups of html files per day
	# scan through the directory and make a mapping of all the copies for each
	daymap = { }
	for ldfile in os.listdir(pwcmdirin):
		mnums = re.match("[a-z]*(\d{4}-\d\d-\d\d)([a-z]*)\.html$", ldfile)
		if mnums:
			daymap.setdefault(mnums.group(1), []).append((AlphaStringToOrder(mnums.group(2)), mnums.group(2), ldfile))
		elif ldfile != '.svn':
			print "not recognized file:", ldfile

	# make the list of days which we will iterate through (in revers date order)
	daydates = daymap.keys()
	daydates.sort()
	daydates.reverse()

	# loop through file in input directory in reverse date order and build up the
	for sdate in daydates:
		# skip dates outside the range specified on the command line
		if sdate < options.datefrom or sdate > options.dateto:
			continue

		fdaycs = daymap[sdate]
		fdaycs.sort()

		# now we parse these files -- in order -- to accumulate their catalogue of diffs
		xprev = None # previous xml file from which we check against diffs, and its version string
		for fdayc in fdaycs:
			fin = fdayc[2]
			jfin = os.path.join(pwcmdirin, fin)
			sdatever = fdayc[1]

       			# here we repeat the parsing and run the patchtool editor until this file goes through.
                        # create the output file name
                        jfout = os.path.join(pwxmldirout, re.match('(.*\.)html$', fin).group(1) + 'xml')
                        patchfile = findpatchfile(fin, newpwpatchesdir, pwpatchesdir)

                        # skip already processed files, if date is earler and it's not a forced reparse
                        # (checking output date against input and patchfile, if there is one)
                        if os.path.isfile(jfout):
                                out_modified = os.stat(jfout).st_mtime
                                in_modified = os.stat(jfin).st_mtime
                                patch_modified = None
                                if os.path.isfile(patchfile):
                                        patch_modified = os.stat(patchfile).st_mtime
                                if (not forcereparse) and (in_modified < out_modified) and ((not patchfile) or patch_modified < out_modified):
                                        continue   # bail out
                                if not forcereparse:
                                        print "input modified since output reparsing ", fin

			while True:
				try:
					RunFilterFile(FILTERfunction, xprev, sdate, sdatever, dname, jfin, patchfile, jfout, forcereparse, options.quietc)

					# update the list of files which have been changed
					# (don't see why it can't be determined by the modification time on the file)
					newlistf = os.path.join(pwxmldirout, changedatesfile)
					fil = open(newlistf,'a+')
					fil.write('%d,%s\n' % (time.time(), os.path.split(jfout)[1]))
					fil.close()
					break

				# exception cases which cause the loop to continue
				except ContextException, ce:
					if options.patchtool:
						print "runfilters.py", ce
						RunPatchTool(dname, (sdate + sdatever), ce)
                                                # find file again, in case new
                                                patchfile = findpatchfile(fin, newpwpatchesdir, pwpatchesdir)
						continue # emphasise that this is the repeat condition

					elif options.quietc:
						print ce.description
						print "\tERROR! failed, quietly moving to next day"
						# sys.exit(1) # remove this and it will continue past an exception (but then keep throwing the same tired errors)
						break # leave the loop having not written the xml file; go onto the next day

					# reraise case (used for parser development), so we can get a stackdump and end
					else:
						raise

			# endwhile
			xprev = (jfout, sdatever)


# These text filtering functions filter twice through stringfiles,
# before directly filtering to the real file.
def RunWransFilters(text, sdate):
	si = cStringIO.StringIO()
	FilterWransColnum(si, text, sdate)
	text = si.getvalue()
	si.close()

	si = cStringIO.StringIO()
	FilterWransSpeakers(si, text, sdate)
	text = si.getvalue()
	si.close()

	flatb = FilterWransSections(text, sdate)
	return (flatb, "wrans")


def RunDebateFilters(text, sdate):
	memberList.cleardebatehistory()

	si = cStringIO.StringIO()
	FilterDebateColTime(si, text, sdate, "debate")
	text = si.getvalue()
	si.close()

	si = cStringIO.StringIO()
	FilterDebateSpeakers(si, text, sdate, "debate")
	text = si.getvalue()
	si.close()

	flatb = FilterDebateSections(text, sdate, "debate")
	return (flatb, "debate")


def RunWestminhallFilters(text, sdate):
	memberList.cleardebatehistory()

	si = cStringIO.StringIO()
	FilterDebateColTime(si, text, sdate, "westminhall")
	text = si.getvalue()
	si.close()

	si = cStringIO.StringIO()
	FilterDebateSpeakers(si, text, sdate, "westminhall")
	text = si.getvalue()
	si.close()

	flatb = FilterDebateSections(text, sdate, "westminhall")
	return (flatb, "westminhall")

def RunWMSFilters(text, sdate):
        si = cStringIO.StringIO()
        FilterWMSColnum(si, text, sdate)
        text = si.getvalue()
        si.close()

        si = cStringIO.StringIO()
        FilterWMSSpeakers(si, text, sdate)
        text = si.getvalue()
        si.close()

        flatb = FilterWMSSections(text, sdate)
        return (flatb, "wms")

# These text filtering functions filter twice through stringfiles,
# before directly filtering to the real file.
def RunLordsFilters(text, sdate):
	fourstream = SplitLordsText(text, sdate)
	#return ([], "lords")

	# the debates section (only)
	if fourstream[0]:
		si = cStringIO.StringIO()
		FilterLordsColtime(si, fourstream[0], sdate)
	   	text = si.getvalue()
		si.close()

		si = cStringIO.StringIO()
		LordsFilterSpeakers(si, text, sdate)
	   	text = si.getvalue()
		si.close()

		flatb = LordsFilterSections(text, sdate)
		return (flatb, "lords")

	# error for now
	assert False
	return None



