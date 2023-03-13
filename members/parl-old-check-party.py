#!/usr/bin/python
# 
# Old Work-In-Progress for something using old Parliament API, comparing
# parties. Would probably want reworking using new API. The purpose would be to
# check for changes against our data, and alert someone that something needs
# fixing (or longer term, fix it automatically).

import re
import urllib.request
import lxml.objectify
import sys

sys.path.append("../pyscraper")
from lords.resolvenames import lordsList

TYPES   = (
    '2 Hered Office Holders', 'Bishops and Archbishops', 'Deputy Hereditary', 'Elected Hereditary', 'Hereditary',
    'Hereditary of 1st creation', 'Hereds given LPs', 'Law Lord', 'Life peer',
)
RANKS   = ( 'Archbishop', 'Baroness', 'Bishop', 'Countess', 'Duke', 'Earl', 'Lady', 'Lord', 'Marquess', 'Prince', 'Viscount' )
GENDERS = ( 'Female', 'Male' )
PARTIES = (
    '', 'Alliance', 'Bishops', 'Conservative', 'Conservative Independent', 'Crossbench', 'Democratic Unionist',
    'Independent Labour', 'Labour', 'Labour Independent', 'Liberal Democrat', 'Non-affiliated (current Member)',
    'Other', 'Plaid Cymru', 'UK Independence Party', 'Ulster Unionist Party',
)
STATUS  = ('Active', 'Retired', 'Deceased', 'Suspended', 'Inactive', 'Disqualified', 'Resigned', 'LeaveOfAbsence') 

class Lord:
    left_date = None

    def __init__(self, lord):
        self.ids        = { 'id': lord.get('id'), 'pims':  lord.get('pimsId'), 'dods':  lord.get('dodsId') }
        self.type       = TYPES.index(lord.type)
        self.rank       = RANKS.index(lord.rank)
        self.firstName  = str(getattr(lord, 'firstName', ''))
        self.lastName   = str(lord.lastName)
        self.shortTitle = str(lord.shortTitle).replace('  ', ' ') # Used in division listings
        self.longTitle  = str(lord.longTitle).replace('Rdt Hon. ', '') # Used in debate speech
        self.party      = PARTIES.index(lord['{urn:parliament/metadata/core/2010/10/01/party}party'].partyName)
        self.website    = str(lord.get('website', ''))
        self.gender     = GENDERS.index(lord['{urn:parliament/metadata/core/2010/10/01/gender}gender'])
        self.lastOath   = str(lord.lastOathDate)[:10]

        honours = getattr(lord, '{urn:parliament/metadata/core/members/2010/10/01/honour}honours', None)
        if honours is not None:
            self.honours = [ ( str(h.name), str(h.startDate) ) for h in honours['{urn:parliament/metadata/core/2010/10/01/honour}honour'] ]

        status          = lord['{urn:parliament/metadata/core/2010/10/01/status}status']
        self.status     = STATUS[STATUS.index(status['name'])]
        self.statusInfo = status['statusInformation']

        if self.status == 'Retired':
            self.left_date = str(self.statusInfo['dateOfRetirement'])[:10]
        elif self.status == 'Deceased':
            self.left_date = str(self.statusInfo['dateOfDeath'])[:10]
        elif self.status == 'Suspended':
            start_date = str(self.statusInfo['startDate'])[:10]
            end_date = str(self.statusInfo['endDate'])[:10]
            reason = self.statusInfo['description']
            self.status = (self.status, start_date, end_date, reason)
        elif self.status == 'Inactive':
            self.left_date = str(self.statusInfo['membershipEndDate'])[:10]
        elif self.status == 'Disqualified':
            start_date = str(self.statusInfo['startDate'])[:10]
            end_date = str(self.statusInfo['endDate'])[:10]
            reason = self.statusInfo['reason']
            self.status = (self.status, start_date, end_date, reason)
        elif self.status == 'Resigned':
            self.left_date = str(self.statusInfo['dateOfResignation'])[:10]
        elif self.status == 'LeaveOfAbsence':
            assert self.party in (PARTIES.index('Non-affiliated (current Member)'), PARTIES.index('Other'))
            #self.party = PARTIES.index(self.statusInfo['party']['partyName'])
        elif self.status == 'Active':
            pass

        # Corrections
        if self.longTitle == 'The Lord McAlpine of West Green':
            self.left_date = '2010-05-21' # From House of Lords journal
        if self.longTitle == 'The Most Hon. the Marquess of Salisbury DL':
            self.status = 'Retired' # The 6th Marquess left, as I understand it
            self.left_date = '1999-11-11'
        if self.longTitle == 'The Rt Hon. the Viscount Younger of Leckie KT KCVO TD DL':
            self.type = TYPES.index('Hereds given LPs') # Not a Hereditary
        if self.longTitle == 'The Earl of Carnarvon KCVO KBE DL':
            self.type = TYPES.index('Elected Hereditary') # One of the 92

    def __str__(self):
        return '%s (%s) - %s' % ( self.longTitle, PARTIES[self.party], self.status )

# Fetch the current live information
lords = urllib.request.urlopen('http://data.parliament.uk/resources/members/api/lords/all/').read()
lords = [ Lord(lord) for lord in lxml.objectify.fromstring(lords).peer ]

for lord in lords:
    # Ignore hereditaries retired by the House of Lords Act 1999, or
    # others who retired or dided before our records begin
    if lord.status in ('Deceased', 'Retired') and lord.left_date <= '1999-11-11': continue

    # We don't show ones that haven't been introduced yet (and couple of bugs, looks like)
    if not lord.lastOath: continue

    date = lord.left_date or '2011-12-04'
    match = lordsList.MatchRevName(lord.shortTitle, date, '')

    #if '%s %s' % (lord.title, lord.lastName) in self.
    if PARTIES[lord.party] == 'Conservative' and lordsList.lords[match]['party'] == 'Con': continue
    if PARTIES[lord.party] == 'Labour' and lordsList.lords[match]['party'] == 'Lab': continue
    if PARTIES[lord.party] == 'Liberal Democrat' and lordsList.lords[match]['party'] == 'LDem': continue
    if PARTIES[lord.party] == 'Crossbench' and lordsList.lords[match]['party'] == 'XB': continue
    if PARTIES[lord.party] == 'Bishops' and lordsList.lords[match]['party'] == 'Bp': continue
    if PARTIES[lord.party] == 'Ulster Unionist Party' and lordsList.lords[match]['party'] == 'UUP': continue
    if PARTIES[lord.party] == 'UK Independence Party' and lordsList.lords[match]['party'] == 'UKIP': continue
    if PARTIES[lord.party] == 'Plaid Cymru' and lordsList.lords[match]['party'] == 'PC': continue
    if PARTIES[lord.party] == 'Plaid Cymru' and lordsList.lords[match]['party'] == 'PC': continue
    print(PARTIES[lord.party], lordsList.lords[match]['party'])

