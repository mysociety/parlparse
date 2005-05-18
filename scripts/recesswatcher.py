#!/usr/bin/env python2.3
# vim:sw=4:ts=4:et:nowrap

# Extact list of dates of recesses of parliament, and write a message out on
# the day of a recess start or end.  So I know they are happening when called
# from a cron job.  Writes out to a parl-recesses.txt file which we can load
# from elsewhere (PHP).  To be run every day.

import urllib
import re
import mx.DateTime
import datetime
import os
import csv
import smtplib

recess_file = os.path.expanduser('~/parldata/parl-recesses.txt')
recess_file_new = recess_file + ".new"

toaddrs = [ "parlparse" ]

today = datetime.date.today().isoformat()

url = "http://www.parliament.uk/faq/business_faq_page.cfm"

ur = urllib.urlopen(url)
co = ur.read()
ur.close()

def domail(subject, msg):
	msg = "From: The Recess Gods <francis@flourish.org>\n" +  \
		  "To: " + ", ".join(toaddrs) + "\n" + \
		  "Subject: " + subject + "\n\n" +  \
		  msg + url + "\n"
	server = smtplib.SMTP('localhost')
	server.sendmail("francis@flourish.org", toaddrs, msg)
	server.quit()

# Matches this kind of table cell:
#     <td class="editonprotabletext">^M
#     <p><font size="2">18 December 2003</font></p>^M
#     </td>^M

cells = re.findall('<td class="editonprotabletext">\s*<p><font size="2">([^<]*?)</font></p>\s*</td>', co)

assert re.search('has announced (provisional dates for )?the Commons calendar', cells.pop(0))
assert len(cells) % 3 == 0

dates = []
last_finish = 1000-01-01
while cells:
    (name, start, finish) = (cells.pop(0), cells.pop(0), cells.pop(0))
    start = (mx.DateTime.strptime(start, "%e %b %Y")+1).date
    finish = (mx.DateTime.strptime(finish, "%e %b %Y")-1).date
    assert start > last_finish
    assert finish > start
    dates.append((name, start, finish)) 
    if start == today:
		domail(name + " starts", "%s of parliament starts today %s, ends %s\n" % (name, start, finish))
    if finish == today:
        domail(name + " ends", "%s of parliament ends today %s\n" % (name, finish))
    # print "%s: %s to %s" % (name, start, finish)

# "dates" now contains a list of all the periods of recess

enddates = map(lambda x: max(x[1], x[2]), dates)
max_date = reduce(max, enddates)
# print "max_date", max_date
if max_date < today:
	print "Parliamentary recess updater in possible trouble"
	print "Unknown when next recess is - check it isn't published elsewhere"
	print ""
	print "Today is %s, last recess ended %s" % (today, max_date)
    print "Source of data: %s" % (url)

csv.writer(open(recess_file_new, "w")).writerows(dates)
os.rename(recess_file_new, recess_file)

