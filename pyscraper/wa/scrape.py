#!/usr/bin/env python3

import datetime
import os
import re

import requests
import requests_cache
from bs4 import BeautifulSoup

FIFTH_PARLIAMENT = 401
SIXTH_PARLIAMENT = 700

DOMAIN = "https://record.senedd.wales"
HTML_PAGE_URL = "%s/XMLExport/?committee={}&page={}" % DOMAIN

wa_dir = os.path.dirname(__file__)
cmpages_dir = f"{wa_dir}/../../../parldata/cmpages/senedd"
os.makedirs(cmpages_dir, exist_ok=True)

cache_path = os.path.join(wa_dir, "cache")
requests_cache.install_cache(cache_path, expire_after=60 * 60 * 12)

today = datetime.date.today()
forcescrape = False
daily = True


def compare(old, new):
    old = re.sub(b'generated="[^"]*"', b"", old)
    new = re.sub(b'generated="[^"]*"', b"", new)
    return old == new


def print_diff(old, new):
    import difflib

    old = old.decode("utf-8").split("\n")
    new = new.decode("utf-8").split("\n")
    diff = difflib.unified_diff(old, new)
    for d in diff:
        print(d)


def reorder(data):
    votes = re.findall(b"(?s)<XML_Plenary_Vote>.*?</XML_Plenary_Vote>", data)
    votes.sort(key=lambda d: int(re.search(b"<ID>(.*?)</ID>", d).group(1)))
    reordered = b"\r\n  ".join(votes)
    data = re.sub(b"(?s)<XML_Plenary_Vote>.*</XML_Plenary_Vote>", reordered, data)
    return data


def write_data(url, typ, date):
    url = DOMAIN + url
    os.makedirs(f"{cmpages_dir}/{typ}", exist_ok=True)
    filename = f"{cmpages_dir}/{typ}/senedd{date}.xml"
    data = requests.get(url).content
    if typ == "votes":
        # Votes sometimes change order in the source data :-/
        data = reorder(data)
    save = "scraping"
    if os.path.isfile(filename):
        current = open(filename, "rb").read()
        if compare(current, data) and not forcescrape:
            save = ""
        else:
            # print_diff(current, data)
            save = "rescraping"

    if save:
        print(f"Senedd {save} {url} {typ}/senedd{date}.xml")
        open(filename, "wb").write(data)


if daily:
    parls = (SIXTH_PARLIAMENT,)
else:
    parls = (FIFTH_PARLIAMENT, SIXTH_PARLIAMENT)

for parl in parls:
    page = 1
    while page:
        url = HTML_PAGE_URL.format(parl, page)
        text = requests.get(url).text
        if "See More" in text and not daily:
            page += 1
        else:
            page = 0

        soup = BeautifulSoup(text, "lxml")
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            date, typ, bilingual, welsh, english, qnr, votes = tds
            assert next(typ.stripped_strings) in ("Plenary - Fifth Senedd", "Plenary")

            date = next(date.stripped_strings)
            date = datetime.datetime.strptime(date, "%d/%m/%Y %H:%M").date()
            if date == today:
                continue

            write_data(bilingual.a["href"], "plenary", date)
            if qnr.a:
                write_data(qnr.a["href"], "qnr", date)
            if votes.a:
                write_data(votes.a["href"], "votes", date)
