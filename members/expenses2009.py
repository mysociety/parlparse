#!/usr/local/bin/python2.3
# -*- coding: latin-1 -*-

# Makes file connecting MP ids to their expenses

import re
import csv
import sys
import sets

sys.path.append("../pyscraper/")
from resolvemembernames import memberList

fout = open('expenses200809.xml', 'w')
fout.write('''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>\n''')

content = csv.reader(open('../rawdata/mpsexpenses200809.txt'))
for cols in content:
    if cols[0] == 'ID': continue # Header
    #if cols[1] == 'TOTALS': continue # Footer
    name = cols[0].decode('utf-8')
    #party = cols[2]
    #cons = cols[3].decode('utf-8')
    money = cols[1:]
    money = map(lambda x: re.sub("\xa3","", x), money)
    money = map(lambda x: re.sub(",","", x), money)
    id = None
    cons = None
    id, found_name, newcons =  memberList.matchfullnamecons(name, cons, '2008-05-01')
    if not id:
        id, found_name, newcons =  memberList.matchfullnamecons(name, cons, '2008-12-01')
    if not id:
        raise Exception, "Failed to find MP %s" % name
    pid = memberList.membertoperson(id)
    fout.write('<personinfo id="%s" ' % pid)
    expense_cols = [ '1', '2', '3', '4', 'total_travel', 'stationery', '9', 'comms_allowance' ]
    for i in range(8):
        col = expense_cols[i]
        if col != '':
            fout.write('expenses2009_col%s="%s" ' % (col, money[i].strip()))
    fout.write('/>\n')

content = csv.reader(open('../rawdata/mpsexpenses200809travel.csv'))
for cols in content:
    if cols[0] == '' or cols[0] == 'Member' or 'travel expenditure' in cols[0]: continue # Header
    name = re.sub('(^.*?), (.*)$', r'\2 \1', cols[0].decode('utf-8'))
    money = cols[1:]
    money = map(lambda x: re.sub("\xa3","", x.decode('utf-8')), money)
    money = map(lambda x: re.sub(",","", x), money)
    id = None
    cons = None
    id, found_name, cons =  memberList.matchfullnamecons(name, cons, '2008-04-01')
    if not id:
        id, found_name, newcons =  memberList.matchfullnamecons(name, cons, '2008-12-01')
    if not id:
        raise Exception, "Failed to find MP %s" % name
    pid = memberList.membertoperson(id)
    fout.write('<personinfo id="%s" ' % pid)
    expense_cols = [
        'mp_reg_travel_a', 'mp_reg_travel_b', 'mp_reg_travel_c', 'mp_reg_travel_d',
        'mp_other_travel_a', 'mp_other_travel_b', 'mp_other_travel_c', 'mp_other_travel_d',
		'spouse_travel_a', 'spouse_travel_b',
		'family_travel_a', 'family_travel_b',
		'employee_travel_a', 'employee_travel_b'
    ]
    for i in range(14):
        col = expense_cols[i]
        if col != '':
            fout.write('expenses2009_col%s="%s" ' % (col, money[i].strip()))
    fout.write('/>\n')

sys.stdout.flush()

fout.write('</publicwhip>\n')
fout.close()

