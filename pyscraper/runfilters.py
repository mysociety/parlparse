#! /usr/bin/python
# vim:sw=8:ts=8:et:nowrap

import sys
import re
import os
import string
import tempfile
import time
import shutil

import xml.sax
xmlvalidate = xml.sax.make_parser()

from ni.parse import ParseDay as ParseNIDay

from contextexception import ContextException
from patchtool import RunPatchTool

from gidmatching import FactorChanges, FactorChangesWrans

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
    # Apply the patch
    shutil.copyfile(filein, fileout)
    status = os.system("patch --quiet %s <%s" % (fileout, patchfile))
    if status == 0:
        return True
    print "blanking out failed patch %s" % patchfile
    print "---- This should not happen, therefore assert!"
    assert False

# the operation on a single file
def RunFilterFile(FILTERfunction, xprev, sdate, sdatever, dname, jfin, patchfile, jfout, bquietc):
    # now apply patches and parse
    patchtempfilename = tempfile.mktemp("", "pw-applypatchtemp-", miscfuncs.tmppath)

    if not bquietc:
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
    if dname == 'regmem' or dname == 'ni':
        regmemout = open(tempfilename, 'w')
        try:
            FILTERfunction(regmemout, text, sdate, sdatever)  # totally different filter function format
        finally:
            regmemout.close()
        # in win32 this function leaves the file open and stops it being renamed
        if sys.platform != "win32":
            xmlvalidate.parse(tempfilename) # validate XML before renaming
        if os.path.isfile(jfout):
            os.remove(jfout)
        os.rename(tempfilename, jfout)
        return

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
    # migrating to patches files stored in parldata, rather than in parlparse
    pwpatchesdir = os.path.join(pwpatchesdirs, dname)
    newpwpatchesdir = os.path.join(toppath, "patches", dname)

    # create output directory
    if not os.path.isdir(pwxmldirout):
        os.mkdir(pwxmldirout)

    # build up the groups of html files per day
    # scan through the directory and make a mapping of all the copies for each
    daymap = { }
    for ldfile in os.listdir(pwcmdirin):
        mnums = re.match("[a-z]*(\d{4}-\d\d-\d\d)([a-z]*)\.(html|json)$", ldfile)
        if mnums:
            daymap.setdefault(mnums.group(1), []).append((AlphaStringToOrder(mnums.group(2)), mnums.group(2), ldfile))
        elif os.path.isfile(os.path.join(pwcmdirin, ldfile)):
            print "not recognized file:", ldfile, " inn ", pwcmdirin

    # make the list of days which we will iterate through (in revers date order)
    daydates = daymap.keys()
    daydates.sort()
    daydates.reverse()

    # loop through file in input directory in reverse date order and build up the
    for sdate in daydates:
        newday = 0
        # skip dates outside the range specified on the command line
        if sdate < options.datefrom or sdate > options.dateto:
            continue

        fdaycs = daymap[sdate]
        fdaycs.sort()

        # detect if there is a change in date on any of them, which will
        # require force reparse on whole day to keep the "latest" flag up to date.
        # this is happening due to over-writes on the today pages
        bmodifiedoutoforder = None
        for fdayc in fdaycs:
            fin = fdayc[2]
            jfin = os.path.join(pwcmdirin, fdayc[2])
            jfout = os.path.join(pwxmldirout, re.match('(.*\.)(html|json)$', fin).group(1) + 'xml')
            patchfile = findpatchfile(fin, newpwpatchesdir, pwpatchesdir)
            if os.path.isfile(jfout):
                out_modified = os.stat(jfout).st_mtime
                in_modified = os.stat(jfin).st_mtime
                if in_modified > out_modified:
                    bmodifiedoutoforder = fin
                if patchfile and os.path.isfile(patchfile):
                    patch_modified = os.stat(patchfile).st_mtime
                    if patch_modified > out_modified:
                        bmodifiedoutoforder = fin
        if bmodifiedoutoforder:
            print "input or patch modified since output reparsing ", bmodifiedoutoforder


        # now we parse these files -- in order -- to accumulate their catalogue of diffs
        xprev = None # previous xml file from which we check against diffs, and its version string
        for fdayc in fdaycs:
            fin = fdayc[2]
            jfin = os.path.join(pwcmdirin, fin)
            sdatever = fdayc[1]

            # here we repeat the parsing and run the patchtool editor until this file goes through.
            # create the output file name
            jfout = os.path.join(pwxmldirout, re.match('(.*\.)(html|json)$', fin).group(1) + 'xml')
            patchfile = findpatchfile(fin, newpwpatchesdir, pwpatchesdir)

            # skip already processed files, if date is earler and it's not a forced reparse
            # (checking output date against input and patchfile, if there is one)
            bparsefile = not os.path.isfile(jfout) or forcereparse or bmodifiedoutoforder

            while bparsefile:  # flag is being used acually as if bparsefile: while True:
                try:
                    RunFilterFile(FILTERfunction, xprev, sdate, sdatever, dname, jfin, patchfile, jfout, options.quietc)

                    # update the list of files which have been changed
                    # (don't see why it can't be determined by the modification time on the file)
                    # (-- because rsync is crap, and different computers have different clocks)
                    newlistf = os.path.join(pwxmldirout, changedatesfile)
                    fil = open(newlistf,'a+')
                    fil.write('%d,%s\n' % (time.time(), os.path.split(jfout)[1]))
                    fil.close()
                    break

                # exception cases which cause the loop to continue
                except ContextException, ce:
                    if options.patchtool:
                        # deliberately don't set options.anyerrors (as they are to fix it!)
                        print "runfilters.py", ce
                        RunPatchTool(dname, (sdate + sdatever), ce)
                        # find file again, in case new
                        patchfile = findpatchfile(fin, newpwpatchesdir, pwpatchesdir)
                        continue # emphasise that this is the repeat condition

                    elif options.quietc:
                        options.anyerrors = True
                        print ce.description
                        print "\tERROR! %s failed on %s, quietly moving to next day" % (dname, sdate)
                        newday = 1
                        # sys.exit(1) # remove this and it will continue past an exception (but then keep throwing the same tired errors)
                        break # leave the loop having not written the xml file; go onto the next day

                    # reraise case (used for parser development), so we can get a stackdump and end
                    else:
                        options.anyerrors = True
                        raise

            # endwhile
            if newday:
                break
            xprev = (jfout, sdatever)


def FixExtraColNumParas(text):
    '''Try and deal with extra paragraphs caused by removing column numbers'''
    text = re.sub('(?:<br>\s*)?</p>(\s*<stamp coldate[^>]*>\s*)<p>(?=[a-z])', r'\1', text)
    return text


def RunNIFilters(fp, text, sdate, sdatever):
    parser = ParseNIDay()
    print "NI parsing %s..." % sdate
    parser.parse_day(fp, text, sdate + sdatever)

