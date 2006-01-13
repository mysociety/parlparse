import fd_parse
from fd_parse import SEQ, OR,  ANY, POSSIBLY, IF, START, END, OBJECT, NULL, OUT, DEBUG, STOP, FORCE, CALL, pattern, tagged

# Time handling

engnumber60='(one|two|three|four|five|six(?!ty)|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|((twenty|thirty|forty|fifty)(-(one|two|three|four|five|six|seven|eight|nine))?))'

archtime=SEQ(
	pattern('\s*(?P<archtime>(a quarter past|half-past|a quarter to|'+engnumber60+' minutes (to|past)|)\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)(\s*o\'\s*clock)?)(?i)'),
	OBJECT('time','','archtime')
	)

dayname=pattern('\s*(?P<dayname>(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\s*')

monthname=pattern('\s*(?P<monthname>(January|February|March|April|May|June|July|August|September|October|November|December))\s*')

year=pattern('(?P<year>\d{4})\s*')

dayordinal=pattern('\s*(?P<day>\d+(st|nd|rd|th))\s*')

plaindate=SEQ(POSSIBLY(dayname), dayordinal, monthname, POSSIBLY(year))

futureday=SEQ(OR(
		SEQ(dayname,pattern('\s*next\s*')),
		pattern('to(-)?morrow'),
		SEQ(
			pattern('on '),
			plaindate
			)
		))

# Dates with idiosyncratic italics

idate=SEQ(
	pattern('\s*<i>\s*'),
	dayname,
	DEBUG('got dayname'),
	fd_parse.TRACE(False),
	POSSIBLY(pattern('\s*</i>\s*')),
	fd_parse.TRACE(False),
	OR(
		pattern('\s*(?P<dayno>\d+)(st|nd|rd|th)\s*<i>\s*'),
		pattern('\s*(?P<dayno>\d+)(<i>)?(st|nd|rd|th)\s*')
	),
	fd_parse.TRACE(False),
	DEBUG('got dayordinal'),
	fd_parse.TRACE(False),
	monthname,
	DEBUG('got monthname'),
	OR(
		SEQ(pattern('\s*</i>\s*'),year),
		SEQ(year,pattern('\s*</i>\s*'))
		),
	OBJECT('date','','dayname','monthname','year','dayno')
	)


