#!/usr/bin/python

# A very experimental program to parse votes and proceedings files.

# At the moment this file contains absolute paths, until someone can show me
# how to avoid them. Hence is unlikely to be unuseable.

import sys
import re
import parselib
from parselib import SEQ, OR,  ANY, POSSIBLY, IF, START, END, OBJECT, NULL, OUT, DEBUG, STOP, FORCE, pattern, tagged


def htmlpar(f):
	return SEQ(pattern('\s*<p>'), f, pattern('</p>'))

htmlul=lambda f:SEQ(pattern('<ul>'), f, pattern('</ul>'))

def namepattern(label='name'):
	return '(?P<'+label+'>[-A-Za-z .]+)'

archtime=pattern('(?P<archtime>half-past\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*o\'clock)(?i)')

dayname=pattern('\s*(?P<dayname>(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\s*')

monthname=pattern('\s*(?P<monthname>(January|February|March|April|May|June|July|August|September|October|November|December))\s*')

year=pattern('(?P<year>\d{4})\s*')

dayordinal=pattern('\s*(?P<day>\d+(st|nd|rd|th))\s*')

futureday=SEQ(dayname,pattern('\s*next\s*'))

idate=SEQ(
	pattern('\s*<i>\s*'),
	dayname,
	pattern('\s*</i>\s*'),
	OR(
		pattern('(?P<day>\d+)<i>(st|nd|rd|th)\s*'),
		pattern('(?P<day>\d+)(st|nd|rd|th)\s*<i>\s*')
	),
	monthname,
	pattern('\s*</i>\s*'),
	year
	)

#idate=pattern('(?P<date>\s*<i>(?P<dayname>(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\s*</i>\s*(?P<day>\d+)\s*<i>(st|nd|rd|th)\s*(?P<monthname>(January|February|March|April|May|June|July|August|September|October|November|December))\s*</i>\s*(?P<year>\d{4}))')

plaindate=SEQ(POSSIBLY(dayname), dayordinal, monthname, POSSIBLY(year))

header=SEQ(
	pattern('(?P<pagex><pagex [\s\S]*?/>)'),
	OUT('pagex'),
	pattern('\s*</td></tr>\s*</table>\s*<table width="90%"\s*cellspacing=6 cols=2 border=0>\s*<tr><td>\s*</font><p>\s*(?i)'))


time=SEQ(
	pattern('\s*<p(?: align=center)?>The House met at (?P<texttime>[\s\S]*?).</p>'),
	OBJECT('time','','texttime')
	)


speaker_signature=SEQ(
	tagged(first='\s*',
		tags=['p','b','i','font'],
		p='(?P<speaker>[a-zA-Z. ]+)(&nbsp;)*',padding='\s'),
	tagged(first='\s*',
		tags=['p','b','i','font'],
		p='(?P<title>(Deputy )?Speaker)(&nbsp;|\s)*',padding='\s'),
	OBJECT('speaker_signature','','speaker')
	)

prayers=pattern('\s*(<p>)?PRAYERS.(</p>)?\s*')

paragraph_number='\s*<p>(?P<number>\d+)(&nbsp;)*'


heading=SEQ(
	pattern('\s*(<p><ul>|<p align=center>)<i>(?P<desc>[\s\S]*?)</i>(</ul>)?</p>'),
	OBJECT('heading', 'desc')
	)

NPAR=pattern(paragraph_number+'(?P<maintext>[\s\S]*?)</p>')

IPAR=SEQ(
	pattern('\s*<p><ul>(?P<maintext>[\s\S]*?)</ul></p>'),
	START('indent'),
	OBJECT('maintext', 'maintext'),
	END('indent')
	)

dateheading=SEQ(
	DEBUG('check date heading'),
	pattern('\s*<p>'),
	DEBUG('consumed p'),
	idate,
	DEBUG('found idate'),
	pattern('\s*</p>'),
	DEBUG('dateheading matched'),
	OBJECT('dateheading','dayname','day','monthname','year')
	)


untagged_par=SEQ(
	DEBUG('checking for untagged paragraph'),
	parselib.TRACE(True),
	pattern('\s*(?P<maintext>(?!\s*\[Adjourned)([^<]|<i>|</i>)+)'),
	OBJECT('untagged_par','maintext')
	)

minute_plain=SEQ(
	NPAR, 
	START('minute','number'),
	OBJECT('maintext', 'maintext'),
	ANY(OR(IPAR,dateheading,untagged_par)),
	END('minute'))

division=SEQ(
	parselib.TRACE(True),
	pattern('\s*<p><ul>The House divided(\.)?</ul></p>'),
	DEBUG('matched division'),
	FORCE(SEQ(
		parselib.TRACE(True),
		pattern('\s*<p><ul><ul>Tellers for the Ayes, '+namepattern('ayeteller1')+', '+namepattern('ayeteller2')+': (?P<ayevote>\d+)(\.)?</ul></ul></p>'),
		DEBUG('ayeteller1'),
		pattern('\s*<p><ul><ul>Tellers for the Noes, '+namepattern('noteller1')+', '+namepattern('noteller2')+'(:)?\s*(?P<novote>\d+)(\.)?</ul></ul></p>'),
		DEBUG('ayeteller2'),
		pattern('\s*<p><ul>So the Question was agreed to\.</ul></p>')
		)),
	OBJECT('division','ayevote','novote','ayeteller1','ayeteller2','noteller1','noteller2')
	)

programme_minute=SEQ(
	pattern('\s*<p><ul>\d+\.\s*([^<]|<i>|</i>)*</ul></p>'),
	OBJECT('programme_minute','')
	)

minute_programme=SEQ(
	pattern(paragraph_number+'(?P<maintext>[\s\S]*?the following provisions shall apply to (proceedings on )?the (?P<bill>[\s\S]*?Bill)( \[<i>Lords</i>\])?(-|:)?)</p>'),
	parselib.TRACE(False),
	START('bill_programme','bill'),
	FORCE(SEQ(
		DEBUG('matched the start of a Bill programme'),
		ANY(OR(
			heading,
			programme_minute,
			)),
		POSSIBLY(division)
		)),
	END('bill_programme')
	)

minute=OR(
	minute_programme,
	minute_plain,
	)


adjournment=SEQ(
	DEBUG('attempting to match adjournment'),
	pattern('\s*(<p( align=right)?>)?\[Adjourned at (?P<time>\s*(\d+(\.\d+)?\s*(a\.m\.|p\.m\.)|12\s*midnight(\.)?))\s*(</p>)?'),
	OBJECT('adjournment','','time')
	)

speaker_address=pattern('\s*(<p><ul>)?Mr Speaker(,|\.)(</ul></p>)?\s*<p><ul>The Lords, authorised by virtue of Her Majesty\'s Commission, for declaring Her Royal Assent to several Acts agreed upon by both Houses(, and under the Parliament Acts 1911 and 1949)? and for proroguing the present Parliament, desire the immediate attendance of this Honourable House in the House of Peers, to hear the Commission read.</ul></p>')

actpattern=SEQ(
	pattern('\s*<p><ul><ul>(?P<shorttitle>[-a-z.,A-Z0-9()\s]*?Act)\s*(?P<year>\d+)(\.)?</ul></ul></p>'),
	OBJECT('act','','shorttitle','year')
	)

royal_assent=SEQ(
	START('royal_assent'),
	pattern('\s*<p><ul>Accordingly the Speaker, with the House, went up to the House of Peers, where a Commission was read(,)? giving, declaring and notifying the Royal Assent to several Acts, and for proroguing this present Parliament.</ul></p>'),
	DEBUG('the royal assent...'),
	pattern('\s*(<p><ul>)?The Royal Assent was given to the following Acts( agreed upon by both Houses)?:(-)?(</ul></p>)?'),
	DEBUG('parsed "Accordingly the Speaker"'),
	ANY(actpattern),
	POSSIBLY(SEQ(
		START('parlact'),
		DEBUG('attempting to match parliament act'),
		parselib.TRACE(False),
		pattern('\s*The Royal Assent was given to the following Act, passed under the provisions of the Parliament Acts 1911 and 1949:'),
		actpattern,
		pattern('\s*\(The said Bill having been endorsed by the Speaker with the following Certificate:</p><p>'),
		pattern('\s*I certify, in reference to this Bill, that the provisions of section two of the Parliament Act 1911, as amended by section one of the Parliament Act 1949, have been duly complied with.</p>'),
		speaker_signature,
		pattern('\.\)\s*</p>'),
		END('parlact')
		)),
	END('royal_assent')
	)

royal_speech=SEQ(	
	DEBUG('starting the royal speech'),
	pattern('\s*<p>\s*(<ul>)?And afterwards Her Majesty\'s Most Gracious Speech was delivered to both Houses of Parliament by the Lord High Chancellor \(in pursuance of Her Majesty\'s Command\), as follows:(</ul>)?</p>'),
	DEBUG('royal speech: My Lords'),
	parselib.TRACE(False),
	pattern('\s*<p>\s*(<ul>)?My Lords and Members of the House of Commons(,)?(</ul>)?</p>'),
	pattern('(?P<royalspeech>[\s\S]*?)<p>\s*(<ul>)?I pray that the blessing of Almighty God may (attend you|rest upon your counsels)\.\s*(</ul>)?</p>'),
	DEBUG('end of royal speech'),
	parselib.TRACE(False),
	DEBUG('finished the royal speech'),
	OBJECT('royalspeech','royalspeech')
	)

words_of_prorogation=SEQ(
	pattern('\s*<p>\s*(<ul>)?After which the Lord Chancellor said:(</ul>)?</p>'),
	pattern('\s*<p>\s*(<ul>)?My Lords and Members of the House of Commons(,|:)?(</ul>)?</p>'),
	DEBUG('and now by virtue of...'),
	pattern('\s*<p>\s*(<ul>)?By virtue of Her Majesty\'s Commission which has now been read(,)? we do, in Her Majesty\'s name, and in obedience to Her Majesty\'s Commands, prorogue this Parliament to (?P<pdate1>[-a-zA-Z\s]*)(,)? to be then here holden, and this Parliament is accordingly prorogued to (?P<pdate2>[-a-zA-Z\s]*)\.(</ul>)?</p>'),
	DEBUG('parliament prorogued')
	)

prorogation=SEQ(IF(
	pattern('\s*<p>\d+&nbsp;&nbsp;&nbsp;&nbsp;Message to attend the Lords Commissioners,-A Message from the Lords Commissioners was delivered by the Gentleman Usher of the Black Rod\.</p>'),
	FORCE(SEQ(
		DEBUG('start prorogation'),
		START('prorogation'),
		speaker_address,
		royal_assent,
		DEBUG('parsed royal assents'),
		royal_speech,
		DEBUG('parsed royal speech'),
		words_of_prorogation,
		DEBUG('parsed words of prorogation'),
		speaker_signature,
		END('prorogation')
		))
	),
	DEBUG('prorogation success')
	)

#speaker_signature=SEQ(
#	OR(
#		pattern('\s*<p align=right><b><i><font size=\+2>(?P<speaker>[\s\S]*?)</font></i></b></p>\s*<b><i><font size=\+1>(?P<title>(Deputy )?Speaker)\s*</font></i></b></p>'),
#		pattern('\s*<p( align=right)?>(<font size=\+1>)?<i><b>(?P<speaker>[a-zA-Z. ]*?)(&nbsp;)*</i>(</font>)?(</b>)?</p>\s*(<p( align=right)?>)?\s*<i><b>\s*(?P<title>(Deputy )?Speaker)(&nbsp;|\s)*(</i></b>\s*</p>)?')
#	),
#	OBJECT('speaker_signature','','speaker')
#	)
#

speaker_chair=SEQ(
	pattern('\s*<p align=center>Mr Speaker will take the Chair at '),
	archtime,
	POSSIBLY(SEQ(pattern('\s*on\s*'),OR(plaindate,futureday))),
	pattern('.</p>\s*')
	)

#appendix_title=pattern('(<p align=center>)?APPENDIX\s*(?P<appno>(|I|II|III))(</p>)?(?=</)')
#	
#
#app_title=SEQ(
#	htmlpar(OR(htmlul(appendix_title),appendix_title)),
#	START('appendix','appno')
#	)
#

app_title=SEQ(
	DEBUG('checking for app_title'),
	parselib.TRACE(False),
	tagged(first='\s*',
		tags=['p','ul'],
		p='(<p align=center>)?APPENDIX\s*(?P<appno>(|I|II|III))(</p>)?(?=</)'
	),
	DEBUG('starting object appendix'),
	START('appendix','appno')
	)

app_heading=heading

app_date=SEQ(
	pattern('\s*<p align=center>'),
	idate,
	pattern('\s*</p>'),
	OBJECT('date','','dayname','day','monthname','year')
	)


app_nopar=SEQ(
	pattern('\s*<p>(<ul>)?(?P<no>\d+)&nbsp;&nbsp;&nbsp;&nbsp;(?P<maintext>[\s\S]*?)(</ul>)?</p>'),
	OBJECT('app_nopar','','no', 'maintext')
	)

misc_par=SEQ(
	pattern('\s*<p>\s*(<ul>)?(?P<maintext>(?!\[W\.H\.|\[Adjourned)([^<]|<i>|</i>)*)(</ul>)?(</p>)?'),
	OBJECT('miscpar','maintext')
	)

app_par=misc_par

app_subheading=SEQ(
	pattern('\s*<p( align=left)?><i>(?P<maintext>[\s\S]*?)</i></p>'),
	OBJECT('app_subhead','','maintext')
	)

app_nosubpar=SEQ(
	pattern('\s*<p><ul>\(\d+\)[\s\S]*?</ul></p>')
	)

#date accidently put in a separate paragraph

app_date_sep=pattern('\s*<p><ul>dated [\s\S]*?\[[a-zA-Z ]*\].</ul></p>')

attr_sep=pattern('\s*<p><ul>\[by Act\]\s*\[[\s\S]*?\].</ul></p>')

emptypar=pattern('\s*<p>\s*</p>\s*(?i)')

appendix=SEQ(
	app_title,
	DEBUG('after app_title'), 
	ANY(OR(
		app_nopar,
		app_heading,
		app_date,
		app_subheading,
		app_nosubpar,
		app_date_sep,
		attr_sep,
		app_par,
		emptypar,
		untagged_par
		)),
	END('appendix'),
	DEBUG('ended appendix')
	)

westminsterhall=SEQ(
	START('westminsterhall'),
	pattern('\s*(<p>\s*<\p>|<p>\s*<p>)?\s*<p( align=center)?>\[W.H., No. (?P<no>\d+)\]</p>'),
	pattern('\s*<p( align=center)?>(<font size=\+1>)?<b>Minutes of Proceedings of the Sitting in Westminster Hall(</font>)?</b></p>'),
	POSSIBLY(SEQ(
		pattern('\s*(<p>)?<b>\[pursuant to the Order of '),
		plaindate,
		pattern('\]</b></p>'),
		)),
	pattern('\s*<p( align=center)?>The sitting (commenced|began) at '),
	archtime,
	OBJECT('commencement','','archtime'),
	pattern('.</p>'),
	ANY(SEQ(parselib.TRACE(False),misc_par), until=adjournment),
	#adjournment,
	speaker_signature,
	END('westminsterhall'))	

certificate=NULL

endpattern=pattern('\s*</td></tr>\s*</table>\s*')

O13notice=SEQ(
	START('O13notice'),
	pattern('\s*<p align=center>_______________</p>'),
	pattern('\s*<p><ul><i>Notice given by the Speaker, pursuant to Standing Order No. 13 \(Earlier meeting of House in certain circumstances\):</i></ul></p>'),
	ANY(
		SEQ(
			DEBUG('misc paragraphs'),
			pattern('\s*<p><ul>(?P<text>[\s\S]*?)</ul></p>'),
			OBJECT('par','text')
		)
	),
	speaker_signature,
	POSSIBLY(pattern('\s*</table>(?i)')),
	POSSIBLY(pattern('\s*<p align=center>_________________________________________</p></center>')),
	pattern('\s*(<p>|<tr><td>)<FONT size=\+2><B><CENTER>(?P<date>[\s\S]*?)</B></CENTER></FONT>\s*(</p>|</td></tr>)(?i)'),
	pattern('\s*<TABLE WIDTH="90%" CELLSPACING=6 COLS=2 BORDER=0>\s*<TR><TD>(?i)'),
	END('O13notice')
	)

corrigenda=SEQ(
	pattern('\s*<p( align=center)?>CORRIGEND(A|UM)</p>\s*'),
	START('corrigenda'),
	ANY(
		OR(
			pattern('\s*<p><ul>[\s\S]*?</ul></p>'),
			untagged_par
			)
	),
	END('corrigenda')
	)

footnote=SEQ(
	pattern('\s*Votes and Proceedings:'),
	plaindate,
	pattern('\s*No. \d+')
	)

page=SEQ(
	START('page'),
	header, 
	POSSIBLY(pattern('\s*<p><b>Votes and Proceedings</b></p>')),
	POSSIBLY(O13notice), #O13notice,
	time,
	prayers,
## prayers don't necessary come first (though they usually do)
	ANY(
		SEQ(parselib.TRACE(False),OR(prayers,minute)),
		until=prorogation, 
		otherwise=SEQ(adjournment, speaker_signature, speaker_chair)), 
	DEBUG('now check for appendices'),
	ANY(appendix),
	POSSIBLY(westminsterhall), 
	#westminsterhall,
	POSSIBLY(certificate),
	POSSIBLY(corrigenda), #corrigenda,
	POSSIBLY(footnote),
	POSSIBLY(pattern('(\s|<p>|</p>)*(?i)')),
	DEBUG('endpattern'),
	endpattern,
	END('page')
	)

votedir='/home/Francis/project/parldata/cmpages/votes'

def parsevote(date):
	name='votes%s.html' % date
	f=open(votedir+'/'+name) # do not do this
	s=f.read()
	# I am not sure what the <legal 1> tags are for. At present
	# it seems safe to remove them.
	s=s.replace('<legal 1>','<p><ul>')
	s=s.replace('<br><br>','</p><p>')
	s=s.replace('<br>','</p>')
	s=s.replace('&#151;','-')
	return page(s,{})

date=sys.argv[1]
(s,env,result)=parsevote(date)


if result.success:
	print result.text()

	fout=open('votes%s.xml' % date,'w')
	fout.write(result.text())
else:
	print "failure"
	print result.text()
	print "----"
	print s[:128]
