# A few functions that turn out to be useful in many of the Scottish
# Parliament scraping scripts.

import sys
import datetime
sys.path.append('../')
from bs4 import NavigableString
from bs4 import Tag
from bs4 import Comment

import re

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
