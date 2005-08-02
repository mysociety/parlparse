import sys
import re
import os
import xml.sax
import tempfile
import string
import miscfuncs
import difflib
from pprint import pprint

#from xmlfilewrite import PrevParsedFile
class PrevParsedFile:
	pass

toppath = miscfuncs.toppath
pwxmldirs = miscfuncs.pwxmldirs
tempfilename = miscfuncs.tempfilename

from miscfuncs import NextAlphaString, AlphaStringToOrder

d = difflib.Differ()


def MatchSpeech(sp1, sp2):
	if sp1.speakerid == sp2.speakerid and len(sp1.paras) == len(sp2.paras):
		for i in range(len(sp1.paras)):
			a = sp1.paras[i]
			b = sp2.paras[i]

			sm = difflib.SequenceMatcher(None, sp1.paras[i], sp2.paras[i])
			for tag, i1, i2, j1, j2 in sm.get_opcodes():
				if tag != "equal":
					print ("%7s a[%d:%d] (%s) b[%d:%d] (%s)" % (tag, i1, i2, a[i1:i2], j1, j2, b[j1:j2]))
		return True
	return False

# generate a matching table between two xml files
def MakeGidFileMatching(flatbprev, flatblatest):
	# increment along both until mismatch
	i = 0
	while i < min(len(flatbprev), len(flatblatest)):
		if not MatchSpeech(flatbprev[i], flatblatest[i]):
			break
		i += 1
	if i < min(len(flatbprev), len(flatblatest)):
		print "Mismatch:"
		print i
		pprint (flatbprev[i].paras)
		pprint (flatblatest[i].paras)


	# do we assume that names don't get mistaken, and the worst

# finds sets of xml files which belong on the same day and matches them to the latest
def RunGidMatching(dname):
	daymap = { }
	pwxmldir = os.path.join(pwxmldirs, dname)

	for xfile in os.listdir(pwxmldir):
		mnums = re.search("(\d{4}-\d\d-\d\d)([a-z]*)\.xml$", xfile)
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
			MakeGidFileMatching(ppf.prevflatb, ppflatest.prevflatb)



# the difficult function that finds matches in the gids
# we don't use an xml parsing feature because it transforms the text 
# Very hard use of difflib going on here too
# We make great use of the indices of the different lists
def FactorChanges(flatb, xprevf, xprevver):
	xin = open(xprevf, "r")
	xprevs = xin.read()
	xin.close()

	# break into the chunks
	chks = re.findall("<(major-heading|minor-heading|speech|division)\s(.*?)>\n([\s\S]*?)\n</(major-heading|minor-heading|speech|division)>",  xprevs)
	print len(chks)

	# make parallel sequences to the flatb and to this which are stripped down to their essence
	# so that the difflib can work on them
	
	# table rows are treated as paragraphs, with the rest of the structure from them ignored

	essflatb = [ ]
	for qb in flatb:
		if re.match("major-heading|minor-heading", qb.typ):
			heading = "heading"
			assert len(qb.stext) == 1
			psplits = [ re.match("\s*(.*?)\s*$", qb.stext[0]).group(1) ]
		else:
			heading = qb.typ
			psplits = [ ]
			for ps in qb.stext:
				if not re.match("\s*</?(?:table|tbody)", ps):
					m = re.match("\s*<(?:p|tr)[^>]*>\s*(.*?)\s*</(?:p|tr)>\s*$", ps)
					if not m:
						print "mismatch", ps
					psplits.append(m.group(1))

		speaker = re.search('nospeaker="true"|speakerid="[^"]*"', qb.speaker).group(0)
		essflatb.append((heading, speaker, tuple(psplits)))

	essx = [ ]
	for chk in chks:
		assert chk[0] == chk[3]  # heading type
		if re.match("major-heading|minor-heading", chk[0]):
			heading = "heading"
			psplits = [ re.match("\s*(.*?)\s*$", chk[2]).group(1) ]
		else:
			heading = chk[0]
			psplits = re.findall("<(?:p|tr)[^>]*>\s*(.*?)\s*</(?:p|tr)>", chk[2])
		speaker = re.search('nospeaker="true"|speakerid="[^"]*"', chk[1]).group(0)

		essx.append((heading, speaker, tuple(psplits)))

	# now apply the diffing function on this
	sm = difflib.SequenceMatcher(None, essflatb, essx)


	print "----------------Matching blocks"
	print sm.get_matching_blocks()[:-1]

#	sys.exit(0)



