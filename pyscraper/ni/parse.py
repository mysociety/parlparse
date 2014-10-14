#! /usr/bin/env python

import re
import os
import glob
import sys
import time
import tempfile
import shutil
import xml.sax
xmlvalidate = xml.sax.make_parser()

sys.path.append('../')
from resolveninames import memberList
from contextexception import ContextException
from BeautifulSoup import BeautifulSoup, Tag

import codecs
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

parldata = '../../../parldata/'

class NISoup(BeautifulSoup):
	# Oh yes, did anyone ever say that I totally ROCK?
	BeautifulSoup.RESET_NESTING_TAGS['b'] = None
	BeautifulSoup.RESET_NESTING_TAGS['i'] = None
	BeautifulSoup.RESET_NESTING_TAGS['font'] = None
	# FrontPage just loves to do things totally wrong
	myMassage = [
		# Remove gumph
		(re.compile('</?center>|<font SIZE="3">'), lambda match: ''),
		# Swap elements that are clearly the wrong way round
		(re.compile('(<p[^>]*>)\s*((</(font|i|b)>)+)'), lambda match: match.group(2) + match.group(1)),
		(re.compile('(<p[^>]*>)\s*(<b>)'), lambda match: match.group(2) + match.group(1)),
		(re.compile('((<(font|i|b)>)+)\s*(</p[^>]*>)'), lambda match: match.group(3) + match.group(1)),
		(re.compile('(<b>)\s*(<p[^>]*>)([^<]*?</b>)'), lambda match: match.group(2) + match.group(1) + match.group(3)),
		(re.compile('<span class="BoldText">(.*?)</span>'), lambda match: '<strong>' + match.group(1) + '</strong>'),
		(re.compile('(?:<span style="font-family: Arial;">|<span style="color: #000000;">){2}(.*?)</span></span>'), lambda match: match.group(1)),
		(re.compile('(?:<span style="font-family: Arial;">|<span style="(?:font-family: Times New Roman; )?color: #000000;">)(.*?)</span>'), lambda match: match.group(1)),
	]

class ParseDay:
	def id(self):
		return '%s.%s.%s' % (self.date, self.idA, self.idB)

	def parse_day(self, fp, text, date):
		self.date = date

		# Special case for 2002-10-08
		if re.search('i$', date):
			self.idA = 9
			self.idB = 17
		else:
			self.idA = 0
			self.idB = 0

		soup = NISoup(text, markupMassage=NISoup.myMassage)
		self.out = fp
		self.out = streamWriter(self.out)
		self.out.write('<?xml version="1.0" encoding="utf-8"?>\n')
		self.out.write('''
<!DOCTYPE publicwhip
[
<!ENTITY pound   "&#163;">
<!ENTITY euro    "&#8364;">

<!ENTITY agrave  "&#224;">
<!ENTITY aacute  "&#225;">
<!ENTITY acirc   "&#226;">
<!ENTITY ccedil  "&#231;">
<!ENTITY egrave  "&#232;">
<!ENTITY eacute  "&#233;">
<!ENTITY ecirc   "&#234;">
<!ENTITY iacute  "&#237;">
<!ENTITY ograve  "&#242;">
<!ENTITY oacute  "&#243;">
<!ENTITY uacute  "&#250;">
<!ENTITY Aacute  "&#193;">
<!ENTITY Eacute  "&#201;">
<!ENTITY Iacute  "&#205;">
<!ENTITY Oacute  "&#211;">
<!ENTITY Uacute  "&#218;">
<!ENTITY Uuml    "&#220;">
<!ENTITY auml    "&#228;">
<!ENTITY euml    "&#235;">
<!ENTITY iuml    "&#239;">
<!ENTITY ntilde  "&#241;">
<!ENTITY ouml    "&#246;">
<!ENTITY uuml    "&#252;">
<!ENTITY fnof    "&#402;">

<!ENTITY nbsp    "&#160;">
<!ENTITY shy     "&#173;">
<!ENTITY deg     "&#176;">
<!ENTITY sup2    "&#178;">
<!ENTITY middot  "&#183;">
<!ENTITY ordm    "&#186;">
<!ENTITY frac14  "&#188;">
<!ENTITY frac12  "&#189;">
<!ENTITY frac34  "&#190;">
<!ENTITY ndash   "&#8211;">
<!ENTITY mdash   "&#8212;">
<!ENTITY lsquo   "&#8216;">
<!ENTITY rsquo   "&#8217;">
<!ENTITY ldquo   "&#8220;">
<!ENTITY rdquo   "&#8221;">
<!ENTITY hellip  "&#8230;">
<!ENTITY bull    "&#8226;">
]>

<publicwhip>
''')
		memberList.cleardebatehistory() # Don't want to keep it between days, or reruns of same day
		memberList.setDeputy(None)
		if date >= '2014-09-07':
			self.parse_day_new_new(soup, date)
		elif date >= '2012-04-30' and not soup('p', { 'class': True } ):
			self.parse_day_new_new(soup, date)
		elif int(date[0:4]) >= 2006:
			self.parse_day_new(soup, date)
		else:
			body = soup('p')
			self.parse_day_old(body)
		self.out.write('</publicwhip>\n')

	def display_speech(self):
		if self.text:
			if self.speaker[0]:
				speaker_str = self.speaker[0]
			else:
				speaker_str = 'nospeaker="true"'
			timestamp = self.speaker[1]
			if timestamp:
				timestamp = ' time="%s"' % timestamp
			self.idB += 1
			self.out.write('<speech id="uk.org.publicwhip/ni/%s" %s%s url="%s">\n%s</speech>\n' % (self.id(), speaker_str, timestamp, self.url, self.text))
			self.text = ''
	
	def display_heading(self, text, timestamp, type):
		if timestamp:
			timestamp = ' time="%s"' % timestamp
		self.out.write('<%s-heading id="uk.org.publicwhip/ni/%s"%s url="%s">%s</%s-heading>\n' % (type, self.id(), timestamp, self.url, text, type))


	def parse_day_old(self, body):
		match = re.match('\d\d(\d\d)-(\d\d)-(\d\d)(i?)$', self.date)
		urldate = '%s%s%s%s' % match.groups()
		self.baseurl = 'http://www.niassembly.gov.uk/record/reports/%s.htm' % urldate
		self.url = self.baseurl

		# Heading check
		if not re.match('Northern\s+Ireland\s+Assembly', body[0].find(text=True)):
			raise Exception, 'Missing NIA heading!'
		date_head = body[1].find(text=True)
		if not re.match('Contents', body[2].find(text=True)):
			raise Exception, 'Missing contents heading!'
		body = body[3:]
	
		timestamp = ''
		in_oral_answers = False
		oral_qn = 0
		self.speaker = (None, timestamp)
		self.text = ''
		for p in body:
			if not p(text=True): continue
			ptext = re.sub("\s+", " ", ''.join(p(text=True)))
			phtml = re.sub("\s+", " ", p.renderContents()).decode('utf-8')
			#print phtml
			if (p.a and p.a.get('href', ' ')[0] == '#') or (p.a and re.match('\d', p.a.get('href', ''))) or ptext=='&nbsp;':
				continue
			if p.findParent('i'):
				match = re.match('(\d\d?)\.(\d\d) (a|p)m', ptext)
				if match:
					hour = int(match.group(1))
					if hour<12 and match.group(3) == 'p':
						hour += 12
					timestamp = "%s:%s" % (hour, match.group(2))
					continue
				#if self.speaker[0]:
				#	display_speech()
				#	self.speaker = (None, timestamp)
				match = re.search('(?:\(|\[)(?:Mr|Madam) Deputy Speaker (?:\[|\()(.*?)(?:\]|\))', phtml)
				if match:
					#print "Setting deputy to %s" % match.group(1)
					memberList.setDeputy(match.group(1))
				match = re.match('The Assembly met at (\d\d\.\d\d|noon)', phtml)
				if match:
					if match.group(1) == 'noon':
						timestamp = '12:00'
					else:
						timestamp = match.group(1)
					self.speaker = (self.speaker[0], timestamp)
				self.text += '<p class="italic">%s</p>\n' % phtml
				continue
			if p.findParent('font', size=1):
				self.text += '<p class="small">%s</p>\n' % phtml
				continue
			if (p.get('align', '') == 'center' and (p.b or p.parent.name == 'b')) or (p.parent.name == 'b' and re.search('Stage$', ptext)):
				self.display_speech()
				self.speaker = (None, timestamp)
				aname = p.a and p.a.get('name', '')
				if ptext == 'Oral Answers':
					self.out.write('<oral-heading>\n')
					in_oral_answers = True
					if aname and re.match('#?\d+$', aname):
						self.idA = int(re.match('#?(\d+)$', aname).group(1))
						self.idB = 0
						self.url = '%s#%s' % (self.baseurl, aname)
				elif aname and re.match('#?\d+$', aname):
					if in_oral_answers:
						self.out.write('</oral-heading>\n')
						in_oral_answers = False
					self.idA = int(re.match('#?(\d+)$', aname).group(1))
					self.idB = 0
					self.url = '%s#%s' % (self.baseurl, aname)
					self.display_heading(ptext, timestamp, 'major')
				elif aname:
					self.idB += 1
					self.display_heading(ptext, timestamp, 'major')
				else:
					self.idB += 1
					self.display_heading(ptext, timestamp, 'minor')
				continue
			elif p.b or p.parent.name == 'b':
				if p.b:
					new_speaker = p.b.find(text=True)
				else:
					new_speaker = ptext
				if not re.match('\s*$', new_speaker):
					self.display_speech()
					speaker = re.sub("\s+", " ", new_speaker).strip()
					speaker = re.sub(':', '', speaker)
					id, str = memberList.match(speaker, self.date)
					self.speaker = (str, timestamp)
				if p.b and p.b.nextSibling:
					p.b.extract()
					phtml = re.sub("\s+", " ", p.renderContents()).decode('utf-8')
					self.text += "<p>%s</p>\n" % phtml
				continue
			match = re.match('(\d+)\.$', phtml)
			if match:
				oral_qn = match.group(1)
				continue
			if p.a and re.match('#\d+$', p.a.get('name', '')):
				raise ContextException, 'Uncaught title!'
			if re.match('Mr\w*(\s+\w)?\s+\w+:$', phtml):
				raise ContextException, 'Uncaught speaker! ' + phtml
			if oral_qn:
				phtml = "%s. %s" % (oral_qn, phtml)
				oral_qn = 0
			self.text += "<p>%s</p>\n" % phtml
		self.display_speech()
		if in_oral_answers:
			self.out.write('</oral-heading>\n')
			in_oral_answers = False

	def new_major_heading(self, ptext, timestamp):
		self.display_speech()
		self.speaker = (None, timestamp)
		self.idA += 1
		self.idB = 0
		self.display_heading(ptext, timestamp, 'major')

	def new_minor_heading(self, ptext, timestamp):
		self.display_speech()
		self.speaker = (None, timestamp)
		self.idB += 1
		self.display_heading(ptext, timestamp, 'minor')

	def new_person_speak(self, p, timestamp):
		speaker = p.strong.find(text=True)
		speaker = re.sub('&nbsp;', '', speaker)
		speaker = re.sub("\s+", " ", speaker).strip()
		speaker = re.sub(':', '', speaker)
		id, stri = memberList.match(speaker, self.date)
		self.speaker = (stri, timestamp)
		p.strong.extract()
		phtml = p.renderContents()
		phtml = re.sub('^:\s*', '', phtml)
		phtml = re.sub("\s+", " ", phtml).decode('utf-8')
		self.text += "<p>%s</p>\n" % phtml
		
	def new_italic_speech(self, ptext, phtml):
		match = re.search('\(((?:Mr|Madam) Speaker)', ptext)
		if not match:
			match = re.search('\(Mr (?:Principal )?Deputy Speaker \[(.*?)\]', ptext)
		if match:
			#print "Setting deputy to %s" % match.group(1)
			memberList.setDeputy(match.group(1))
		self.text += '<p class="italic">%s</p>\n' % phtml

	def new_time_period(self, ptext, optional=False):
		match = re.search('(\d\d?)(?:\.\s*(\d\d))? ?(am|pm|noon|midnight)', ptext)
		if not match:
			if not optional:
				raise ContextException, 'Time not found in TimePeriod %s' % p
			return None
		hour = int(match.group(1))
		if hour<12 and match.group(3) == 'pm':
			hour += 12
		if hour==12 and match.group(3) in ('midnight', 'am'):
			hour = 0
		timestamp = "%s:%s" % (hour, match.group(2))
		return timestamp

	def parse_day_new(self, soup, date):
		for s in soup.findAll(lambda tag: tag.name=='strong' and tag.contents == []):
			s.extract()

		self.url = ''

		if date >= '2011-12-12':
			body_div = soup.find('div', 'grid_10') or soup.find('div','grid_7')
			if not body_div:
				raise ContextException, 'Could not find div containing main content.'
			
			body = body_div.findAll('p')

			nia_heading_re = re.compile(r'Session: 2011/2012')
			if not nia_heading_re.match(''.join(body[0](text=True))):
				raise ContextException, 'Missing NIA heading!'
			date_head = body[1].find(text=True)
			body = body[3:] # body[2] is a PDF download link or ISBN
		else:
			body = soup('p')
			nia_heading_re = re.compile(
				r'''
				(the)?(\s|&nbsp;|<br>)*
				(transitional)?(\s|&nbsp;|<br>)*
				(
					northern(\s|&nbsp;|<br>)*
					ireland(\s|&nbsp;|<br>)*
				)?
				assembly
				''',
				re.IGNORECASE | re.VERBOSE
			)
			if not nia_heading_re.match(''.join(body[0](text=True))):
				raise ContextException, 'Missing NIA heading!'

			date_head = body[1].find(text=True)
			body = body[2:]

		timestamp = ''
		self.speaker = (None, timestamp)
		self.text = ''
		for p in body:
			ptext = re.sub("\s+", " ", ''.join(p(text=True)))
			phtml = re.sub("\s+", " ", p.renderContents()).decode('utf-8')
			#print p, "\n---------------------\n"
			if p.a and re.match('[^h/]', p.a.get('href', '')):
				continue
			if re.match('(&nbsp;)+$', ptext) or ptext == '':
				continue
			try:
				cl = p['class']
			except KeyError:
				raise ContextException, 'Missing class on paragraph: %s' %p
			cl = re.sub(' style\d', '', cl)

			if cl == 'OralAnswers':
				# Main heading, or departmental heading (in bold)
				if ptext == 'Oral Answers to Questions' or (p.find('strong', recursive=False) and len(p.contents)==1): cl = 'H3SectionHeading'
				elif re.match('\d+\.( |&nbsp;)+<strong>', phtml): cl = 'B1SpeakersName'
				elif p.strong: raise ContextException, 'Unhandled <strong> found in %s' % p
				else: cl = 'H4StageHeading'
			if cl == 'OralWrittenQuestion' or cl == 'OralAnswers-Question':
				cl = 'B1SpeakersName'
			if cl in ('H1DocumentHeading', 'OralWrittenAnswersHeading', 'OralAnswers-H1Heading', 'WrittenStatement-Heading', 'H3SubHeading', 'OralAnswers-H2DepartmentHeading'):
				cl = 'H3SectionHeading'
			if cl in ('H4StageHeadingCxSpFirst', 'H4StageHeadingCxSpLast', 'OralAnswers-H3SubjectHeading'):
				cl = 'H4StageHeading'
			if cl == 'WrittenStatement-Content' or cl == 'B1BodyText-NumberedList' or cl == 'B2BodyTextBullet1':
				cl = 'B3BodyText'
			if cl == 'B3BodyText' and (phtml[0:8] == '<strong>' or re.match('\d+\.( |&nbsp;)+<strong>', phtml)):
				cl = 'B1SpeakersName'
			if cl == 'TimePeriod' and re.search('in the chair(?i)', phtml):
				cl = 'B3SpeakerinChair'
			if cl == 'B1BodyTextQuote':
				cl = 'B3BodyTextItalic'
			if p.em and len(p.contents) == 1:
				cl = 'B3BodyTextItalic'

			if cl == 'H3SectionHeading':
				self.new_major_heading(ptext, timestamp)
			elif cl == 'H4StageHeading' or cl == 'H5StageHeading' or cl == 'B3BodyTextClause':
				self.new_minor_heading(ptext, timestamp)
			elif cl == 'B1SpeakersName':
				self.display_speech()
				m = re.match('.*?:', phtml)
				if not p.strong and m:
					newp = Tag(soup, 'p', [('class', 'B1SpeakersName')])
					newspeaker = Tag(soup, 'strong')
					newspeaker.insert(0, m.group())
					newp.insert(0, phtml.replace(m.group(), ''))
					newp.insert(0, newspeaker)
					p = newp
				m = re.match('([0-9]+\. )(.*?) asked', phtml)
				if not p.strong and m:
					newp = Tag(soup, 'p', [('class', 'B1SpeakersName')])
					newspeaker = Tag(soup, 'strong')
					newspeaker.insert(0, m.group(2))
					newp.insert(0, phtml.replace(m.group(), ' asked'))
					newp.insert(0, newspeaker)
					newp.insert(0, m.group(1))
					p = newp
				if re.search("<strong>O(&rsquo;|')Neill\)?</strong>", phtml):
					newp = Tag(soup, 'p', [('class', 'B1SpeakersName')])
					newspeaker = Tag(soup, 'strong')
					newspeaker.insert(0, re.sub('</?strong>', '', m.group()))
					newp.insert(0, phtml.replace(m.group(), ''))
					newp.insert(0, newspeaker)
					p = newp
				if not p.strong:
					raise ContextException, 'No strong in p! %s' % p
				self.new_person_speak(p, timestamp)
			elif cl in ('B3BodyTextItalic', 'Q3Motion', 'BillAmend-AmendedText', 'BillAmend-Moved', 'BillAmend-withMinister', 'BillAmend-AmendMade', 'BillAmend-ClauseHeading', 'AyesNoes', 'AyesNoesParties', 'AyesNoesVotes', 'D3PartyMembers', 'B3SpeakerinChair', 'B3BodyTextSpeakerintheChair', 'H2DocumentStartTime', 'AyesNoesDivisionTellers', 'CommunityVoteTable'):
				match = re.match('The Assembly met at ((\d\d?)\.(\d\d) (am|pm)|noon)', phtml)
				if match:
					if match.group(1) == 'noon':
						timestamp = '12:00'
					else:
						hour = int(match.group(2))
						if hour<12 and match.group(4) == 'pm':
							hour += 12
						timestamp = "%s:%s" % (hour, match.group(3))
					self.speaker = (self.speaker[0], timestamp)
				self.new_italic_speech(ptext, phtml)
			elif cl in ('Q3MotionBullet', 'BillAmend-AmendedTextIndent', 'BillAmend-AmendedTextIndent2', 'BillAmend-AmendedTextIndent3', 'BillAmend-QuotewithMinister'):
				self.text += '<p class="indentitalic">%s</p>\n' % phtml
			elif cl in ('B3BodyText', 'B3BodyTextnoindent', 'RollofMembersList', 'TableText'):
				self.text += '<p>%s</p>\n' % phtml
			elif cl == 'Q1QuoteIndented' or cl == 'Q1Quote':
				self.text += '<p class="indent">%s</p>\n' % phtml
			elif cl == 'TimePeriod':
				timestamp = self.new_time_period(ptext)
			elif cl == 'MsoNormal':
				continue
			else:
				raise ContextException, 'Uncaught paragraph! %s %s' % (cl, p)
		self.display_speech()

	def parse_day_new_new(self, soup, date):
		for s in soup.findAll(lambda tag: tag.name=='strong' and tag.contents == []):
			s.extract()

		self.url = ''

		body_div = soup.find('div', 'grid_10')
		if not body_div:
			raise ContextException, 'Could not find div containing main content.'
		body = [ x for x in body_div.contents if isinstance(x, Tag) ]

		bbody = []
		for t in body:
			if t.name == 'div' and t['class'] in ('WordSection1', 'WordSection2'):
				sub_body = [ x for x in t.contents if isinstance(x, Tag) ]
				bbody.extend(sub_body)
			else:
				bbody.append(t)
		body = bbody

		assert body[0].string == 'Official Report (Hansard)'
		nia_heading_re = re.compile(r'\s*Session: 201[1-4]/201[2-5]')
		first_line = ''.join(body[1](text=True))
		if not nia_heading_re.match(first_line):
			raise ContextException, 'Missing NIA heading! Got %s' % first_line
		body = body[3:] # body[2] is a PDF download link or ISBN

		for i in range(0, len(body)):
			if body[i].name == 'h2':
				break
		body = body[i:] # Contents before first h2

		timestamp = ''
		self.speaker = (None, timestamp)
		self.text = ''
		for p in body:
			ptext = re.sub("\s+", " ", ''.join(p(text=True)))
			phtml = re.sub("\s+", " ", p.renderContents()).decode('utf-8')
			#print str(p).decode('utf-8'), "\n---------------------\n"
			if p.a and re.match('[^h/]', p.a.get('href', '')):
				continue
			if ptext == '&nbsp;' or ptext == '':
				continue

			if p.name == 'h2':
				self.new_major_heading(ptext, timestamp)
			elif p.name == 'h3':
				self.new_minor_heading(ptext, timestamp)
			elif phtml[0:8] == '<strong>' or re.match('T?\d+\.( |&nbsp;)*<strong>', phtml):
				new_timestamp = self.new_time_period(ptext, optional=True)
				if new_timestamp:
					timestamp = new_timestamp
					continue
				if p.strong and len(p.contents)==1:
					self.new_minor_heading(ptext, timestamp)
					continue
				self.display_speech()
				self.new_person_speak(p, timestamp)
			elif p.em and len(p.contents) == 1:
				self.new_italic_speech(ptext, phtml)
			elif p.string or p.a:
				self.text += '<p>%s</p>\n' % phtml
			elif p.name == 'table' or p.name == 'ul':
				self.text += re.sub("\s+", " ", unicode(p))
			elif re.match('([^<]|<em>|</em>|<a name[^>]*>|</a>)+$', phtml):
				self.text += '<p>%s</p>\n' % phtml
			else:
				raise ContextException, 'Uncaught paragraph! %s' % p
		self.display_speech()

