#! /usr/bin/python2.3
# vim:sw=8:ts=8:et:nowrap

import sys
import re
import os
import string


# In Debian package python2.3-egenix-mxdatetime
import mx.DateTime



from splitheadingsspeakers import SplitHeadingsSpeakers
from splitheadingsspeakers import StampUrl

from clsinglespeech import qspeech
from parlphrases import parlPhrases

from miscfuncs import FixHTMLEntities

from filterdivision import FilterDivision
from lordsfilterdivisions import LordsFilterDivision
from lordsfilterdivisions import LordsDivisionParsingPart
from filterdebatespeech import FilterDebateSpeech

from contextexception import ContextException


def StripDebateHeading(hmatch, ih, headspeak, bopt=False):
	reheadmatch = '(?:<stamp aname="[^"]*"/>)*' + hmatch
	if (not re.match(reheadmatch, headspeak[ih][0])) or headspeak[ih][2]:
		if bopt:
			return ih
		print "\n", headspeak[ih]
		raise ContextException('non-conforming "%s" heading ' % hmatch)
	return ih + 1

def StripLordsDebateHeadings(headspeak, sdate):
	# check and strip the first two headings in as much as they are there
	ih = 0
	ih = StripDebateHeading('Initial', ih, headspeak)

	# House of Lords
	ih = StripDebateHeading('house of lords(?i)', ih, headspeak, True)

	# Thursday, 18th December 2003.
	mdateheading = re.match('(?:<stamp aname="[^"]*"/>)*([\w\s\d,]*)\.', headspeak[ih][0])
	if not mdateheading or (sdate != mx.DateTime.DateTimeFrom(mdateheading.group(1)).date) or headspeak[ih][2]:
		print headspeak[ih]
		#raise ContextException('non-conforming date heading')  # recoverable?
	else:
		ih = ih + 1

	if re.match("THE QUEEN(?:'|&....;)S SPEECH", headspeak[ih][0]):
		print headspeak[ih][0]
		print "QUEENS SPEECH"
		# don't advance, because this is the heading (works for 2005-05-17)

	elif re.match("Parliament", headspeak[ih][0]):
		print "parliamentparliament"
		# don't advance; this is a title (works for 2005-05-11)

	else:
		# The House met at eleven of the clock (Prayers having been read earlier at the Judicial Sitting by the Lord Bishop of St Albans): The CHAIRMAN OF COMMITTEES on the Woolsack.
		gstarttime = re.match('(?:<stamp aname="[^"]*"/>)*(?:reassembling.*?recess, )?the house (?:met|resumed)(?: for Judicial Business)? at ([^(]*)(?i)', headspeak[ih][0])
		if (not gstarttime) or headspeak[ih][2]:
			print "headspeakheadspeakih", headspeak[ih][0]
			raise ContextException('non-conforming "house met at" heading ', fragment=headspeak[ih][0])
		ih = ih + 1

		# Prayers&#151;Read by the Lord Bishop of Southwell.
		ih = StripDebateHeading('prayers(?i)', ih, headspeak, True)



	# find the url, colnum and time stamps that occur before anything else in the unspoken text
	stampurl = StampUrl(sdate)

	# set the time from the wording 'house met at' thing.
	for j in range(0, ih):
		stampurl.UpdateStampUrl(headspeak[j][1])

	if (not stampurl.stamp) or (not stampurl.pageurl):
		raise Exception, ' missing stamp url at beginning of file '
	return (ih, stampurl)



# Handle normal type heading
def LordsHeadingPart(headingtxt, stampurl):
	bmajorheading = False

	headingtxtfx = FixHTMLEntities(headingtxt)
	qb = qspeech('nospeaker="true"', headingtxtfx, stampurl)
	if bmajorheading:
		qb.typ = 'major-heading'
	else:
		qb.typ = 'minor-heading'

	# headings become one unmarked paragraph of text
	qb.stext = [ headingtxtfx ]
	return qb


# this function is taken from debdivisionsections
def SubsPWtextsetS(st):
	if re.search('pwmotiontext="yes"', st) or not re.match('<p', st):
		return st
	return re.sub('<p(.*?)>', '<p\\1 pwmotiontext="yes">', st)

# this function is taken from debdivisionsections
# to be inlined
def SubsPWtextset(stext):
	res = map(SubsPWtextsetS, stext)
	return res

#	<p>On Question, Whether the said amendment (No. 2) shall be agreed to?</p>
#reqput = re.compile('%s|%s|%s|%s|%s(?i)' % (regqput, regqputt, regitbe, regitbepq1, regitbepq))
resaidamend =  re.compile("<p[^>]*>On Question, (?:[Ww]hether|That) (?:the said amendment|the amendment|the House|Clause|Amendment|the Bill|the said [Mm]otion|Lord|the manuscript|the Motion)")

#	<p>On Question, Whether the said amendment (No. 2) shall be agreed to?</p>
#	<p>Their Lordships divided: Contents, 133; Not-Contents, 118.</p>
#housedivtxt = "The (?:House|Committee) (?:(?:having )?divided|proceeded to a Division)"
relorddiv = re.compile('<p[^>]*>(?:\*\s*)?Their Lordships divided: Contents,? (\d+) ?; Not-Contents,? (\d+)\.?</p>$')
def GrabLordDivisionProced(qbp, qbd):
	if not re.match("speech|motion", qbp.typ) or len(qbp.stext) < 1:
		print qbp.stext
		raise Exception, "previous to division not speech"

	hdg = relorddiv.match(qbp.stext[-1])
	if not hdg:
		print qbp.stext[-1]
		raise ContextException("no lordships divided before division", stamp=qbp.sstampurl)

	# if previous thing is already a no-speaker, we don't need to break it out
	# (the coding on the question put is complex and multilined)
	if re.search('nospeaker="true"', qbp.speaker):
		qbp.stext = SubsPWtextset(qbp.stext)
		return None

	# look back at previous paragraphs and skim off a part of what's there
	# to make a non-spoken bit reporting on the division.
	iskim = 1
	if not resaidamend.match(qbp.stext[-2]):
		print qbp.stext[-2]
		raise ContextException("no on said amendment", stamp=qbp.sstampurl, fragment=qbp.stext[-2])
	iskim = 2

	# copy the two lines into a non-speaking paragraph.
	qbdp = qspeech('nospeaker="true"', "", qbp.sstampurl)
	qbdp.typ = 'speech'
	qbdp.stext = SubsPWtextset(qbp.stext[-iskim:])

	# trim back the given one by two lines
	qbp.stext = qbp.stext[:-iskim]

	return qbdp

# separate out the making of motions and my lords speeches
# the position of a colon gives it away
# returns a pre and post speech accounting for unspoken junk before and after a block of spoken stuff
def FilterLordsSpeech(qb):

	# pull in the normal filtering that gets done on debate speeches
	# does the paragraph indents and tables.  Maybe should be inlined for lords
	FilterDebateSpeech(qb)

	# no speaker case, no further processing
	if re.match('nospeaker="true"', qb.speaker):
		return [ qb ]

	# the colon attr is blank or has a : depending on what was there after the name that was matched
	ispeechstartp1 = 0 # plus 1

	# no colonattr or colon, must be making a speech
	recol = re.search('colon="(:?)"', qb.speaker)
	if not recol or recol.group(1):
		# text of this kind at the begining should not be spoken
		if re.search("<p>(?:moved|asked) (?i)", qb.stext[0]):
			print qb.speaker
			print qb.stext[0]
			raise ContextException("has moved amendment after colon (try taking : out)", stamp=qb.sstampurl)
		ispeechstartp1 = 1  # 0th paragraph is speech text

	# just a question -- non-colon
	res = [ ] # output list
	if not ispeechstartp1:
		if re.match("<p>asked Her Majesty's Government|<p>rose to (?:ask|call|draw attention|consider)|<p>asked the|<p>&mdash;Took the Oath", qb.stext[0]):
			qb.stext[0] = re.sub('^<p>', '<p class="asked">', qb.stext[0])  # cludgy; already have the <p>-tag embedded in the string
			ispeechstartp1 = 2  # 1st paragraph is speech text

		# identify a writ of summons (single line)
		elif re.match("<p>(?:[\s,]*having received a [Ww]rit of [Ss]ummons .*?)?[Tt]ook the [Oo]ath\.</p>$", qb.stext[0]):
			assert len(qb.stext) == 1
			qb.stext[0] = re.sub('^<p>', '<p class="summons">', qb.stext[0])  # cludgy; already have the <p>-tag embedded in the string
			return [ qb ]

		# identify a moved amendment
		elif re.match("<p>moved,? |<p>Amendments? |<p>had given notice|<p>rose to move|<p>had given his intention", qb.stext[0]):

			# find where the speech begins
			ispeechstartp1 = len(qb.stext)
			for i in range(len(qb.stext)):
				rens = re.match("(<p>The noble \S* said:\s*)", qb.stext[i])
				if rens:
					qb.stext[i] = "<p>" +  qb.stext[i][rens.end(1):]
					i = ispeechstartp1
					break
			# everything up to this point is non-speech
			assert ispeechstartp1 > 0
			qbprev = qspeech(qb.speaker, "", qb.sstampurl)
			qbprev.typ = 'speech'
			qbprev.stext = SubsPWtextset(qb.stext[:ispeechstartp1])
			res.append(qbprev)

			# upgrade the spoken part
			if ispeechstartp1 != len(qb.stext):
				qb.speaker = string.replace(qb.speaker, 'colon=""', 'colon=":"')
				qb.stext = qb.stext[ispeechstartp1:]
				ispeechstartp1 = 1 # the spoken text must reach here
			else:
				return res


		# error, no moved amendment found
		else:
			print qb.stext
			print "no moved amendment; is a colon missing after the name?"
			raise ContextException("missing moved amendment", stamp=qb.sstampurl)

	# advance to place where non-speeches happen
	if ispeechstartp1 > len(qb.stext):
		print "ispeechstartp1 problem; speeches running through", ispeechstartp1, len(qb.stext)
		print qb.stext
		raise ContextException("end of speech boundary unclear running through; need to separate paragraphs?", stamp=qb.sstampurl)

	# a common end of speech is to withdraw an amendment
	bAmendWithdrawn = False
	while ispeechstartp1 < len(qb.stext):
		if re.match('<p>Amendment(?: No\. \d+[A-Z]+)?(?:, as an amendment)?(?: to(?: Commons)? Amendment No\. \d+[A-Z]*| to the Motion)?,? by leave,? withdrawn.</p>', qb.stext[ispeechstartp1]):
			#print "withdrawnwithdrawn", qb.stext[ispeechstartp1]
			bAmendWithdrawn = True
			break
		if re.match('<p>(?:Amendment.{0,50}?|by leave, )withdrawn', qb.stext[ispeechstartp1]):
			print "**********Marginal amendwith", qb.stext[ispeechstartp1]
		ispeechstartp1 += 1

	# the speech ran its proper course
	if ispeechstartp1 == len(qb.stext):
		res.append(qb)
		assert not bAmendWithdrawn
		return res

	# put in the withdrawn amendment into the current speech
	if bAmendWithdrawn:
		qb.stext[ispeechstartp1] = re.sub('<p(.*?)>', '<p\\1 pwmotiontext="yes" pwmotionwithdrawn="yes">', qb.stext[ispeechstartp1])
		ispeechstartp1 += 1

	# From amendment withdrawn onwards put in as unspoken text
	res.append(qb)
	if ispeechstartp1 < len(qb.stext):
		qbunspo = qspeech('nospeaker="true"', "", qb.sstampurl)
		qbunspo.typ = 'speech'
		qbunspo.stext = SubsPWtextset(qb.stext[ispeechstartp1:])
		del qb.stext[ispeechstartp1:]
		res.append(qbunspo)

	return res


################
# main function
################
def LordsFilterSections(text, sdate):

	# deal with one exceptional case of indenting
	if sdate == "2005-10-26":
		l = len(text)
		text = re.sub("<ul><ul>(<ul>)?", "<ul>", text)
		text = re.sub("</ul></ul>(</ul>)?", "</ul>", text)

		# regsection1 = '<h\d><center>.*?\s*</center></h\d>' in splitheadingsspeakers.py
		print "Duplicate <ul>s removed and <center> sorted on %s which shortened text by %d" % (sdate, l - len(text))


	# split into list of triples of (heading, pre-first speech text, [ (speaker, text) ])
	headspeak = SplitHeadingsSpeakers(text)


	# break down into lists of headings and lists of speeches
	(ih, stampurl) = StripLordsDebateHeadings(headspeak, sdate)
	if ih == None:
		return

	# loop through each detected heading and the detected partitioning of speeches which follow.
	# this is a flat output of qspeeches, some encoding headings, and some divisions.
	# see the typ variable for the type.
	flatb = [ ]

	for sht in headspeak[ih:]:
		# triplet of ( heading, unspokentext, [(speaker, text)] )
		headingtxt = stampurl.UpdateStampUrl(string.strip(sht[0]))  # we're getting stamps inside the headings sometimes
		unspoketxt = sht[1]
		speechestxt = sht[2]

		# the heading detection, as a division or a heading speech object
		# detect division headings
		gdiv = re.match('Division No. (\d+)', headingtxt)

		# heading type
		if not gdiv:
			qbh = LordsHeadingPart(headingtxt, stampurl)
			flatb.append(qbh)

		# division type
		else:
			(unspoketxt, qbd) = LordsDivisionParsingPart(string.atoi(gdiv.group(1)), unspoketxt, stampurl, sdate)

			# grab some division text off the back end of the previous speech
			# and wrap into a new no-speaker speech
			qbdp = GrabLordDivisionProced(flatb[-1], qbd)
			if qbdp:
				flatb.append(qbdp)
			flatb.append(qbd)

		# continue and output unaccounted for unspoken text occuring after a
		# division, or after a heading
		if (not re.match('(?:<[^>]*>|\s)*$', unspoketxt)):
			qb = qspeech('nospeaker="true"', unspoketxt, stampurl)
			qb.typ = 'speech'
			flatb.extend(FilterLordsSpeech(qb))

		# there is no text; update from stamps if there are any
		else:
			stampurl.UpdateStampUrl(unspoketxt)

		# go through each of the speeches in a block and put it into our batch of speeches
		for ss in speechestxt:
			qb = qspeech(ss[0], ss[1], stampurl)
			qb.typ = 'speech'
			flatb.extend(FilterLordsSpeech(qb))


	# we now have everything flattened out in a series of speeches
	return flatb


