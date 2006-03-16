#! /usr/bin/python2.4

import sys
import re
import string
import cStringIO

import mx.DateTime

from parlphrases import parlPhrases
from miscfuncs import FixHTMLEntities
from miscfuncs import FixHTMLEntitiesL
from miscfuncs import SplitParaIndents

from filterwransemblinks import rreglink
from filterwransemblinks import rregemail

from filterwransemblinks import rehtlink
from filterwransemblinks import ConstructHTTPlink

from resolvemembernames import memberList


# this code fits onto the paragraphs before the fixhtmlentities and
# performs difficult regular expression matching that can be
# used for embedded links.

# this code detects square bracket qnums [12345], standing order quotes,
# official report references (mostly in wranses), and hyperlinks (most of which
# are badly typed and full of spaces).

# the structure of each function is to search for an occurrance of the pattern.
# it sends the text before the match to the next function, it encodes the
# pattern itself however it likes, and sends the text after the match back to
# itself as a kind of recursion.

# in the future it should be possible to pick out direct references to
# other members of the house in speeches.


reqnum = re.compile("\s*\[(\d+)\]\s*$")
refqnum = re.compile("\s*\[(\d+)\]\s*")

redatephraseval = re.compile('(?:(?:%s),? )?(\d+ (?:%s)( \d+)?)' % (parlPhrases.daysofweek, parlPhrases.monthsofyear))
def TokenDate(ldate, phrtok):
	try:
		lldate = mx.DateTime.DateTimeFrom(ldate.group(0)).date
		if lldate > mx.DateTime.now().date:
			lldate = (mx.DateTime.DateTimeFrom(ldate) - mx.DateTime.RelativeDateTime(years=1)).date
		ldate = lldate
		phrtok.lastdate = ldate
	except:
		phrtok.lastdate = ''
	return ('phrase', ' class="date" code="%s"' % FixHTMLEntities(phrtok.lastdate))

restandingo = re.compile('''(?x)
		Standing\sOrder\sNo\.\s*
		(
		 \d+[A-Z]?               # number+letter
		 (?:\s*\(\d+\))?         # bracketted number
		 (?:\s*\([a-z]\))?		 # bracketted letter
		)
		(?:\s*
		\(([^()]*(?:\([^()]*\))?)\) # inclusion of title for clarity
		)?
''')
restandingomarg = re.compile("Standing Order No")
def TokenStandingOrder(mstandingo, phrtok):
	if mstandingo.group(2):
		return ('phrase', ' class="standing-order" code="%s" title="%s"' % (FixHTMLEntities(mstandingo.group(1)), FixHTMLEntities(mstandingo.group(2))))
	return ('phrase', ' class="standing-order" code="%s"' % mstandingo.group(1))

def TokenHttpLink(mhttp, phrtok):
	qstrlink = ConstructHTTPlink(mhttp.group(1), mhttp.group(2), mhttp.group(3))
	return ('a', ' href="%s"' % qstrlink)

reoffrepw = re.compile('<i>official(?:</i> <i>| )report,?</i>,? c(?:olumns?)?\.? (\d+(?:&#150;\d+)?[WS]*)(?i)')
def TokenOffRep(qoffrep, phrtok):
	# extract the proper column without the dash
	qcpart = re.match('(\d+)(?:&#150;(\d+))?([WS]*)(?i)$', qoffrep.group(1))
	if qcpart.group(2):
		qcpartlead = qcpart.group(1)[len(qcpart.group(1)) - len(qcpart.group(2)):]
		if string.atoi(qcpartlead) >= string.atoi(qcpart.group(2)):
			print ' non-following column leadoff ', qoffrep.group(0)
			#raise Exception, ' non-following column leadoff '

	# this gives a link to the date.colnumW type show.
	qcolcode = qcpart.group(1) + string.upper(qcpart.group(3))
	if (string.upper(qcpart.group(3)) == 'WS'):
		sectt = 'wms'
	elif (string.upper(qcpart.group(3)) == 'W'):
		sectt = 'wrans'
	else:
		sectt = 'debates'
	offrepid = '%s/%s.%s' % (sectt, phrtok.lastdate, qcolcode)

	return ('phrase', ' class="offrep" id="%s"' % offrepid )


#my hon. Friend the Member for Regent's Park and Kensington, North (Ms Buck)
# (sometimes there are spurious adjectives
rehonfriend = re.compile('''(?x)
				(?:[Mm]y|[Hh]er|[Hh]is|[Oo]ur|[Tt]he)
				(\sright)?               # group 1 (privy counsellors)
				(.{0,26}?)               # group 2 sometimes an extra adjective eg "relentlyessly inclusive"
				(?:\s|&nbsp;)*(?:hon\.)?
				(\sand\slearned)?		 # group 3 used when MP is a barrister
				(?:&.{4};and\sgallant&.{4};)?  # for such nonsense
				(?:\s|&nbsp;)*(?:[Ff]riends?|Member)
				(?:,?\s.{0,16})? 		 # superflous words (eg ", in this context,")
				(?:\sthe\sMember\s)?	 # missing in the case where it's mere's "the hon. Member for"
				for\s
				([^(]{3,60}?)			 # group 4 the name of the constituency
				\s*
				\(([^)]{5,60}?)\)		 # group 5 the name of the MP, inserted for clarity.
						''')
rehonfriendmarg = re.compile('the\s+(hon\.\s*)?member for [^(]{0,60}\((?i)')
def TokenHonFriend(mhonfriend, phrtok):
	# will match for ids
	orgname = mhonfriend.group(5)
	res = memberList.matchfullnamecons(orgname, mhonfriend.group(4), phrtok.sdate, alwaysmatchcons = False)
	if not res[0]:  # comes back as None
		nid = "unknown"
		mname = orgname
	else:
		nid = res[0]
		mname = res[1]
	assert not re.search("&", mname)
	
	# remove any xml entities from the name
	orgname = res[1]

	# if you put the .encode("latin-1") on the res[1] it doesn't work when there are strange characters.
	return ('phrase', (' class="honfriend" id="%s" name="%s"' % (nid, mname)).encode("latin-1"))



# the array of tokens which we will detect on the way through
tokenchain = [
	( "date",			redatephraseval,None, 				TokenDate ),
	( "offrep", 		reoffrepw, 		None, 				TokenOffRep ),
	( "standing order", restandingo, 	restandingomarg, 	TokenStandingOrder ),
	( "httplink", 		rehtlink, 		None, 				TokenHttpLink ),
	( "offrep", 		reoffrepw, 		None, 				TokenOffRep ),
	( "honfriend", 		rehonfriend, 	rehonfriendmarg, 	TokenHonFriend ),
			  ]


# this handles the chain of tokenization of a paragraph
class PhraseTokenize:

	# recurses over itc < len(tokenchain)
	def TokenizePhraseRecurse(self, qs, stex, itc):

		# end of the chain
		if itc == len(tokenchain):
			self.toklist.append( ('', '', FixHTMLEntities(stex, stampurl=(qs and qs.sstampurl))) )
			return

		# keep eating through the pieces for the same token
		while stex:
			# attempt to split the token
			mtoken = tokenchain[itc][1].search(stex)
			if mtoken:   # the and/or method fails with this
				headtex = stex[:mtoken.span(0)[0]]
			else:
				headtex = stex

			# check for marginals
			if tokenchain[itc][2] and tokenchain[itc][2].search(headtex):
				pass
				#print "Marginal token match:", tokenchain[itc][0]
				#print tokenchain[itc][2].findall(headtex)
				#print headtex

			# send down the one or three pieces up the token chain
			if headtex:
				self.TokenizePhraseRecurse(qs, headtex, itc + 1)

			# no more left
			if not mtoken:
				break

			# break up the token if it is there
			tokpair = tokenchain[itc][3](mtoken, self)
			self.toklist.append( (tokpair[0], tokpair[1], FixHTMLEntities(mtoken.group(0), stampurl=(qs and qs.sstampurl))) )
			#print "Token detected:", mtoken.group(0)

			# the tail part
			stex = stex[mtoken.span(0)[1]:]



	def __init__(self, qs, stex):
		self.lastdate = ''
		self.toklist = [ ]
		self.sdate = qs and qs.sstampurl.sdate

		# separate out any qnums at end of paragraph
 		self.rmqnum = reqnum.search(stex)
		if self.rmqnum:
			stex = stex[:self.rmqnum.span(0)[0]]

		# separate out qnums stuffed into front of paragraph (by the grabber of the speakername)
		frqnum = refqnum.search(stex)
		if frqnum:
			assert not self.rmqnum
			self.rmqnum = frqnum
			stex = stex[frqnum.span(0)[1]:]

		self.TokenizePhraseRecurse(qs, stex, 0)


	def GetPara(self, ptype, bBegToMove=False, bKillqnum=False):

		if (not bKillqnum) and self.rmqnum:
			self.rqnum = ' qnum="%s"' % self.rmqnum.group(1)
		else:
			self.rqnum = ""


		if bBegToMove:
			res = [ '<p class="%s" pwmotiontext="yes">' % ptype ]
		elif ptype:
			res = [ '<p class="%s">' % ptype ]
		else:
			res = [ '<p%s>' % self.rqnum ]

		for tok in self.toklist:
			if tok[0]:
				res.append('<%s%s>' % (tok[0], tok[1]))
				res.append(tok[2])
				res.append('</%s>' % tok[0])
			else:
				res.append(tok[2])

		res.append('</p>')
		return string.join(res, '')



