import re
import os
import sys
import string
import urllib
import copy

import mx.DateTime

class wamemberrecord:
    def __init__(self):
        self.title = ''
        self.waid = ''
        self.firstname = ''
        self.lastname = ''
        self.constituency = ''
        self.constituencytype = ''
        self.fromdate = ''
        self.todate = ''
        self.wa_internal_id = ''

    def OutRecord(self, fout):
        fout.write('<member_wa\n')
        fout.write('\tid="uk.org.publicwhip/member/%s"\n' % self.waid)
        fout.write('\tfirstname="%s"\n' % self.firstname)
        fout.write('\tlastname="%s"\n' % self.lastname)
        fout.write('\tconstituency="%s"\n' % self.constituency)
        fout.write('\tconstituencytype="%s"\n' % self.constituencytype)
        fout.write('\twa_internal_id="%s"\n' % self.wa_internal_id)
        fout.write('\tfromdate="%s"\n' % self.fromdate)
        fout.write('\ttodate="%s"\n' % self.todate)
        fout.write('/>\n')

class wamembersrecords:
    def __init__(self):
        self.warec = [ ]
        self.currentWaId = 120000

    def AddRecord(self, nr):
        # should check for existing record here
        self.warec.append(nr)

    def GenerateIDs(self):
        for r in self.warec:
            r.waid = self.currentWaId
            self.currentWaId += 1

def LoadTableWithFromDate(fpath, fname):
    fin = open(os.path.join(fpath, fname), "r")
    text = fin.read()
    fin.close()
    getdates = 0

    was = wamembersrecords();
    first = wamembersrecords();
    second = wamembersrecords();
    third = wamembersrecords();
    current = wamembersrecords();

    firstend = mx.DateTime.DateFrom('30/04/2003')
    secondend = mx.DateTime.DateFrom('02/05/2007')
    thirdend = mx.DateTime.DateFrom('31/03/2011')

    # extract the rows
    rows = re.findall('<tr[^>]*>\s*([\s\S]*?)\s*</tr>(?i)', text)
    for row in rows:
        #print row

        # extract the columns of a row
        row = re.sub('(&nbsp;|\s)+', ' ', row)
        cols = re.findall('<td[^>]*>(?:<p[^>]*><a[^>]*UID=)(\d+)(?:"[^>]*>)([\s\S]*?)(?:</a></p>)(?:\s*<p>[\s\S]*</p>\s*)*</td>\s*<td>([\s\S]*)</td>\s*<td>([\s\S]*)</td>\s*<td>([\s\S]*)</td>(?im)', row)

        if not cols or not cols[0]:
            print 'skipping'
            continue

        #print '--------------'
        #print cols
        #print cols[0][0]
        #print cols[0][1]
        #print cols[0][2]
        #print cols[0][3]
        #print cols[0][4]

        wamem = wamemberrecord()

        names = cols[0][1].split()
        print names
        wamem.firstname = names[0]
        wamem.lastname = names[1]

        wamem.wa_internal_id = cols[0][0]
        if cols[0][3]:
            wamem.constituency = cols[0][3]
            wamem.constituencytype = 'constituency'
        elif cols[0][4]:
            wamem.constituency = cols[0][4]
            wamem.constituencytype = 'region'
        else:
            print "no constituency for " % cols[0][1]
            continue

        wa_details = ''
        fname = 'member_%s.html' % wamem.wa_internal_id
        if getdates:
            url = 'http://www.senedd.assemblywales.org/mgUserInfo.aspx?UID=%s' % wamem.wa_internal_id
            ur = urllib.urlopen(url)
            wa_details = ur.read()
            ur.close()
            cache = open(os.path.join('../rawdata/wamembers', fname), "w")
            cache.write(wa_details)
            cache.close
        else:
            cache = open(os.path.join('../rawdata/wamembers', fname), "r")
            wa_details = cache.read()
            cache.close

        end_dates = re.findall('-\s*(\d+&#47;\d+&#47;\d+)\s*</li>', wa_details)
        start_dates = re.findall('<li>\s*(\d+&#47;\d+&#47;\d+)\s*-', wa_details)
        for start_date,end_date in zip(start_dates,end_dates):
            start_date = start_date.replace('&#47;', '/')
            end_date = end_date.replace('&#47;', '/')
            print '%s - %s' % (start_date, end_date)
            wa_prev = copy.copy(wamem)
            wa_prev.fromdate = start_date
            wa_prev.todate = end_date

            end_datetime = mx.DateTime.DateFrom(end_date)
            if end_datetime <= firstend:
                first.AddRecord(wa_prev)
            elif end_datetime <= secondend:
                second.AddRecord(wa_prev)
            elif end_datetime <= thirdend:
                third.AddRecord(wa_prev)

        if len(start_dates) > len(end_dates):
            date = start_dates.pop()
            date = date.replace('&#47;', '/')
            wamem.enddate = ''
            wamem.fromdate = date
            print date

        current.AddRecord(wamem)

    was.warec.extend(first.warec)
    was.warec.extend(second.warec)
    was.warec.extend(third.warec)
    was.warec.extend(current.warec)

    was.GenerateIDs()
    return was

was = LoadTableWithFromDate('../rawdata/wamembers', 'wa_members.html')

waxml = open('wamembers.xml', "w")
waxml.write("""<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>
""")

for wa in was.warec:
    wa.OutRecord(waxml)

waxml.write("\n</publicwhip>\n")
waxml.close()
