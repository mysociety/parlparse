#!/usr/bin/python
# vim:sw=8:ts=8:et:nowrap

# A very experimental program to parse votes and proceedings files.

# At the moment this file contains absolute paths, until someone can show me
# how to avoid them. Hence is unlikely to be unuseable.

import sys
import os
import os.path
import re
import fd-parse
import fd-dates
from dates import *

from parselib import SEQ, OR,  ANY, POSSIBLY, IF, START, END, OBJECT, NULL, OUT, DEBUG, STOP, FORCE, CALL, pattern, tagged

sys.path.append("../")
from xmlfilewrite import WriteXMLHeader
from contextexception import ContextException

# Names may have dots and hyphens in them.
def namepattern(label='name'):
	return "(?P<"+label+">[-A-Za-z .']+)"

emptypar=pattern('\s*<p>\s*</p>\s*(?i)')
emptypar2=pattern('\s*<p><ul>\s*</ul></p>\s*')

# characters that may be allowed in a bill or act
actpattern='[-a-z.,A-Z0-9()\s]*?' 

act=SEQ(
	pattern('\s*<p><ul>(<ul>)?(?P<shorttitle>'+actpattern+' Act)\s*(?P<year>\d+)(\.)?(</ul>)?</ul></p>'),
	OBJECT('act','','shorttitle','year')
	)

measurepattern=SEQ(
	pattern('\s*<p><ul>(<ul>)?(?P<shorttitle>[-a-z.,A-Z0-9()\s]*?Measure)\s*(?P<year>\d+)(\.)?</ul>(</ul>)?</p>'),
	OBJECT('measure','','shorttitle','year')
	)


header=SEQ(
	pattern('(?P<pagex><pagex [\s\S]*?/>)'),
	OUT('pagex'),
	pattern('\s*</td></tr>\s*</table>\s*<table width="90%"\s*cellspacing=6 cols=2 border=0>\s*<tr><td>\s*</font><p>\s*(?i)'))


meeting_time=SEQ(
	START('opening'),
	pattern('\s*(<p>1&nbsp;&nbsp;&nbsp;&nbsp;|<p(?: align=center)?>)The House met at\s*'),
	parselib.TRACE(True),
	archtime,
	parselib.TRACE(True),
	OR(
		pattern('\s*\.'),
		pattern('; and the Speaker Elect having taken the Chair;')
		),
	pattern('</p>'),
	END('opening')
	)


speaker_signature=SEQ(
	tagged(first='\s*',
		tags=['p','b','i','font'],
		p="(?P<speaker>[-a-zA-Z.' ]+)",
		padding='\s|&nbsp;',
		last='(<font size=3>|\s|</p>)*'),
	tagged(first='\s*',
		tags=['p','b','i','font'],
		p='(?P<title>(Deputy )?Speaker(\s*Elect)?)(&nbsp;|\s)*',
		padding='\s|&nbsp;'),
	OBJECT('speaker_signature','','speaker')
	)

prayers=pattern('\s*(<p>)?PRAYERS.(</p>)?\s*')

paragraph_number='\s*<p>(?P<number>\d+)(&nbsp;)*'


heading=SEQ(
	pattern('\s*(<p><ul>|<p align=center>)<i>(?P<desc>([^<]|<i>|</i>)*?)(</ul>)?</p>'),
	OBJECT('heading', 'desc')
	)

minute_main=pattern(paragraph_number+'(?P<minute_text>[\s\S]*?)</p>')

maintext=SEQ(
	pattern('(?P<maintext>([^<]|<i>|</i>)+)'),
	OBJECT('maintext','maintext')
	)

def process_minute():
	def anon(s,env):

		if len(env['second'])> 0:
			print "second reading"
		return (s,env,Success())
	return anon
minute_order=SEQ(
	pattern('\s*<ul><i>Ordered</i>(,)?(?P<text>([^<])*)</ul></p>'),
	OBJECT('order','','text')
	)

bill_second=SEQ(
	pattern('; and ordered to be read a second time '),
	futureday,
	OBJECT('second_reading_scheduled','','billname')
	) 

first_reading=SEQ(
	DEBUG('checking minute bill'),
	parselib.TRACE(True,vals=['minute_text']),
	pattern('''(?P<billname>'''+actpattern+''' Bill),-(?P<sponsor>[-A-Za-z'. ]*?)((,)? supported by (?P<supporters>[-A-Za-z'., ]*?))?(,)? presented (\(under Standing Order No\. 50 \(Procedure upon bills whose main object is to create a charge upon the public revenue\)\) )?(a Bill to [\s\S]*?)(:)?\s*And the same was read the first time'''),
	DEBUG('matched bill'),
	parselib.TRACE(True),
	POSSIBLY(bill_second),
	DEBUG('checked bill second'),
	parselib.TRACE(False),
	pattern('\s*and to be printed \[\s*Bill\s*(?P<billno>\d+)\s*\](\.)?'),
	OBJECT('first_reading','','billname','sponsor','billno'), #process_minute(),
	parselib.TRACE(False),
	)

second_reading1=SEQ(
	pattern('''(?P<billname>'''+actpattern+''') Bill,-The ''' + actpattern + ''' Bill was(,)? according to Order(,)? read a second time and stood committed to a Standing Committee(\.)?'''),
	OBJECT('second_reading','','billname'),
	OBJECT('commitalto_standing','','billname')
	)

second_reading2=SEQ(
	pattern('''(?P<billname>'''+actpattern+''') Bill,-The ''' + actpattern + ''' Bill was(,)? according to Order(,)? read a second time and stood committed to a Standing Committee(\.)?'''),
	OBJECT('second_reading','','billname'),
	OBJECT('commitalto_standing','','billname')
	)

bill_analysis=OR(
	first_reading,
	second_reading1 #,	second_reading2
	)


#minute_bill=SEQ(
#	parselib.TRACE(False),
#	pattern(paragraph_number+'(?P<billname>'+actpattern+' Bill),-(?P<sponsor>[-A-Za-z. ]*?)((,)? supported by (?P<supporters>[-A-Za-z., ]*?))?(,)? presented (a Bill to [\s\S]*?)(:)?\s*And the same was read the first time'),
#	DEBUG('matched bill'),
#	parselib.TRACE(False),
#	POSSIBLY(bill_second),
#	DEBUG('checked bill second'),
#	parselib.TRACE(False),
#	pattern('\s*and to be printed \[Bill (?P<billno>\d+)\]\.</p>'),
#	OBJECT('first_reading','','billname','sponsor','billno'), #process_minute(),
#	parselib.TRACE(False),
#	POSSIBLY(SEQ(
#		pattern('''\s*<p><ul><i>Ordered</i>, That the Explanatory Notes relating to the '''+actpattern+''' Bill be printed \[Bill \d+-EN\]\.\s*</ul></p>''')
#		))
#	)
#

#redundant
minute_resolution=SEQ(
	pattern('\s*<ul><i>Resolved</i>(,)?(?P<text>([^<])*)</ul></p>'),
	OBJECT('resolution','','text')
	)

minute_doubleindent=SEQ(
	parselib.TRACE(False),
	pattern('\s*<p><ul><ul>'),
	START('doubleindent'),
	OR(
		SEQ(
			pattern('(\s|&nbsp;)*\((?P<no>[ivxldcm]+)\)(\s|&nbsp;)*'),
			OBJECT('number','','no'),
			maintext
			),
		SEQ(
			maintext
			)
		),
	parselib.TRACE(False),
	pattern('</ul></ul></p>'),
	END('doubleindent')
	)

minute_tripleindent=SEQ(
	parselib.TRACE(False),
	pattern('\s*<p><ul><ul><ul>'),
	START('tripleindent'),
	OR(
		SEQ(
			pattern('(\s|&nbsp;)*\((?P<no>[ivxldcm]+)\)(\s|&nbsp;)*'),
			OBJECT('number','','no'),
			maintext
			),
		SEQ(
			maintext
			)
		),
	parselib.TRACE(False),
	pattern('</ul></ul></ul></p>'),
	END('tripleindent')
	)

minute_indent=SEQ(
	pattern('\s*(<p>)?<ul>(?P<maintext>[\s\S]*?)(</b>)?</ul></p>'),
	START('indent'),
	OBJECT('maintext', 'maintext'),
	END('indent')
	)

dateheading=SEQ(
	START('dateheading'),
	pattern('\s*<p( align=center)?>'),
	DEBUG('dateheading consumed p'),
	idate,
	DEBUG('found idate'),
	pattern('\s*</p>'),
	END('dateheading')
	)


untagged_par=SEQ(
	DEBUG('checking for untagged paragraph'),
	parselib.TRACE(False),
	pattern('\s*(?P<maintext>(?![^<]*\[Adjourned)([^<]|<i>|</i>)+)\s*(</ul>|</p>)?'),
	OBJECT('untagged_par','maintext')
	)

table=SEQ(
	START('table'),
	POSSIBLY(pattern('\s*<p align=center>Table</p>(\s|<ul>)*')),
	pattern('\s*(<center>)?\s*(?P<table><table[\s\S]*?</table>)\s*(</center>)?(\s|</ul>|</p>)*'),
	#OBJECT('table_markup','table'),
	OBJECT('table_markup',''),
	END('table')
	)


speaker_absence=SEQ(
	parselib.TRACE(False),
	pattern('''\s*(The)? Speaker's Absence'''),
	OR(
		SEQ(
			pattern(',-The House being met, and the Speaker having leave of absence pursuant to paragraph \(3\) of Standing Order No\. 3 \(Deputy Speaker\)\, ' + namepattern('deputy')+', the (?P<position>((First|Second) Deputy |)Chairman of Ways and Means), proceeded to the Table\.'),
			OBJECT('speaker_absence','','deputy','position')
			),
		SEQ(
			pattern(',-<i>Resolved</i>, That the Speaker have leave of absence on '),
			futureday,
			pattern('[^<]*?\.-\(<i>'+namepattern('proposer')+'</i>\.'),
			OBJECT('speaker_future_absence','','proposer')
			)
		)
	)

oathtaking=SEQ(
	START('oathtaking'),
	parselib.TRACE(True),
	DEBUG('Members take the Oath'),
	pattern('\s*Members take the Oath or make Affirmation,-(Then )?the following Members took and subscribed the Oath, or made and subscribed the Affirmation required by law:'),
	DEBUG('...Members take the Oath'),
	END('oathtaking')
	)

member_single_oath=SEQ(
	pattern("\s*<p>\s*(?P<mp_name>[-A-Za-z'Ö, .]+)\s*</p>"),
	DEBUG('got MP name'),
	parselib.TRACE(True),
	pattern("\s*<p>\s*(<i>for\s*</i>)?(?P<constituency>[-.A-Z',a-z&ô ]*?)</p>"),
	OBJECT('oath','','mp_name','constituency')
	) 

member_oaths=ANY(
	OR(
		pattern('\s*<p><ul></ul></p>'),
		member_single_oath
		)
	)
	

minute_plain=SEQ(
	parselib.TRACE(True, length=512),
	minute_main, 
	parselib.TRACE(True, length=512),
	START('minute','number'),
	DEBUG('minute started'),
	POSSIBLY(
		OR(
			CALL(speaker_absence,'minute_text'),
			CALL(bill_analysis,'minute_text'),
			SEQ(
				CALL(oathtaking,'minute_text'),
				member_oaths
				)
			)
		),
	DEBUG('just completed analyses'),
	parselib.TRACE(False, length=512),
	OBJECT('maintext', 'minute_text'),
	ANY(OR(
		minute_order,
		minute_tripleindent,
		minute_doubleindent,
		minute_indent,
		dateheading,
		untagged_par,
		table
		)),
	END('minute'))

division=SEQ(
	parselib.TRACE(False),
	pattern('\s*<p><ul>The House divided(\.)?</ul></p>'),
	DEBUG('matched division'),
	FORCE(SEQ(
		parselib.TRACE(False),
		pattern('\s*<p><ul><ul>Tellers for the Ayes, '+namepattern('ayeteller1')+', '+namepattern('ayeteller2')+': (?P<ayevote>\d+)(\.)?</ul></ul></p>'),
		DEBUG('ayeteller1'),
		pattern('\s*<p><ul><ul>Tellers for the Noes, '+namepattern('noteller1')+', '+namepattern('noteller2')+'(:)?\s*(?P<novote>\d+)(\.)?</ul></ul></p>'),
		DEBUG('ayeteller2'),
		pattern('\s*<p><ul>So the Question was agreed to\.</ul></p>')
		)),
	OBJECT('division','ayevote','novote','ayeteller1','ayeteller2','noteller1','noteller2')
	)

programme_minute=SEQ(
	OR(
		pattern('\s*<p><i>([^<]|<i>|</i>)*?</p>'),
		pattern('\s*<p><ul>(\d+\.|\(\d+\))\s*([^<]|<i>|</i>)*</ul></p>'),
		pattern('\s*<p><ul><ul>(\([a-z]\)|\d+)\s*([^<]|<i>|</i>)*</ul></ul></p>'),
		untagged_par,
		table
	),
	OBJECT('programme_minute','')
	)

next_committee=SEQ(
	tagged(
		first='\s*',
		tags=['p','ul'],
		p='Committee to-morrow.',
		fixpunctuation=True),
	OBJECT('committee_to_morrow','')
	)

programme_order=SEQ(
	pattern('''\s*<p><ul><i>Ordered(,)?\s*</i>That the following provisions shall apply to the '''+actpattern+''' Bill:</ul></p>'''),
	ANY(programme_minute)
	)	

minute_programme=SEQ(
	parselib.TRACE(False),
	pattern(paragraph_number+'(?P<maintext>[\s\S]*?the following (provisions|proceedings) shall apply to (proceedings on )?the (?P<bill>[\s\S]*?Bill)( \[<i>Lords</i>\])?(-|:|\s*for the purpose of[^<]*?)?)</p>'),
	parselib.TRACE(False),
	START('bill_programme','bill'),
	FORCE(SEQ(
		DEBUG('matched the start of a Bill programme'),
		ANY(OR(
			heading,
			programme_minute,
			)),
		POSSIBLY(division),
		POSSIBLY(programme_order),
		POSSIBLY(next_committee)
		)),
	END('bill_programme')
	)

minute_ra=SEQ(
	pattern(paragraph_number+'Royal Assent'),
	FORCE(SEQ(
		START('royal_assent'),
		parselib.TRACE(False),
		pattern('(,)?(-)?The (Deputy )?Speaker notified the House(,)? in accordance with the Royal Assent Act 1967(,)? That Her Majesty had signified her Royal Assent to the following Act(s)?(,)? agreed upon by both Houses((,)? and to the following Measure(s)? passed under the provisions of the Church of England \((Assembly )?Powers\) Act 1919)?(:)?</p>(?i)'),
		parselib.TRACE(False),
		ANY(OR(
			act,
			measurepattern,
			pattern('\s*<p><ul>(_)+</ul></p>')
			)),
		END('royal_assent')
		))
	)


minute=OR(
	minute_programme,
	minute_ra,
	minute_plain,
	)

adj_motion=SEQ(
	tagged(
		first='\s*',
		tags=['p','ul'],
		p='Adjournment,-<i>Resolved</i>, That the sitting be now adjourned.-',
		fixpunctuation=True
		),
	parselib.TRACE(False),
	pattern('\(<i>'+namepattern('proposer')+'</i>(\.)?\)(\s|</ul>|</p>)*'),
	OBJECT('adj_motion','','proposer')
	)

adjournment=SEQ(
	DEBUG('attempting to match adjournment'),
	POSSIBLY(OR(
		SEQ(
		pattern('\s*And accordingly, the House, having continued to sit till'),
		parselib.TRACE(False),
		archtime,
		pattern('\s*(,)?\s*adjourned (till|until) to-morrow(\.)?')
		),
		tagged(
			tags=['p','ul'],
			p='And accordingly the sitting was adjourned till [^<]*(\.)?')			
	)),
	pattern('\s*(<p( align=right)?>)?\s*\[Adjourned at (?P<time>\s*(\d+(\.\d+)?\s*(a\.m\.|p\.m\.)|12\s*midnight(\.)?))\s*(</p>)?'),
	OBJECT('adjournment','','time'),
	POSSIBLY(emptypar2),
	parselib.TRACE(False)
	)

speaker_address=pattern('\s*(<p><ul>)?Mr Speaker(,|\.)(</ul></p>)?\s*<p><ul>The Lords, authorised by virtue of Her Majesty\'s Commission, for declaring Her Royal Assent to several Acts agreed upon by both Houses(, and under the Parliament Acts 1911 and 1949)? and for proroguing the present Parliament, desire the immediate attendance of this Honourable House in the House of Peers, to hear the Commission read.</ul></p>')

royal_assent=SEQ(
	START('royal_assent'),
	pattern('\s*<p><ul>Accordingly the Speaker, with the House, went up to the House of Peers, where a Commission was read(,)? giving, declaring and notifying the Royal Assent to several Acts, and for proroguing this present Parliament.</ul></p>'),
	DEBUG('the royal assent...'),
	pattern('\s*(<p><ul>)?The Royal Assent was given to the following Acts( agreed upon by both Houses)?:(-)?(</ul></p>)?'),
	DEBUG('parsed "Accordingly the Speaker"'),
	ANY(act),
	POSSIBLY(SEQ(
		START('parlact'),
		DEBUG('attempting to match parliament act'),
		parselib.TRACE(False),
		pattern('\s*The Royal Assent was given to the following Act, passed under the provisions of the Parliament Acts 1911 and 1949:'),
		act,
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

speaker_chair=SEQ(
	POSSIBLY(pattern('\s*<TR><TD><HR size=1></TD></TR>')),
	pattern('\s*(<tr><td><center>|<p align=center>)Mr Speaker (Elect )?will take the Chair at '),
	archtime,
	POSSIBLY(SEQ(pattern('\s*on\s*'),OR(plaindate,futureday))),
	pattern('.(</center></td></tr>|</p>)\s*'),
	POSSIBLY(pattern('\s*<TR><TD><HR size=1></TD></TR>'))
	)

app_title=SEQ(
	DEBUG('checking for app_title'),
	parselib.TRACE(False),
	tagged(first='\s*',
		tags=['p','ul'],
		padding='\s',
		p='(<p align=center>)?APPENDIX\s*(?P<appno>(III|II|I|))(</p>)?(?=</)'
	),
	parselib.TRACE(False),
	DEBUG('starting object appendix'),
	START('appendix','appno')
	)

app_heading=heading

app_date=SEQ(
	parselib.TRACE(False),
	pattern('\s*<p( align=center)?>'),
	START('date_heading'),
	idate,
	pattern('\s*</p>'),
	END('date_heading')
	)


app_nopar=SEQ(
	pattern('\s*<p>(<ul>)?(<i>)?(?P<no>\d+)&nbsp;&nbsp;&nbsp;&nbsp;(</i>)?(?P<maintext>[\s\S]*?)(</ul>)?</p>'),
	OBJECT('app_nopar','maintext','no')
	)

misc_par=SEQ(
	pattern('\s*<p( align=left)?>\s*(<ul>)?(?P<maintext>(?!\[W\.H\.|\[Adjourned)([^<]|<i>|</i>)+)(</ul>)?(</p>)?'),
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

appendix=SEQ(
	app_title,
	DEBUG('after app_title'),
	parselib.TRACE(False), 
	ANY(SEQ(parselib.TRACE(True),OR(
		app_nopar,
		minute_doubleindent,
		app_date,
		app_heading,
		app_subheading,
		app_nosubpar,
		app_date_sep,
		attr_sep,
		app_par,
		emptypar,
		untagged_par
		))),
	END('appendix'),
	DEBUG('ended appendix')
	)

westminsterhall=SEQ(
	START('westminsterhall'),
	POSSIBLY(pattern('\s*<hr width=90%>')),
	pattern('\s*(<p>\s*</p>|<p>\s*<p>)?\s*<p( align=center)?>\s*\[\s*W.H.(,)?\s*No(\.)?\s*(?P<no>\d+)\s*\]\s*</p>'),
	tagged(
		tags=['p','font','b'],
		first='\s*',
		padding='<p>',
		p='Minutes of Proceedings of the Sitting in Westminster Hall',
		last='(<font size=3>)?(</p>)?'
		),
	POSSIBLY(SEQ(
		pattern('(\s|<p>|<b>)*\[pursuant to the Order of '),
		plaindate,
		pattern('\](</font>)?</b></p>'),
		)),
	pattern('\s*(<p( align=center)?>)?(<font size=3>)?The sitting (commenced|began) at (?i)'),
	archtime,
	pattern('.(</b>)?</p>'),
	DEBUG('remaining westminster hall'),
	ANY(SEQ(parselib.TRACE(True),
		OR(
			adj_motion,
			pattern('\s*<p><ul><ul>([^<])*?</ul></ul></p>'),
			misc_par,
			untagged_par
			)), 
		until=adjournment),
	parselib.TRACE(False),
	speaker_signature,
	END('westminsterhall'))	

chairmens_panel=SEQ(
	parselib.TRACE(True),
	tagged(
		first='\s*',
		tags=['p','b'],
		p='''CHAIRMEN'S PANEL'''
		),
	DEBUG('chairmen\'s panel...'),
	pattern('''\s*<p>In pursuance of Standing Order No\. 4 \(Chairmen's Panel\), the Speaker (has )?nominated '''),
	OR(
		pattern('''([-A-Za-z Ö.']+?, )*?([-A-Za-z Ö.']+?) and ([-A-Za-z Ö.']+? )to be members of the Chairmen's Panel during this Session\.</p>'''),
		pattern('''([-A-Za-z Ö.']+? )to be a member of the Chairmen's Panel during this Session( of Parliament)?\.</p>''')
		),
	OBJECT('chairmens_panel','')
	)

certificate=SEQ(
	tagged(
		first='\s*',
		tags=['p','b','ul'],
		p='''THE SPEAKER'S CERTIFICATE'''
		),
	tagged(
		first='\s*',
		tags=['p','ul'],
		p='''\s*The Speaker certified that the (?P<billname>[-a-z.,A-Z0-9()\s]*?Bill) is a Money Bill within the meaning of the Parliament Act 1911(\.)?'''
		),
	OBJECT('money_bill_certificate','','billname')
	)

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
	POSSIBLY(pattern('\s*<hr[^>]*>')),
	pattern('(<p( align=center)?>|\s)*CORRIGEND(A|UM)</p>\s*'),
	START('corrigenda'),
	ANY(
		OR(
			pattern('\s*<p><ul>[\s\S]*?</ul></p>'),
			pattern('\s*<ul>[\s\S]*?</ul>'),
			untagged_par
			)
	),
	END('corrigenda')
	)

memorandum=SEQ(
	pattern('\s*<p( align=center)?>MEMORANDUM</p>'),	
	START('memorandum'),
	POSSIBLY(
		SEQ(
			pattern('\s*<p align=center>(?P<text>[^<]*?)</p>'),
			OBJECT('heading','','text')
			)
		),
	POSSIBLY(
		SEQ(
			pattern('\s*<p>(?P<text>[^<]*?)</p>'),
			OBJECT('paragraph','','text')
			)
		),	
	END('memorandum')
	)




footnote=SEQ(
	pattern('\s*Votes and Proceedings:'),
	plaindate,
	pattern('\s*No. \d+')
	)

page=SEQ(
	START('page','date'),
	header, 
	POSSIBLY(pattern('\s*<p><b>Votes and Proceedings</b></p>')),
	POSSIBLY(O13notice), #O13notice,
	meeting_time,
	#prayers,
## prayers don't necessary come first (though they usually do)
	ANY(
		SEQ(parselib.TRACE(False),OR(prayers,minute)),
		until=prorogation, 
		otherwise=SEQ(adjournment, speaker_signature, speaker_chair)), 
	DEBUG('now check for appendices'),
	ANY(appendix),
	POSSIBLY(chairmens_panel),
	#chairmens_panel,
	POSSIBLY(certificate), #certificate,
	POSSIBLY(westminsterhall), 
	#westminsterhall,
	POSSIBLY(corrigenda), 
	#corrigenda,
	POSSIBLY(memorandum),
	POSSIBLY(footnote),
	POSSIBLY(pattern('(\s|<p>|</p>)*')),
	DEBUG('endpattern'),
	endpattern,
	END('page')
	)

votedir='/home/Francis/project/parldata/cmpages/votes'

def parsevote(date):
	name='votes%s.html' % date
	f=open(votedir+'/'+name) # do not do this
	s=f.read()
        return parsevotetext(s, date)

def parsevotetext(s, date):
	# I am not sure what the <legal 1> tags are for. At present
	# it seems safe to remove them.
	s=s.replace('<legal 1>','<p><ul>')
	s=re.sub('<br><br>(?i)','</p><p>',s)
	s=re.sub('<br>(?i)','</p>',s)
	s=s.replace('&#151;','-')
	s=s.replace('\x99','&#214;')
	s=s.replace('</i></b><b><i><i><b>','') # has no useful effect
	s=s.replace('</i></b></i></b>','</i></b>')
	s=re.sub('alaign=center(?i)','align=center',s)
	s=re.sub('<i>\s*</i>','',s)
	s=re.sub('</p>\s*</ul>','</p>\n',s)

	return page(s,{'date':date})

if __name__ == '__main__':

	date=sys.argv[1]
	(s,env,result)=parsevote(date)
	
	
	if result.success:
		print result.text()
	
		output='''<?xml version="1.0" encoding="ISO-8859-1"?>'''+result.text()

		outdir='votes'
		outfile=os.path.join('votes','votes%s.xml' % date)
		fout=open(outfile,'w')
		fout.write(output)
	else:
		print "failure"
		print result.text()
		print "----"
		print s[:128]
		sys.exit(1)

# For calling from lazyrunall.py
def RunVotesFilters(fout, text, sdate):
        (s,env,result)=parsevotetext(text, sdate)

        if result.success:
                WriteXMLHeader(fout)
                fout.write(result.text())  
        else:
                raise ContextException("Failed to parse vote\n%s\n%s" % (result.text(), s[:128]))




