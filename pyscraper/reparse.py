#! /usr/bin/env python

import argparse
import os
import re
from os.path import join

from miscfuncs import toppath
from new_hansard import ParseDay

index_filename = join(toppath, 'seen_hansard_xml.txt')
reparse_filename = join(toppath, 'reparse_hansard_xml.txt')
zip_directory = join(toppath, 'cmpages', 'hansardzips')
zip_dir_slash = "%s/" % zip_directory
line_re = re.compile(r'^[^:]*:(.*/)([^/]*)$')
files = {}

parser = argparse.ArgumentParser(description='Process Hansard XML.')
parser.add_argument('-v', '--verbose', action='count')
ARGS = parser.parse_args()

# make sure we only look at a file once
class Entries(list):
    def __init__(self):
        entries = []
        if os.path.exists(reparse_filename):
            with open(reparse_filename) as f:
                entries = [e.strip().replace(zip_dir_slash, '') for e in f.readlines()]
        super(Entries, self).__init__(entries)

    def dump(self):
        with open(reparse_filename, 'w') as f:
            f.writelines("{0}\n".format(entry) for entry in self)

entries = Entries()


def handle_file(filename, debate_type):
    file_key = '{0}:{1}'.format(
        debate_type,
        filename.strip().replace(zip_dir_slash, '')
    )
    if file_key in entries:
        if ARGS.verbose:
            print "already seen {0}, not re-parsing again".format(filename)
        return False

    parser.reset()
    if ARGS.verbose:
        print "looking at {0}".format(filename)
    ret = parser.handle_file(filename, debate_type, ARGS.verbose)

    if ret == 'failed':
        print "ERROR parsing {0} {1}".format(filename, debate_type)
    elif ret == 'not-present':
        print "Nothing to parse in {0} {1}".format(filename, debate_type)
    elif ret == 'same':
        print "parsed {0} {1}, no changes from {2}".format(
            filename, debate_type, parser.prev_file
        )
    elif ret in ('change', 'new'):
        print "parsed {0} {1} to {2}".format(
            filename, debate_type, parser.output_file
        )
    else:
        print "parsed {0} {1} to {2}, unknown return {3}".format(
            filename, debate_type, parser.output_file, ret
        )
    entries.append(file_key)

    return True

with open(index_filename) as lines:
    for line in lines:
        matches = line_re.search(line.strip())
        if matches:
            files[matches.group(2)] = matches.group(1) + matches.group(2)

parser = ParseDay()

try:
    for filename in files.values():
        f = join(toppath, 'cmpages', 'hansardzips', filename)
        if 'CHAN' in f:
            handle_file(f, 'debate')
            handle_file(f, 'westminhall')
        elif 'LHAN' in f:
            handle_file(f, 'lords')
        elif 'PBC' in f:
            handle_file(f, 'standing')

# this is just to make sure we record progress
except Exception:
    entries.dump()
    raise

entries.dump()
