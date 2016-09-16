#!/usr/bin/env python
# vim:sw=4:ts=4:et:nowrap

import urllib
import mx.DateTime
import json
from os.path import join
from bs4 import BeautifulSoup

from miscfuncs import toppath

recess_file = join(toppath, 'recessdates.json')

def get_recess_dates(url):
    page = urllib.urlopen(url)
    content = page.read()
    page.close()

    soup = BeautifulSoup(content, 'html.parser')

    dates = soup.find(id='ctl00_ctl00_FormContent_SiteSpecificPlaceholder_PageContent_ctlMainBody_wrapperDiv')

    today = mx.DateTime.today().date
    recess_dates = []
    for row in dates.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) == 3:
            name = cells[0].text
            start_date = mx.DateTime.DateFrom(cells[1].text).date
            end_date = mx.DateTime.DateFrom(cells[2].text).date

            recess_dates.append({ 'name': name, 'start': start_date, 'end': end_date})

    return { 'last_update': today, 'recesses': recess_dates}

urls = {
    'lords': 'http://www.parliament.uk/about/faqs/house-of-lords-faqs/lords-recess-dates/',
    'commons': "http://www.parliament.uk/about/faqs/house-of-commons-faqs/business-faq-page/recess-dates/"
}

data = {}
for house in urls.keys():
    data[house] = get_recess_dates(urls[house])

with open(recess_file, 'w') as f:
    json.dump(data, f, indent=4, sort_keys=True)

