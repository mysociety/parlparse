#!/usr/bin/python

# A very experimental program to parse votes and proceedings files.

# At the moment this file contains absolute paths, until someone can show me
# how to avoid them. Hence is unlikely to be unuseable.

import sys
import re
import parselib
from parselib import SEQ, OR,  ANY, POSSIBLY, IF, START, END, OBJECT, NULL, OUT, DEBUG, STOP, pattern


def htmlpar(f):
	return SEQ(pattern('\s*<p>'), f, pattern('</p>'))

htmlul=lambda f:SEQ(pattern('<ul>'), f, pattern('</ul>'))

archtime=pattern('half-past\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*o\'clock(?i)')

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

prayers=pattern('\s*(<p>)?PRAYERS.(</p>)?\s*')


NPAR=pattern('\s*<p>(?P<number>\d+)(&nbsp;)*(?P<maintext>[\s\S]*?)</p>')

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

minute=SEQ(
	DEBUG('minute'),
	NPAR, 
	DEBUG('matched npar'),
	START('minute','number'),
	OBJECT('maintext', 'maintext'),
	ANY(OR(IPAR,dateheading)),
	#ANY(OR(IPAR)),
	END('minute'))

adjournment=SEQ(
	DEBUG('attempting to match adjournment'),
	pattern('\s*(<p( align=right)?>)?\[Adjourned at (?P<time>\s*(\d+(\.\d+)?\s*(a\.m\.|p\.m\.)|12\s*midnight(\.)?))\s*(</p>)?'),
	OBJECT('adjournment','','time')
	)

print IF

speaker_address=pattern('\s*<p><ul>Mr Speaker,</ul></p>\s*<p><ul>The Lords, authorised by virtue of Her Majesty\'s Commission, for declaring Her Royal Assent to several Acts agreed upon by both Houses and for proroguing the present Parliament, desire the immediate attendance of this Honourable House in the House of Peers, to hear the Commission read.</ul></p>')

royal_assent=SEQ(
	DEBUG('started royal assent parsing'),
	pattern('\s*<p><ul>Accordingly the Speaker, with the House, went up to the House of Peers, where a Commission was read, giving, declaring and notifying the Royal Assent to several Acts, and for proroguing this present Parliament.</ul></p>\s*<p><ul>The Royal Assent was given to the following Acts:-</ul></p>'),
	DEBUG('parsed "Accordingly the Speaker"'),
	ANY(SEQ(
		pattern('\s*<p><ul><ul>(?P<shorttitle>[-a-z.,A-Z()\s]*?Act)\s*(?P<year>\d+)(\.)?</ul></ul></p>'),
		OBJECT('act','','shorttitle','year')
		))
	)

royal_speech=SEQ(	
	DEBUG('starting the royal speech'),
	pattern('\s*<p><ul>And afterwards Her Majesty\'s Most Gracious Speech was delivered to both Houses of Parliament by the Lord High Chancellor \(in pursuance of Her Majesty\'s Command\), as follows:</ul></p>'),
	DEBUG('royal speech: My Lords'),
	parselib.TRACE(True),
	pattern('\s*<p><ul>My Lords and Members of the House of Commons(,)?</ul></p>[\s\S]*?<p><ul>I pray that the blessing of Almighty God may attend you.\s*</ul></p>'),
	parselib.TRACE(True),
	DEBUG('finished the royal speech')
	)

words_of_prorogation=SEQ(
	pattern('\s*<p><ul>After which the Lord Chancellor said:</ul></p>'),
	pattern('\s*<p><ul>My Lords and Members of the House of Commons(,)?</ul></p>'),
	DEBUG('and now by virtue of...'),
	pattern('\s*<p><ul>By virtue of Her Majesty\'s Commission which has now been read we do, in Her Majesty\'s name, and in obedience to Her Majesty\'s Commands, prorogue this Parliament to (?P<pdate1>[-a-zA-Z\s]*), to be then here holden, and this Parliament is accordingly prorogued to (?P<pdate2>[-a-zA-Z\s]*).</ul></p>')
	)

prorogation=IF(
	pattern('\s*<p>\d+&nbsp;&nbsp;&nbsp;&nbsp;Message to attend the Lords Commissioners,-A Message from the Lords Commissioners was delivered by the Gentleman Usher of the Black Rod\.</p>'),
	SEQ(
		DEBUG('start prorogation'),
		START('prorogation'),
		speaker_address,
		royal_assent,
		DEBUG('parsed royal assents'),
		royal_speech,
		DEBUG('parsed royal speech'),
		words_of_prorogation,
		DEBUG('parsed words of prorogation'),
		END('prorogation')
		)
	)

speaker_signature=SEQ(
	OR(
		pattern('\s*<p align=right><b><i><font size=\+2>(?P<speaker>[\s\S]*?)</font></i></b><br>\s*<b><i><font size=\+1>(?P<title>(Deputy )?Speaker)\s*</font></i></b></p>'),
		pattern('\s*<p( align=right)?>(<font size=\+1>)?<i><b>(?P<speaker>[a-zA-Z. ]*?)(&nbsp;)*</i>(</font>)?(</b>)?(</p>\s*<p( align=right)?>|<br>\s*)<i><b>\s*(?P<title>(Deputy )?Speaker)(&nbsp;|\s)*(</i></b>\s*</p>)?')
	),
	OBJECT('speaker_signature','','speaker')
	)

speaker_chair=SEQ(
	pattern('\s*<p align=center>Mr Speaker will take the Chair at '),
	archtime,
	POSSIBLY(SEQ(pattern('\s*on\s*'),OR(plaindate,futureday))),
	pattern('.</p>\s*')
	)

appendix_title=pattern('(<p align=center>)?APPENDIX\s*(?P<appno>(|I|II|III))(</p>)?(?=</)')
	

app_title=SEQ(
	htmlpar(OR(htmlul(appendix_title),appendix_title)),
	START('appendix','appno')
	)

app_heading=SEQ(
	pattern('\s*<p><ul><i>(?P<desc>[\s\S]*?)</i></ul></p>'),
	OBJECT('app_heading', 'desc')
	)

app_date=SEQ(
	pattern('\s*<p align=center>'),
	idate,
	pattern('\s*</p>'),
	OBJECT('date','','dayname','day','monthname','year')
	)


app_nopar=SEQ(
	pattern('\s*<p><ul>(?P<no>\d+)&nbsp;&nbsp;&nbsp;&nbsp;(?P<maintext>[\s\S]*?)</ul></p>'),
	OBJECT('app_nopar','','no', 'maintext')
	)

misc_par=SEQ(
	pattern('\s*<p><ul>(?P<maintext>[\s\S]*?)</ul></p>'),
	OBJECT('miscpar','maintext')
	)

app_par=misc_par

app_subheading=SEQ(
	pattern('\s*<p><i>(?P<maintext>[\s\S]*?)</i></p>'),
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
	ANY(OR(
		app_nopar,
		app_heading,
		app_date,
		app_subheading,
		app_nosubpar,
		app_date_sep,
		attr_sep,
		app_par,
		emptypar
		)),
	END('appendix')
	)

westminsterhall=SEQ(
	pattern('\s*(<p>\s*<\p>|<p>\s*<p>)?\s*<p( align=center)?>\[W.H., No. (?P<no>\d+)\]</p>'),
	pattern('\s*<p( align=center)?>(<font size=\+1>)?<b>Minutes of Proceedings of the Sitting in Westminster Hall(</font>)?</b>(</p>|<br>)'),
	pattern('\s*(<p>)?<b>\[pursuant to the Order of '),
	plaindate,
	pattern('\]</b></p>'),
	pattern('\s*<p( align=center)?>The sitting commenced at '),
	archtime,
	pattern('.</p>'),
	ANY(misc_par),
	adjournment,
	speaker_signature)	

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
	pattern('\s*<p>CORRIGENDA</p>\s*'),
	ANY(pattern('\s*<p><ul>[\s\S]*?</ul></p>'))
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
	POSSIBLY(O13notice),
	#O13notice,
	time,
	prayers,
## prayers don't necessary come first (though they usually do)
	ANY(OR(prayers,minute),
		until=SEQ(prorogation, speaker_signature),
		otherwise=SEQ(adjournment, speaker_signature, speaker_chair)), 
	DEBUG('now check for appendices'),
	ANY(appendix),
	POSSIBLY(westminsterhall),
	#westminsterhall,
	POSSIBLY(certificate),
	POSSIBLY(corrigenda),
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
