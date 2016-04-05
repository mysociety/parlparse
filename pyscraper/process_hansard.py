#! /usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import datetime
import time
import fnmatch
import glob
import re
from os.path import join
from miscfuncs import toppath

from new_hansard import ParseDay


parser = argparse.ArgumentParser(description='Process Hansard XML.')
parser.add_argument('--from', dest='date_from', default=datetime.date.today().isoformat(), metavar='YYYY-MM-DD')
parser.add_argument('--to', dest='date_to', default=datetime.date.today().isoformat(), metavar='YYYY-MM-DD')
ARGS = parser.parse_args()


def find(pattern, path):
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(os.path.join(root, name))
    return result

index_filename = join(toppath, 'seen_hansard_xml.txt')
zip_directory = join(toppath, 'cmpages', 'hansardzips')


dir_match = '\d+_((\d{4}-\d{2}-\d{2})_\d{2}:\d{2}:\d{2})$'
dirs = []
for d in os.listdir(zip_directory):
    m = re.match(dir_match, d)
    if m:
        date = m.group(2)
        if ARGS.date_from <= date <= ARGS.date_to:
            dirs.append(join(zip_directory, d))


time_match = '.*/%s' % dir_match
timeformat = '%Y-%m-%d_%H:%M:%S'
# process the directories in date order so we do any revisions in the correct
# order
dirs.sort(key=lambda x: time.strptime(re.match(time_match, x).groups(1)[0], timeformat)[0:6])

# make sure we only look at a file once
entries = []
if os.path.exists(index_filename):
    with open(index_filename) as f:
        entries = [e.strip() for e in f.readlines()]

# in case the file is present but empty
if entries is None:
    entries = []


def handle_file(parser, entries, filename, debate_type):
    file_key = '{0}:{1}'.format(debate_type, filename)
    if file_key in entries:
        print "already seen {0}, not parsing again".format(filename)
        return entries, False

    parser.handle_file(filename, debate_type)
    print "parsed {0} file to {1}".format(debate_type, parser.output_file)
    entries.append(file_key)

    return entries, True

try:
    for d in dirs:
        if os.path.isdir(d):
            p = ParseDay()
            xml_files = find('*.xml', d)
            for x in xml_files:
                print "parsing {0}".format(x)
                p.reset()
                if re.search('CHAN', x):
                    for dt in ['debate', 'westminhall']:
                        entries, parsed = handle_file(p, entries, x, dt)
                        p.reset()
                elif re.search('LHAN', x):
                    entries, parsed = handle_file(p, entries, x, 'lords')
                elif re.search('PBC', x):
                    entries, parsed = handle_file(p, entries, x, 'standing')

# this is just to make sure we record progress
except Exception:
    with open(index_filename, 'w') as f:
        f.writelines("{0}\n".format(entry) for entry in entries)
    raise

with open(index_filename, 'w') as f:
    f.writelines("{0}\n".format(entry) for entry in entries)
