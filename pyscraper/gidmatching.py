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
def FactorChanges(flatb, scrapeversion):
	# quick break into the chunks
	chks = re.findall("<(major-heading|minor-heading|oral-heading|speech|division)\s(.*?)>\n([\s\S]*?)\n</(major-heading|minor-heading|oral-heading|speech|division)>",
					  scrapeversion)


	# make identically structured huge string over the previous xml file with heading stuff stripped out
	essxlist = [ ]
	essxindx = [ ]
	for chk in chks:
		assert chk[0] == chk[3]  # chunk type
		essxindx.append(len(essxlist))
		essxlist.append("HEADING-" + chk[0])
		speaker = re.search('nospeaker="true"|speakerid="[^"]*"', chk[1]).group(0)
		essxlist.append(speaker)

		if re.match("oral-heading|major-heading|minor-heading", chk[0]):
			assert not re.search("[<>]", chk[2])
			heading = chk[2].strip()
			essxlist.extend(heading.split())
		else:
			for ps in chk[2].split('\n'):
				m = re.match("\s*<(?:p|tr)[^>]*>\s*(.*?)\s*</(?:p|tr)>\s*$", ps)
				if m:
					para = m.group(1)
				else:
					assert re.match("\s*</?(?:table|tbody|thead|caption|divisioncount|mplist|mpname|lordlist|lord)", ps)
					para = ps
				essxlist.extend(re.findall("<[^>]*>|&\w+;|[^<>\s]+", para))

	essxindx.append(len(essxlist))
	assert len(chks) + 1 == len(essxindx)


	# now make a huge string over the flatb with heading stuff stripped out
	essflatblist = [ ]
	essflatbindx = [ ]
	for qb in flatb:
		essflatbindx.append(len(essflatblist))
		essflatblist.append("HEADING-" + qb.typ)
		essflatblist.append(re.search('nospeaker="true"|speakerid="[^"]*"', qb.speaker).group(0))

		if re.match("oral-heading|major-heading|minor-heading", qb.typ):
			heading = ("".join(qb.stext)).strip()
			essflatblist.extend(heading.split())

		# strip format labels out of paragraphs
		else:
			for ps in qb.stext:
				m = re.match("\s*<(?:p|tr)[^>]*>\s*(.*?)\s*</(?:p|tr)>\s*$", ps)
				if m:
					para = m.group(1)
				else:
					assert re.match("\s*</?(?:table|tbody|thead|caption|divisioncount|mplist|mpname|lordlist|lord)", ps)
					para = ps
				# html tags should be words on their own
				essflatblist.extend(re.findall("<[^>]*>|&\w+;|[^<>\s]+", para))

	essflatbindx.append(len(essflatblist))
	assert len(essflatbindx) == len(flatb) + 1


	# make parallel sequences to the flatb and to this which are stripped down to their essence
	# so that the difflib can work on them


	# now apply the diffing function on this
	sm = difflib.SequenceMatcher(None, essxlist, essflatblist)
	smblocks = [ ((smb[0], smb[0] + smb[2]), (smb[1], smb[1] + smb[2]))  for smb in sm.get_matching_blocks()[:-1] ]

	# we collect the range for the previous speeches and map it to a set of ranges
	# in the next speeches
	res = [ ]
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
				ixit = (ixi[0] + offs, ixi[1] + offs)
				assert not nixrl or (nixrl[-1][1] <= ixit[0])
				nixrl.append(ixit)
				nixrlsz += ixit[1] - ixit[0]

		if not nixrl:
			print chks[ix]
		assert nixrl # need to handle the empty case where no overlap found specially
		# type would then be matchtype = "missing"


		# go through the matchint cases
		matchlist = [ GetMinIndex(essflatbindx, nixrl[0][0]) ]
		if nixrlsz != ixr[1] - ixr[0] or len(nixrl) > 1:
			matchtype = "changes"
			for ixit in nixrl:
				ml = GetMinIndex(essflatbindx, ixit[0])
				if matchlist[-1] != ml:
					matchlist.append(ml)
				ml = GetMinIndex(essflatbindx, ixit[1] - 1)
				if matchlist[-1] != ml:
					matchlist.append(ml)
			if len(matchlist) != 1:
				matchtype = "multiplecover"
		else:
			assert len(nixrl) == 1
			matchtype = "perfectmatch"

		# output the pile of redirects of the right type
		chk = chks[ix]
		oldgid = re.search('id="([\w\d\-\./]*)"', chk[1]).group(1)
		for matchg in matchlist:
			res.append('<gidredirect oldgid="%s" newgid="%s" matchtype="%s"/>\n' % (oldgid, flatb[matchg].GID, matchtype))
		# output old version as well, if it's different
		if matchtype != "perfectmatch":
			res.append("<%s %s>\n" % (chk[0], chk[1]))
			res.append(chk[2])
			res.append("\n")
			res.append("</%s>\n" % chk[0])

	return res


# special case because the questions can be re-ordered
def FactorChangesWrans(majblocks, scrapeversion):

	# we need to break the scrape version
	# we separate out and match the major headings separately
	# (anyway, these aren't really used)

	# and then match the questions

	# first extract all the oldtype gid-redirects that will have been put in here by the pre-2005 bMakeOldWransGidsToNew cases
	res = re.findall('<gidredirect oldgid="[^"]*" newgid="[^"]*" matchtype="oldwransgid"/>\n', scrapeversion)

	# extract major headings and match them exactly (till we find a failed example).
	mhchks = re.findall('<major-heading id="([^"]*)"[^>]*>\n\s*([\s\S]*?)\s*?\n</major-heading>', scrapeversion)
	assert len(majblocks) == len(mhchks)
	for i in range(len(majblocks)):
		heading = ("".join(majblocks[i][0].stext)).strip()
		assert heading == mhchks[i][1]
		res.append('<gidredirect oldgid="%s" newgid="%s" matchtype="perfectmatch"/>\n' % (mhchks[i][0], majblocks[i][0].qGID))

	# break into question blocks
	qebchks = re.findall('<minor-heading id="([^"]*)"([^>]*)>\n([\s\S]*?)</minor-heading>\n([\s\S]*?)\s*(?=<(?:major-heading|minor-heading|gidredirect[^>]*oldwranstype|/publicwhip))',
						 scrapeversion)

	# make the map from qnums to blocks
	qnummapq = { }
	for majblock in majblocks:
		for qblock in majblock[1]:
			for qnum in qblock.qnums:
				assert qnum not in qnummapq  # failure means this qnum is found twice in the file.
				qnummapq[qnum] = qblock

	# for each block, find the map forward and check if we want to reprint it in full.
	for qebchk in qebchks:
		qqnums = re.findall('<p [^>]*?qnum="([\d\w]+)">', qebchk[3])
		assert qqnums

		# make sure that they all link to the same qnum in the new one
		qblock = None
		for qqnum in qqnums:
			if qblock:
				assert qblock.headingqb.qGID == qnummapq[qqnum].headingqb.qGID
			else:
				qblock = qnummapq[qqnum]


		# now have to check matching.
		# convert both to strings and compare.
		essxfq = [ ]
		for wd in re.findall("<[^>]*>|&\w+;|[^<>\s]+", qebchk[3]):
			mwd = re.match("<(p|tr|reply|ques)[^>]*>", wd)
			if mwd:
				essxfq.append("<%s>" % mwd.group(1))
			elif not re.match("<gidredirect", wd):
				essxfq.append(wd)

		# build up the same summary from the question block
		essbkfq = [ ]
		for qblockqr in (qblock.queses, qblock.replies):
			for qb in qblockqr:
				essbkfq.append("<%s>" % qb.typ)
				for wd in re.findall("<[^>]*>|&\w+;|[^<>\s]+", "\n".join(qb.stext)):
					mwd = re.match("<(p|tr)[^>]*>", wd)
					if mwd:
						essbkfq.append("<%s>" % mwd.group(1))
					elif not re.match("<gidredirect", wd):
						essbkfq.append(wd)
				essbkfq.append("</%s>" % qb.typ)

		# print the link forwards
		bchanges = (essxfq != essbkfq)
		matchtype = bchanges and "changes" or "perfectmatch"
		if bchanges:
			res.append("\n")
		res.append('<gidredirect oldgid="%s" newgid="%s" matchtype="%s"/>\n' % (qebchk[0], qblock.headingqb.qGID, matchtype))

		# if changes write out the original, else just the gidmaps
		if bchanges:
			res.append('<minor-heading id="%s"%s>\n' % qebchk[0:2])
			res.append(qebchk[2])
			res.append('</minor-heading>\n')
			res.append(qebchk[3])
			res.append("\n\n")
		else:
			for lred in re.findall("<gidredirect[^>]*>\n", qebchk[3]):
				res.append("\t")
				res.append(lred)

	return res

