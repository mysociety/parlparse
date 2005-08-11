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

# get the min index that matches this
def GetMinIndex(indx, a):
	assert indx[0] == 0 and a < indx[-1]
	i0, i1 = 0, len(indx) - 1
	while i0 + 1 < i1:
		im = (i0 + i1) / 2
		assert i0 != im and i1 != im
		if indx[im] <= a:
			i0 = im
		else:
			i1 = im
	assert indx[i0] <= a < indx[i1]
	return i0



# the difficult function that finds matches in the gids
# we don't use an xml parsing feature because it transforms the text
# Very hard use of difflib going on here too
# We make great use of the indices of the different lists
def FactorChanges(flatb, xprevf, xprevver):
	xin = open(xprevf, "r")
	xprevs = xin.read()
	xin.close()

	# quick break into the chunks
	chks = re.findall("<(major-heading|minor-heading|speech|division)\s(.*?)>\n([\s\S]*?)\n</(major-heading|minor-heading|speech|division)>",
					  xprevs)

	# make identically structured huge string over the previous xml file with heading stuff stripped out
	essxlist = [ ]
	essxindx = [ ]
	for chk in chks:
		assert chk[0] == chk[3]  # chunk type
		essxindx.append(len(essxlist))
		essxlist.append("HEADING-" + chk[0])
		speaker = re.search('nospeaker="true"|speakerid="[^"]*"', chk[1]).group(0)
		essxlist.append(speaker)

		if re.match("major-heading|minor-heading", chk[0]):
			heading = re.match("\s*(.*?)\s*$", chk[2]).group(1)
			essxlist.extend(heading.split())
		else:
			for ps in chk[2].split('\n'):
				m = re.match("\s*<(?:p|tr)[^>]*>\s*(.*?)\s*</(?:p|tr)>\s*$", ps)
				if m:
					para = m.group(1)
				else:
					print "TABTABTABTAB", ps
					assert re.match("\s*</?(?:table|tbody)", ps)
					para = ps
				essxlist.extend(para.split())

	essxindx.append(len(essxlist))
	assert len(chks) + 1 == len(essxindx)


	# now make a huge string over the flatb with heading stuff stripped out
	essflatblist = [ ]
	essflatbindx = [ ]
	for qb in flatb:
		essflatbindx.append(len(essflatblist))
		essflatblist.append("HEADING-" + qb.typ)
		essflatblist.append(re.search('nospeaker="true"|speakerid="[^"]*"', qb.speaker).group(0))

		if re.match("major-heading|minor-heading", qb.typ):
			assert len(qb.stext) == 1
			heading = re.match("\s*(.*?)\s*$", qb.stext[0]).group(1)
			essflatblist.extend(heading.split())

		# strip format labels out of paragraphs
		else:
			for ps in qb.stext:
				m = re.match("\s*<(?:p|tr)[^>]*>\s*(.*?)\s*</(?:p|tr)>\s*$", ps)
				if m:
					para = m.group(1)
				else:
					assert re.match("\s*</?(?:table|tbody)", ps)
					para = ps
				essflatblist.extend(para.split())

	essflatbindx.append(len(essflatblist))
	assert len(essflatbindx) == len(flatb) + 1


	# make parallel sequences to the flatb and to this which are stripped down to their essence
	# so that the difflib can work on them


	# now apply the diffing function on this
	sm = difflib.SequenceMatcher(None, essxlist, essflatblist)
	smblocks = [ ((smb[0], smb[0] + smb[2]), (smb[1], smb[1] + smb[2]))  for smb in sm.get_matching_blocks()[:-1] ]
	print smblocks

	# we collect the range for the previous speeches and map it to a set of ranges
	# in the next speeches
	for ix in range(len(chks)):
		ixr = (essxindx[ix], essxindx[ix + 1])
		nixrl = [ ]
		nixrlsz = 0

		# intersect the set of ranges against the contiguous blocks and match forwards
		for lsmb in smblocks:
			if ixr[1] > lsmb[0][0] and ixr[0] < lsmb[0][1]:
				ixi = (max(ixr[0], lsmb[0][0]), min(ixr[1], lsmb[0][1]))
				assert ixi[0] < ixi[1]
				offs = lsmb[1][0] - lsmb[0][0]
				ixit = (ixi[0] - offs, ixi[1] - offs)
				nixrl.append(ixit)
				nixrlsz += ixit[1] - ixit[0]

		assert nixrl # need to handle the empty case where no overlap found specially
		nix = GetMinIndex(essflatbindx, nixrl[0][0])
		if ix != nix:
			print "mmmmmmmmmmmmmmmmmm"

	
		# there's been a change
		if nixrlsz != ixr[1] - ixr[0]:
			print nixrl, ixr
		else:
			assert len(nixrl) == 1



#	mismatchstart = (0, 0)
#	for smb in sm.get_matching_blocks():
#		print smb
#		MismatchingSequences(flatb, essflatb, (mismatchstart[0], smb[0]), xprevf, xprevver, essx, (mismatchstart[1], smb[1]))
#		for i in range(smb[2]):
#			MatchingSpeech(flatb[smb[0] + i], essx[smb[1] + i], chks[smb[1] + i], xprevver)
#		mismatchstart = (smb[0] + smb[2], smb[1] + smb[2])



#	sys.exit(0)



