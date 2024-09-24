# vim:sw=8:ts=8:et:nowrap

import os.path
import re

import miscfuncs

pwcmdirs = miscfuncs.pwcmdirs

from miscfuncs import AlphaStringToOrder, NextAlphaString


def MakeDayMap(folder, typ, basedir=pwcmdirs, extension="html"):
    # make the output directory
    if not os.path.isdir(basedir):
        os.mkdir(basedir)
    pwcmfolder = os.path.join(basedir, folder)
    if not os.path.isdir(pwcmfolder):
        os.mkdir(pwcmfolder)

    # the following is code copied from the lordspullgluepages

    # scan through the directory and make a mapping of all the copies for each
    lddaymap = {}
    for ldfile in os.listdir(pwcmfolder):
        mnums = re.match("%s(\d{4}-\d\d-\d\d)([a-z]*)\.%s$" % (typ, extension), ldfile)
        if mnums:
            sdate = mnums.group(1)
            salpha = mnums.group(2)
            lddaymap.setdefault(sdate, []).append(
                (AlphaStringToOrder(salpha), salpha, ldfile)
            )
        elif ldfile.endswith("~") or ldfile == "changedates.txt":
            pass
        elif os.path.isfile(os.path.join(pwcmfolder, ldfile)):
            print("not recognized file:", ldfile, " in ", pwcmfolder)

    return lddaymap, pwcmfolder


def GetFileDayVersions(day, lddaymap, pwcmfolder, typ, extension="html"):
    # make the filename
    dgflatestalpha, dgflatest, dgflatestdayalpha = "", None, None
    if day in lddaymap:
        ldgf = max(lddaymap[day])  # uses alphastringtoorder
        dgflatestalpha = ldgf[1]
        dgflatest = os.path.join(pwcmfolder, ldgf[2])
        dgflatestdayalpha = "%s%s" % (day, dgflatestalpha)
    dgfnextalpha = NextAlphaString(dgflatestalpha)
    ldgfnext = "%s%s%s.%s" % (typ, day, dgfnextalpha, extension)
    dgfnext = os.path.join(pwcmfolder, ldgfnext)
    dgfnextdayalpha = "%s%s" % (day, dgfnextalpha)
    assert not dgflatest or os.path.isfile(dgflatest), (
        "%s exists and is not a file?" % dgflatest
    )
    assert not os.path.isfile(dgfnext), "%s already exists?" % dgfnext
    return dgflatest, dgflatestdayalpha, dgfnext, dgfnextdayalpha
