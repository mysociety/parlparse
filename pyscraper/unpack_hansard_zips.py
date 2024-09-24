#!/usr/bin/env python3

import datetime
import errno
import json
import os
import re
import subprocess
from os.path import exists, isdir, join
from tempfile import NamedTemporaryFile

import requests
from lxml import etree
from miscfuncs import toppath

atom_feed_url = "http://api.data.parliament.uk/resources/files/feed?dataset=12"
zip_directory = join(toppath, "cmpages", "hansardzips")
json_index_filename = join(toppath, "hansardfeed.json")
atom_ns = {"namespaces": {"ns": "http://www.w3.org/2005/Atom"}}


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and isdir(path):
            pass
        else:
            raise


def parse_datetime(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S+01:00")


def entry_directory(entry):
    return "{}_{}".format(
        entry["id"],
        entry["entry_updated"].replace(" ", "_"),
    )


def get_atom_entries(hansard_atom_url):
    r = requests.get(hansard_atom_url)
    tree = etree.fromstring(r.content)

    result = [
        {
            "entry_updated": str(
                parse_datetime(e.xpath("ns:updated", **atom_ns)[0].text)
            ),
            "id": int(
                re.search(r"/(\d+)\.zip$", e.xpath("ns:id", **atom_ns)[0].text).group(1)
            ),
            "link_url": e.xpath("ns:link", **atom_ns)[0].attrib["href"],
        }
        for e in tree.xpath("/ns:feed/ns:entry", **atom_ns)
    ]
    for entry in result:
        entry["directory"] = entry_directory(entry)
    return result


def entry_key(entry):
    return "|".join(str(entry[k]) for k in ("entry_updated", "id"))


# Load the existing entries:

if exists(json_index_filename):
    with open(json_index_filename) as f:
        entries = json.load(f)
else:
    entries = []

existing_keys = set(entry_key(e) for e in entries)

# Now add any entries that weren't already in the feed:

for new_entry in sorted(
    get_atom_entries(atom_feed_url), key=lambda e: (e["entry_updated"], e["id"])
):
    if entry_key(new_entry) not in existing_keys:
        entries.append(new_entry)

# Write out the updated JSON:

with open(json_index_filename, "w") as f:
    json.dump(entries, f, indent=4, sort_keys=True)


class UnzipError(Exception):
    pass


def extract_zip(zip_filename, destination_directory):
    unzip_command = ["unzip", "-q", zip_filename, "-d", destination_directory]
    p = subprocess.Popen(unzip_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, _ = p.communicate()
    # We get return code 1 quite often ("a warning was output")
    # because some of these zip files use backslash as a directory
    # separator:
    if p.returncode not in (0, 1):
        raise UnzipError("Excuting {0} failed".format(" ".join(unzip_command)))
    # Walk the whole directory before processing the unpacked files,
    # so we don't modified the tree while recursing through it:
    walked = os.walk(destination_directory)
    for dirpath, dirnames, filenames in walked:
        for filename in filenames:
            full_filename = join(dirpath, filename)
            m = re.search(r"^(.*)\.zip$", filename, re.I)
            if m:
                # Then there's a ZIP file in the zip file - create a
                # directory for it and unpack it.
                subdir = m.group(1)
                full_subdir = join(dirpath, subdir)
                mkdir_p(full_subdir)
                try:
                    extract_zip(full_filename, full_subdir)
                    os.remove(full_filename)
                except UnzipError:
                    print("Unpacking failed for {0}".format(full_subdir))


# Now download any new entries and unpack the zip files:

for entry in entries:
    subdir = join(zip_directory, entry["directory"])
    if exists(subdir):
        continue
    mkdir_p(subdir)

    r = requests.get(entry["link_url"])
    ntf = NamedTemporaryFile(
        prefix="{}-".format(entry["id"]), suffix=".zip", delete=False
    )
    ntf.write(r.content)
    ntf.close()

    print(
        "Unpacking top level zip file {}, downloaded from {}".format(
            ntf.name, entry["link_url"]
        )
    )

    try:
        extract_zip(ntf.name, subdir)
    except UnzipError:
        print("Unpacking failed, removing {0}".format(subdir))
        # shutil.rmtree(subdir)
        # raise
