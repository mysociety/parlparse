#! /usr/bin/env python2.4
# vim:sw=4:ts=4:et:nowrap

import datetime
import sys
import os

sys.path.append("../pyscraper")
from resolvemembernames import memberList

today = datetime.date.today().isoformat()

lines = file("../rawdata/wtt-constituencies.txt").readlines()

for line in lines:
    cons = line.strip()
    cancons = memberList.canonicalcons(cons, today)
    print cancons



