#!/usr/bin/python
# vim:sw=8:ts=8:et:nowrap

# A very experimental program to parse votes and proceedings files.

# To do:

# House committees (notes below)
# Second readings
# detached [by Act] [name] paragraphs
# eating of <p>'s when shouldn't (see 2003-03-03)

import sys
import os
import os.path
import re
import fd_parse
from fd_dates import *


from fd_parse import SEQ, OR,  ANY, POSSIBLY, IF, START, END, OBJECT, NULL, OUT, DEBUG, STOP, FORCE, CALL, ATTRIBUTES, pattern, tagged, plaintextpar, plaintext

sys.path.append("../")
from xmlfilewrite import WriteXMLHeader
from contextexception import ContextException

splitparagraphs=ANY(
	SEQ(
		pattern('\s*(<p([^>]*?)>(<ul>)?)(?P<partext>([^<]|<i>|</i>)*)(</ul>)?(</p>)?'),
		OBJECT('paragraph','partext')
		)
	)

def namepattern(label='name'):
	return "(?P<"+label+">[-A-Za-z .']+)"



fd_parse.standard_patterns.update(
		{
		'mp'	: lambda n: namepattern('mp%s' % n),
		'act'	: lambda n: '(?P<actname%s>[-a-z.,A-Z0-9()\s]*?)' % n 
		}
	)

# Names may have dots and hyphens in them.

emptypar=pattern('\s*<p>\s*</p>\s*(?i)')
emptypar2=pattern('\s*<p><ul>\s*</ul></p>\s*')

actpattern='(?P<actname>[-a-z.,A-Z0-9()\s]*?)' 

act=SEQ(
	pattern('\s*<p><ul>(<ul>)?(?P<shorttitle>'+actpattern+' Act)\s*(?P<year>\d+)(\.)?(</ul>)?</ul></p>'),
	OBJECT('act','','shorttitle','year')
	)

measurepattern=SEQ(
	pattern('\s*<p><ul>(<ul>)?(?P<shorttitle>[-a-z.,A-Z0-9()\s]*?Measure)\s*(?P<year>\d+)(\.)?</ul>(</ul>)?</p>'),
	OBJECT('measure','','shorttitle','year')
	)


header=SEQ(
	pattern('<pagex (?P<pagex>[\s\S]*?)/>'),
	#OUT('pagex'),
	ATTRIBUTES(groupstring='pagex'),
	pattern('\s*</td></tr>\s*</table>\s*<table width="90%"\s*cellspacing=6 cols=2 border=0>\s*<tr><td>\s*</font><p>\s*(?i)'))


# TODO -- meeting may be pursuant to an order see: 2002-03-26

meeting_time=SEQ(
	START('opening'),
	pattern('\s*(<p>1&nbsp;&nbsp;&nbsp;&nbsp;|<p(?: align=center)?>)The House met at\s*'),
	fd_parse.TRACE(True),
	archtime,
	fd_parse.TRACE(True),
	POSSIBLY(
		SEQ(
			pattern('(,)? pursuant to Order \['),
			plaindate,
			pattern('\]')
			)
		),
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

# all p ul
# clause, ((another)? amendment proposal, (question put, division) or (question proposed - amendment by leave withdrawn) or (question - put and negatived) or (question proposed, that the amendment be made) [? after a division / deferred divisions] 'and it being ? oclock on clauses A-B', (question - put and negatived), (question put, that clause A stand part of the bill, division), clauses C to B agreed to, chairmen left chair to report, hline, dep speaker resumes ..., comittee again to-morrow

# clauses E to F agreed to, bill to be reported (dep speaker...), ord bill be read a third time ...

# A clause (....) (Name) brought up and read the first time
# Another clause

#house_committee=SEQ(
#	pattern("(?P<billname>"+actpattern+" Bill\s*\[" + ordinal(dayno) + "\s*\llotted day\],-"The House, according to Order, resolved itself into a Committee on the Bill\.</p>"),
#	tagged(first="\s*", tags=['p'],p="\(In the Committee\)")

# Note: text of the sub-paragraphs will need to be spat out.

committee_reported=OR(
	SEQ(
		DEBUG('checking committee report'),
		fd_parse.TRACE(True, envlength=512),
		CALL(
			SEQ(DEBUG('inside call'),
			fd_parse.TRACE(True, envlength=512),
			plaintext(

'%(act1),-%(mp) reported from Standing Committee %(committee), That it had gone through the %(act2), and made Amendments thereunto.',

				strings={ 'committee' : '(?P<sc>[A-B])' },
				debug=True),
			START('committee_reported',['actname1','mp','sc']),
			fd_parse.TRACE(True, envlength=512)),
			callstrings=['minute_text'],
			passback={
				'actname1' : 'billname',
				'sc' : 'sc'}), 
		DEBUG('committee_reported found'),
		fd_parse.TRACE(True),
		SEQ(
			plaintextpar(

'Bill, as amended in the Standing Committee, to be considered to-morrow; and to be printed [Bill %(billno)].',
				strings={ 'billno' : '(?P<billno>\d+)' }
				),
			OBJECT('billprint','','billno', 'billname'),
			plaintextpar(

'Minutes of Proceedings of the Committee to be printed [No. %(scprint)].',
				strings={ 'scprint' : '(?P<scprint>\d+)'}
				),
			OBJECT('scminutesprint','','billname','billno','sc','scprint')
			),
		END('committee_reported')
		)
	)

bill_second=SEQ(
	pattern('; and ordered to be read a second time '),
	futureday,
	OBJECT('second_reading_scheduled','','billname')
	) 

first_reading=SEQ(
	DEBUG('checking minute bill'),
	fd_parse.TRACE(True,vals=['minute_text']),
	pattern('''(?P<billname>'''+actpattern+''' Bill),-(?P<sponsor>[-A-Za-z'. ]*?)((,)? supported by (?P<supporters>[-A-Za-z'., ]*?))?(,)? presented (\(under Standing Order No\. 50 \(Procedure upon bills whose main object is to create a charge upon the public revenue\)\) )?(a Bill to [\s\S]*?)(:)?\s*And the same was read the first time'''),
	DEBUG('matched bill'),
	fd_parse.TRACE(True),
	POSSIBLY(bill_second),
	DEBUG('checked bill second'),
	fd_parse.TRACE(False),
	pattern('\s*and to be printed \[\s*Bill\s*(?P<billno>\d+)\s*\](\.)?'),
	OBJECT('first_reading','','billname','sponsor','billno'), #process_minute(),
	OBJECT('billprint','','billname','billno'),
	fd_parse.TRACE(False),
	)

second_reading1=SEQ(
	#pattern('''(?P<billname>'''+actpattern+''') Bill,-The ''' + actpattern + ''' Bill was(,)? according to Order(,)? read a second time and stood committed to a Standing Committee(\.)?'''),
	plaintext('%(act1),-The %(act2) Bill was, according to Order, read a second time and stood committed to a Standing Committee.'),
	OBJECT('second_reading','','actname1'),
	OBJECT('commitalto_standing','','actname1')
	)

second_reading2=SEQ(
#	pattern('''(?P<billname>'''+actpattern+''') Bill,-The ''' + actpattern + ''' Bill was(,)? according to Order(,)? read a second time and stood committed to a Standing Committee(\.)?'''),
	plaintext('%(act1),-The %(act2) was, according to Order, read a second time and stood committed to a Standing Committee.'),
	OBJECT('second_reading','','actname1'),
	OBJECT('commitalto_standing','','actname1')
	)

third_reading=SEQ(
	plaintext('%(act1) [%(ordinal) allotted day],-%(act2) was, according to Order, read the third time, and passed.',
		strings={
			'ordinal' : '\d+(st|nd|rd|th)'
		}),
	OBJECT('third_reading', '', 'actname1')
	)

explanatory_notes=SEQ(
	DEBUG('explanatory notes'),
	fd_parse.TRACE(True),
	plaintext('%(act1),-<i>Ordered</i>, That the Explanatory Notes to the %(act2) be printed [Bill %(enprint)].',
		debug=True,
		strings={
			'enprint' : '(?P<enprintno>\d+-EN)'
			}
		),
	OBJECT('enprint','','enprintno', 'actname1')
	)

bill_analysis=OR(
	first_reading,
	second_reading1,	
	second_reading2,
	third_reading,
	explanatory_notes
#	house_committee
	)


#minute_bill=SEQ(
#	fd_parse.TRACE(False),
#	pattern(paragraph_number+'(?P<billname>'+actpattern+' Bill),-(?P<sponsor>[-A-Za-z. ]*?)((,)? supported by (?P<supporters>[-A-Za-z., ]*?))?(,)? presented (a Bill to [\s\S]*?)(:)?\s*And the same was read the first time'),
#	DEBUG('matched bill'),
#	fd_parse.TRACE(False),
#	POSSIBLY(bill_second),
#	DEBUG('checked bill second'),
#	fd_parse.TRACE(False),
#	pattern('\s*and to be printed \[Bill (?P<billno>\d+)\]\.</p>'),
#	OBJECT('first_reading','','billname','sponsor','billno'), #process_minute(),
#	fd_parse.TRACE(False),
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
	fd_parse.TRACE(False),
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
	fd_parse.TRACE(False),
	pattern('</ul></ul></p>'),
	END('doubleindent')
	)

minute_tripleindent=SEQ(
	fd_parse.TRACE(False),
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
	fd_parse.TRACE(False),
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
	fd_parse.TRACE(False),
	pattern('\s*(?P<maintext>(?![^<]*\[Adjourned)([^<]|<i>|</i>)+)\s*(</ul>|</p>)?'),
	OBJECT('untagged_par','maintext')
	)

table=SEQ(
	START('table'),
	POSSIBLY(pattern('\s*<p align=center>(<i>)?Table(</i>)?</p>(\s|<ul>)*')),
	pattern('\s*(<center>)?\s*(?P<table><table[\s\S]*?</table>)\s*(</center>)?(\s|</ul>|</p>)*'),
	#OBJECT('table_markup','table'),
	OBJECT('table_markup',''),
	END('table')
	)


speaker_absence=SEQ(
	fd_parse.TRACE(False),
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
	fd_parse.TRACE(True),
	DEBUG('Members take the Oath'),
	pattern('\s*Members take the Oath or make Affirmation,-(Then )?the following Members took and subscribed the Oath, or made and subscribed the Affirmation required by law:'),
	DEBUG('...Members take the Oath'),
	END('oathtaking')
	)

member_single_oath=SEQ(
	pattern("\s*<p>\s*(?P<mp_name>[-A-Za-z'Ö, .]+)\s*</p>"),
	DEBUG('got MP name'),
	fd_parse.TRACE(True),
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
	fd_parse.TRACE(True, slength=512),
	minute_main, 
	fd_parse.TRACE(True, slength=512),
	START('minute',['number']),
	DEBUG('minute started'),
	POSSIBLY(
		OR(
			CALL(speaker_absence,['minute_text']),
			CALL(bill_analysis,['minute_text']),
			SEQ(
				CALL(oathtaking,['minute_text']),
				member_oaths
				),
			committee_reported
			)
		),
	DEBUG('just completed analyses'),
	fd_parse.TRACE(False, slength=512),
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
	fd_parse.TRACE(False),
	pattern('\s*<p><ul>The House divided(\.)?</ul></p>'),
	DEBUG('matched division'),
	FORCE(SEQ(
		fd_parse.TRACE(False),
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
	DEBUG('next committee'),
	fd_parse.TRACE(True),
	plaintextpar('Committee to-morrow.'),
	fd_parse.TRACE(True),
#	tagged(
#		first='\s*',
#		tags=['p','ul'],
#		p='Committee to-morrow.',
#		fixpunctuation=True),
	OBJECT('committee_to_morrow','')
	)

programme_order=SEQ(
	DEBUG('programme_order'),
	pattern('''\s*<p><ul><i>Ordered(,)?\s*</i>(,)?\s*That the following provisions shall apply to the '''+actpattern+''' Bill:</ul></p>'''),
	DEBUG('found ordered'),
	ANY(programme_minute)
	)	

minute_programme=SEQ(
	fd_parse.TRACE(False),
	pattern(paragraph_number+'(?P<maintext>[\s\S]*?the following (provisions|proceedings) shall apply to (proceedings on )?the (?P<bill>[\s\S]*?Bill)( \[<i>Lords</i>\])?(-|:|\s*for the purpose of[^<]*?)?)</p>'),
	fd_parse.TRACE(False),
	START('bill_programme',['bill']),
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
		fd_parse.TRACE(False),
		pattern('(,)?(-)?The (Deputy )?Speaker notified the House(,)? in accordance with the Royal Assent Act 1967(,)? That Her Majesty had signified her Royal Assent to the following Act(s)?(,)? agreed upon by both Houses((,)? and to the following Measure(s)? passed under the provisions of the Church of England \((Assembly )?Powers\) Act 1919)?(:)?</p>(?i)'),
		fd_parse.TRACE(False),
		ANY(OR(
			act,
			measurepattern,
			pattern('\s*<p><ul>(_)+</ul></p>')
			)),
		END('royal_assent')
		))
	)

detached_paragraph=SEQ(
	STOP()
	)

minute=OR(
	detached_paragraph,
	minute_programme,
	minute_ra,
	minute_plain,
	)

adj_motion=SEQ(
	plaintextpar('Adjournment,-<i>Resolved</i>, That the sitting be now adjourned.-'),
#	tagged(
#		first='\s*',
#		tags=['p','ul'],
#		p='Adjournment,-<i>Resolved</i>, That the sitting be now adjourned.-',
#		fixpunctuation=True
#		),
	fd_parse.TRACE(False),
	pattern('\(<i>'+namepattern('proposer')+'</i>(\.)?\)(\s|</ul>|</p>)*'),
	OBJECT('adj_motion','','proposer')
	)

adjournment=SEQ(
	DEBUG('attempting to match adjournment'),
	POSSIBLY(OR(
		SEQ(
		pattern('\s*And accordingly, the House, having continued to sit till'),
		fd_parse.TRACE(False),
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
	fd_parse.TRACE(False)
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
		fd_parse.TRACE(False),
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
	fd_parse.TRACE(False),
	pattern('\s*<p>\s*(<ul>)?My Lords and Members of the House of Commons(,)?(</ul>)?</p>'),
	pattern('(?P<royalspeech>[\s\S]*?)<p>\s*(<ul>)?I pray that the blessing of Almighty God may (attend you|rest upon your counsels)\.\s*(</ul>)?</p>'),
	DEBUG('end of royal speech'),
	fd_parse.TRACE(False),
	DEBUG('finished the royal speech'),
	START('royalspeech'),
	CALL(splitparagraphs, ['royalspeech']),
	END('royalspeech'),
#	OBJECT('royalspeech','royalspeech')
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
	fd_parse.TRACE(False),
	tagged(first='\s*',
		tags=['p','ul'],
		padding='\s',
		p='(<p align=center>)?APPENDIX\s*(?P<appno>(III|II|I|))(</p>)?(?=</)'
	),
	fd_parse.TRACE(False),
	DEBUG('starting object appendix'),
	START('appendix',['appno'])
	)

app_heading=heading

app_date=SEQ(
	fd_parse.TRACE(False),
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
	pattern('\s*<p( align=left)?><i>(?P<maintext>([^<]|<i>|</i>)*)</p>'),
	OBJECT('app_subhead','','maintext')
	)

app_nosubpar=SEQ(
	pattern('\s*<p><ul>\(\d+\)([^<]|<i>|</i>)*</ul></p>')
	)

#date accidently put in a separate paragraph

app_date_sep=pattern('\s*<p><ul>dated ([^<]|<i>|</i>)*?\[[a-zA-Z ]*\].</ul></p>')

attr_sep=pattern('\s*<p><ul>\[by Act\]\s*\[[\s\S]*?\].</ul></p>')

appendix=SEQ(
	app_title,
	DEBUG('after app_title'),
	fd_parse.TRACE(False), 
	ANY(SEQ(fd_parse.TRACE(True),OR(
		app_nopar,
		minute_doubleindent,
		app_date,
		app_heading,
		app_subheading,
		app_nosubpar,
		app_date_sep,
		attr_sep,
		app_par,
		OR(emptypar, emptypar2),
		untagged_par,
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
		pattern('\](|</font>|</b>)*</p>'),
		)),
	pattern('\s*(<p( align=center)?>)?(<font size=3>)?The sitting (commenced|began) at (?i)'),
	archtime,
	pattern('.(</b>)?</p>'),
	DEBUG('remaining westminster hall'),
	ANY(SEQ(fd_parse.TRACE(True),
		OR(
			adj_motion,
			pattern('\s*<p><ul><ul>([^<])*?</ul></ul></p>'),
			misc_par,
			untagged_par
			)), 
		until=adjournment),
	fd_parse.TRACE(False),
	speaker_signature,
	END('westminsterhall'))	

chairmens_panel=SEQ(
	tagged(
		first='\s*',
		tags=['p','b'],
		p='''CHAIRMEN'S PANEL'''
		),
	DEBUG('chairmen\'s panel...'),
	pattern('''\s*<p>(<ul>)?In pursuance of Standing Order No\. 4 \(Chairmen's Panel\)(,)? the Speaker (has )?nominated '''),
	OR(
		pattern('''([-A-Za-z Ö.']+?, )*?([-A-Za-z Ö.']+?) and ([-A-Za-z Ö.']+? )to be members of the Chairmen's Panel during this Session(\.)?</p>'''),
		pattern('''([-A-Za-z Ö.']+? )to be a member of the Chairmen's Panel during this Session( of Parliament)?(\.)?(</ul>)?</p>''')
		),
	OBJECT('chairmens_panel','')
	)

certificate=SEQ(
	POSSIBLY(pattern('\s*<p( align=center)?>_+</p>')),
	tagged(
		first='\s*',
		padding='\s',
		tags=['p','b','ul'],
		p='''THE SPEAKER'S CERTIFICATE'''
		),
	tagged(
		first='\s*',
		tags=['p','ul'],
		p='''\s*The Speaker certified that the (?P<billname>[-a-z.,A-Z0-9()\s]*?Bill) is a Money Bill within the meaning of the Parliament Act 1911(\.)?'''
		),
	OBJECT('money_bill_certificate','','billname'),
	POSSIBLY(pattern('\s*<p( align=center)?>_+</p>')),
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
	START('page',['date']),
	header, 
	POSSIBLY(pattern('\s*<p><b>Votes and Proceedings</b></p>')),
	POSSIBLY(O13notice), #O13notice,
	meeting_time,
	#prayers,
## prayers don't necessary come first (though they usually do)
	ANY(
		SEQ(fd_parse.TRACE(True),OR(prayers,minute)),
		until=prorogation, 
		otherwise=SEQ(adjournment, speaker_signature, speaker_chair)), 
	DEBUG('now check for appendices'),
	ANY(appendix),
	POSSIBLY(chairmens_panel),
	#chairmens_panel,
	POSSIBLY(certificate), 
	#certificate,
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
	
		#output='''<?xml version="1.0" encoding="ISO-8859-1"?>'''+result.text()
		xml=result.delta.apply(None)
		output=xml.toprettyxml(encoding="ISO-8859-1")
		print output

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
		result.delta.apply(None).writexml(fout, encoding="ISO-8859-1")
#                WriteXMLHeader(fout)
#                fout.write(result.text())  
        else:
                raise ContextException("Failed to parse vote\n%s\n%s" % (result.text(), s[:128]))




