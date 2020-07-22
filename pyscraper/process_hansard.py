#! /usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import datetime
import re
from os.path import join
from miscfuncs import toppath

from new_hansard import ParseDay


today = datetime.date.today()
yesterday = today - datetime.timedelta(1)

parser = argparse.ArgumentParser(description='Process Hansard XML.')
parser.add_argument('--from', dest='date_from', default=yesterday.isoformat(), metavar='YYYY-MM-DD')
parser.add_argument('--to', dest='date_to', default=today.isoformat(), metavar='YYYY-MM-DD')
parser.add_argument('-v', '--verbose', action='count')
ARGS = parser.parse_args()

index_filename = join(toppath, 'seen_hansard_xml.txt')
zip_directory = join(toppath, 'cmpages', 'hansardzips')
zip_dir_slash = "%s/" % zip_directory


dir_match = '\d+_((\d{4}-\d{2}-\d{2})_\d{2}:\d{2}:\d{2})$'
dirs = []
for d in os.listdir(zip_directory):
    m = re.match(dir_match, d)
    fn = join(zip_directory, d)
    if m and os.path.isdir(fn) and ARGS.date_from <= m.group(2) <= ARGS.date_to:
        dirs.append(fn)

# process the directories in date order so we do any revisions in the correct
# order
dirs.sort(key=lambda x: re.match('.*/%s' % dir_match, x).group(1))


# make sure we only look at a file once
class Entries(list):
    def __init__(self):
        entries = []
        if os.path.exists(index_filename):
            with open(index_filename) as f:
                entries = [e.strip().replace(zip_dir_slash, '') for e in f.readlines()]
        super(Entries, self).__init__(entries)

    def dump(self):
        with open(index_filename, 'w') as f:
            f.writelines("{0}\n".format(entry) for entry in self)

entries = Entries()


def find(pattern, path):
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if re.search(pattern, name):
                result.append(join(root, name).replace(zip_dir_slash, ''))
    return result


def handle_file(filename, debate_type):
    file_key = '{0}:{1}'.format(debate_type, filename)
    if file_key in entries:
        if ARGS.verbose:
            print "already seen {0}, not parsing again".format(filename)
        return False

    parser.reset()
    if ARGS.verbose:
        print "looking at {0}".format(filename)
    ret = parser.handle_file(join(zip_directory, filename), debate_type, ARGS.verbose)

    if ret == 'failed':
        print "ERROR parsing {0} {1}".format(filename, debate_type)
    elif ret == 'not-present':
        if ARGS.verbose:
            print "Nothing to parse in {0} {1}".format(filename, debate_type)
    elif ret == 'same':
        prev_file = parser.prev_file.replace(toppath, '')
        print "parsed {0}, no changes from {1}".format(filename, prev_file)
    elif ret in ('change', 'new'):
        output_file = parser.output_file.replace(toppath, '')
        print "parsed {0} to {1}".format(filename, output_file)
    else:
        output_file = parser.output_file.replace(toppath, '')
        print "parsed {0} {1} to {2}, unknown return {3}".format(filename, debate_type, output_file, ret)
    entries.append(file_key)

    return True

parser = ParseDay()
try:
    for d in dirs:
        xml_files = find('([CL]HAN|PBC).*\.xml$', d)
        for x in xml_files:
            if 'CHAN' in x:
                handle_file(x, 'debate')
                handle_file(x, 'westminhall')
            elif 'LHAN' in x:
                handle_file(x, 'lords')
            elif 'PBC' in x:
                handle_file(x, 'standing')

# this is just to make sure we record progress
except Exception:
    entries.dump()
    raise

entries.dump()
