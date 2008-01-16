#!/usr/bin/python2.4

import sys
import os
import random
import datetime
import time
import urllib

from BeautifulSoup import BeautifulSoup
from BeautifulSoup import NavigableString
from BeautifulSoup import Tag
from BeautifulSoup import Comment

agent = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"

class MyURLopener(urllib.FancyURLopener):
    version = agent

urllib._urlopener = MyURLopener()

import re

currentdate = datetime.date.today()
currentyear = datetime.date.today().year

output_directory = "../../../parldata/cmpages/sp/written-answers/"
written_answers_template = output_directory + "wa%s_%d.html"
written_answers_urls_template = output_directory + "wa%s.urls"

# Fetch the year indices that we either don't have
# or is the current year's...

written_answers_prefix = "http://www.scottish.parliament.uk/business/pqa/"
written_answers_year_template = written_answers_prefix + "%d.htm"

for year in range(1999,currentyear+1):
    index_page_url = written_answers_year_template % year
    output_filename = output_directory + str(year) + ".html"
    if (not os.path.exists(output_filename)) or (year == currentyear):
        ur = urllib.urlopen(index_page_url)
        fp = open(output_filename, 'w')
        fp.write(ur.read())
        fp.close()
        ur.close()

def month_name_to_int( name ):

    months = [ None,
               "january",
               "february",
               "march",
               "april",
               "may",
               "june",
               "july",
               "august",
               "september",
               "october",
               "november",
               "december" ]

    result = 0

    for i in range(1,13):
        if name.lower() == months[i]:
            result = i
            break

    return result

def non_tag_data_in( o ):
    if o.__class__ == NavigableString:
        return re.sub('(?ms)[\r\n]',' ',o)
    elif o.__class__ == Tag:
        return ''.join( map( lambda x: non_tag_data_in(x) , o.contents ) )
    elif o.__class__ == Comment:
        return ''

for year in range(1999,currentyear+1):

    year_index_filename = output_directory  + str(year) + ".html"
    if not os.path.exists(year_index_filename):
        raise Exception, "Missing the year index: '%s'" % year_index_filename
    fp = open(year_index_filename)
    html = fp.read()
    fp.close()

    soup = BeautifulSoup( html )
    link_tags = soup.findAll( 'a' )

    contents_pages = set()
    daily_pages = set()

    contents_hash = {}

    for t in link_tags:

        if t.has_key('href') and re.match('^wa-',t['href']):

            s = ""
            for c in t.contents:
                if type(c) == NavigableString:
                    s = s + str(c)
            s = re.sub('(?ims)\s+',' ',s)
            s = s.strip()

            if len(s) == 0:
                continue

            # print year_index_filename + "==> " + s
            d = None

            m_week = re.match( '^Written Ans?wers?[^\d]*\s(\d+)\s*(\w+)?\s*(\d+)?\s*\-\s*(\d+)\s+(\w+)\s+(\d{4})\s*', s )
            m_day = re.match( '^Daily Written[^\d]*\s(\d+)\s+(\w+)\s+(\d{4})\s*', s )

            page = t['href']

            subdir, leaf = page.split("/")
            # print "  subdir: "+subdir+", leaf: "+leaf

            if re.match( '^Statis', s ):
                continue
            elif m_day:
                # print "Got day: "+s
                daily_pages.add( (subdir,leaf) )
            elif m_week:
                day_start = m_week.group(1)
                month_start = m_week.group(2)
                year_start = m_week.group(3)
                day_end = m_week.group(4)
                month_end = m_week.group(5)
                year_end = m_week.group(6)
                if not month_start:
                    month_start = month_end
                if not year_start:
                    year_start = year_end
                start_date = datetime.date( int(year_start), month_name_to_int(month_start), int(day_start,10) )
                end_date = datetime.date( int(year_end), month_name_to_int(month_end), int(day_end,10) )
                contents_pages.add( (subdir,leaf,start_date,end_date) )
                contents_hash[subdir+"_"+leaf] = True

    # Fetch all the contents pages:

    for (subdir,leaf,start_date,end_date) in contents_pages:

        contents_filename = output_directory + "contents-"+subdir+"_"+leaf
        contents_url = written_answers_prefix + subdir + "/" + leaf

        if not os.path.exists(contents_filename) or (currentdate - end_date).days < 4:
            ur = urllib.urlopen(contents_url)
            fp = open(contents_filename, 'w')
            fp.write(ur.read())
            fp.close()
            ur.close()
                
    # Now find all the daily pages from the contents pages...

    for (subdir,leaf,start_date,end_date) in contents_pages:

        contents_filename = output_directory + "contents-"+subdir+"_"+leaf

        fp = open(contents_filename)
        contents_html = fp.read()
        fp.close()

        contents_html = re.sub('&nbsp;',' ',contents_html)
        contents_soup = BeautifulSoup(contents_html)
        link_tags = contents_soup.findAll( lambda x: x.name == 'a' and x.has_key('href') and re.match('^wa.*',x['href']) )
        links = map( lambda e: re.sub('#.*$','',e['href']), link_tags )            

        for alternative_leaf in links:
            # print "alternative_leaf is: "+alternative_leaf
            if contents_hash.has_key(subdir+"_"+alternative_leaf):
                continue
            
            day_filename = output_directory + "day-" + subdir + "_" + alternative_leaf
            day_url = written_answers_prefix + subdir + "/" + alternative_leaf

            if not os.path.exists(day_filename):
                ur = urllib.urlopen(day_url)
                fp = open(day_filename, 'w')
                fp.write(ur.read())
                fp.close()
                ur.close()
                amount_to_sleep = int( 20 * random.random() )
                time.sleep( amount_to_sleep )
