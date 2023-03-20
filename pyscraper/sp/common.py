# A few functions that turn out to be useful in many of the Scottish
# Parliament scraping scripts.

import sys
import datetime
sys.path.append('../')
from bs4 import NavigableString
from bs4 import Tag
from bs4 import Comment

import re

# A number of SPIDs have a 0 (zero) in place of an O (letter O), and
# this converts a string containing them.  It also fixes leading 0s in
# the number after the hyphen.
def fix_spid(s):
    result = re.sub('(S[0-9]+)0-([0-9]+)',r'\1O-\2',s)
    return re.sub('(S[0-9]+\w+)-0*([0-9]+)',r'\1-\2',result)

months = { "january"   : 1,
           "february"  : 2,
           "march"     : 3,
           "april"     : 4,
           "may"       : 5,
           "june"      : 6,
           "july"      : 7,
           "august"    : 8,
           "september" : 9,
           "october"   : 10,             
           "november"  : 11,
           "december"  : 12 }

abbreviated_months = { }
for k in months.keys():
    abbreviated_months[k[0:3]] = months[k]

def month_name_to_int( name ):

    lowered = name.lower()

    if lowered in months:
        return months[lowered]

    if lowered in abbreviated_months:
        return abbreviated_months[lowered]

    return 0

def non_tag_data_in(o, tag_replacement=''):
    if o.__class__ == NavigableString:
        return re.sub('(?ms)[\r\n]',' ',o)
    elif o.__class__ == Tag:
        if o.name == 'script':
            return tag_replacement
        else:
            return tag_replacement.join( [non_tag_data_in(x) for x in o.contents] )
    elif o.__class__ == Comment:
        return tag_replacement
    else:
        # Hope it's a string or something else concatenatable...
        return o

def tidy_string(s):
    # Lots of the paragraphs in the HTML begin with a pointless ':'
    # surrounded by spaces:
    result = re.sub("(?imsu)^\s*:\s*",'',s)
    result = re.sub('(?ims)\s+',' ',result)
    return result.strip()

# These two methods from:
#
#  http://snippets.dzone.com/posts/show/4569

from html.entities import name2codepoint

def substitute_entity(match):
    ent = match.group(2)
    if match.group(1) == "#":
        return chr(int(ent))
    else:
        cp = name2codepoint.get(ent)
        if cp:
            return chr(cp)
        else:
            return match.group()

def decode_htmlentities(string):
    entity_re = re.compile("&(#?)(\d{1,5}|\w{1,8});")
    return entity_re.subn(substitute_entity, string)[0]

def compare_spids(a,b):
    ma = re.search('S(\d+\w+)-(\d+)',a)
    mb = re.search('S(\d+\w+)-(\d+)',b)
    if ma and mb:
        mas = ma.group(1)
        mbs = mb.group(1)
        mai = int(ma.group(2),10)
        mbi = int(mb.group(2),10)
        if mas < mbs:
            return -1
        elif mas > mbs:
            return 1
        else:
            if mai < mbi:
                return -1
            if mai > mbi:
                return 1
            else:
                return 0
    else:
        raise Exception("Couldn't match spids: "+a+" and "+b)

def just_time( non_tag_text ):
    m = re.match( '^\s*(\d?\d)[:\.](\d\d)\s*$', non_tag_text )
    if m:
        return datetime.time(int(m.group(1),10),int(m.group(2),10))
    else:
        return None

def meeting_closed( non_tag_text ):
    m = re.match( '(?imsu)^\s*:?\s*Meeting\s+closed\s+at\s+(\d?\d)[:\.](\d\d)\s*\.?\s*$', non_tag_text )
    if m:
        return datetime.time(int(m.group(1),10),int(m.group(2),10))
    else:
        return None

def meeting_suspended( non_tag_text ):
    m = re.match( '(?imsu)^\s*:?\s*Meeting\s+suspended(\s+(at|until)\s+(\d?\d)[:\.](\d\d)\s*\.?\s*|\s*\.?\s*)$', non_tag_text )
    if m:
        if m.group(2):
            at_or_until = m.group(2)
            hours = m.group(3)
            minutes = m.group(4)
            return (True, at_or_until, datetime.time(int(hours, 10), int(minutes, 10)))
        else:
            return (True, None, None)
    else:
        return None
