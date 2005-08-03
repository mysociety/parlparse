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


# handle mismatching sequences of speeches
def MismatchingSequences(flatb, essflatb, seqf, xprevf, xprevver, essx, seqx):
	if seqf[0] == seqf[1] and seqx[0] == seqx[1]:
		return

	# break this down into paragraphs and find the differences between those
	essbp = [ ]
	for essqb in essflatb[seqf[0]:seqf[1]]:
		essbp.extend(essqb[2])
	essxp = [ ]
	for essqx in essx[seqx[0]:seqx[1]]:
		essxp.extend(essqx[2])

	# we may use a Differ object
	print "Mismatch sequences", seqf, seqx
	print "----------------Matching blocks"
	d = difflib.Differ()
	pprint(list(d.compare(essbp, essxp)))

	# This gets the sequences together subject to 
	# inaccuracies.  Need to sequence the strings 
	# according to <tag></tag>, and by word, and then 
	# merge them together as <spans>
	
	# also read the gidredirects properly  
	
	# then extend to the parl debates


def MatchingSpeech(qb, xb, chk, xprevver):
	oldgid = re.search('id="([^"]*)"', chk[1]).group(1)
	qb.gidredirect.append((oldgid, qb.GID))
	# will be able to add in further redirects from chk[4] here


	# will also copy over the speeches filtered through the <span> tags as well.


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

	# we have to filter out any spans in the paragraphs
	essx = [ ]
	for chk in chks:
		assert chk[0] == chk[3]  # heading type
		assert not re.search("<span", chk[2])  # until we learn to thin out and handle it
		if re.match("major-heading|minor-heading", chk[0]):
			heading = "heading"
			psplits = [ re.match("\s*(.*?)\s*$", chk[2]).group(1) ]
		else:
			heading = chk[0]
			psplits = re.findall("<(?:p|tr)[^>]*>\s*(.*?)\s*</(?:p|tr)>", chk[2])
		speaker = re.search('nospeaker="true"|speakerid="[^"]*"', chk[1]).group(0)

		essx.append((heading, speaker, tuple(psplits)))
	assert len(chks) == len(essx)

	# now apply the diffing function on this
	sm = difflib.SequenceMatcher(None, essflatb, essx)
	mismatchstart = (0, 0)
	for smb in sm.get_matching_blocks():
		MismatchingSequences(flatb, essflatb, (mismatchstart[0], smb[0]), xprevf, xprevver, essx, (mismatchstart[1], smb[1]))
		for i in range(smb[2]):
			MatchingSpeech(flatb[smb[0] + i], essx[smb[1] + i], chks[smb[1] + i], xprevver)
		mismatchstart = (smb[0] + smb[2], smb[1] + smb[2])



#	sys.exit(0)



