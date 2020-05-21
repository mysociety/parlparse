#!/usr/bin/python

import os
import json
import re
import string
import copy
import sys
import datetime
import time
import codecs

from base_resolver import ResolverBase

members_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..', 'members'))

class MemberList(ResolverBase):
    import_organization_id = 'scottish-parliament'

    # This will return a list of person ID strings or None.  If there
    # are no matches, the list will be empty.  If we recognize a valid
    # speaker, but that person is not an MSP (e.g. The Convener,
    # Members, the Lord Advocate, etc.) then we return None.

    # (In fact, it's not at all clear that distinguishing the empty
    # list and None cases is actually useful.)

    # FIXME: use Set instead of lists

    def match_whole_speaker(self,speaker_name,speaker_date):

        #lfp = codecs.open("/var/tmp/all-names",'a','utf-8')
        #lfp.write("%s\t%s\n"%(speaker_date,speaker_name))
        #lfp.close()

        # if speaker_date:
        #     print speaker_name+" [on date "+speaker_date + "]"
        # else:
        #     print speaker_date+" [no date]"

        party = ''

        m = re.match('^(.*) \((Con|Lab|Labour|LD|SNP|SSP|Green|Ind|SSCUP|SCCUP|Sol)\s?\)(.*)$',speaker_name)
        if m:
            speaker_name = m.group(1) + m.group(3)
            party = m.group(2)

        # print "party is: "+party

        # Now we should have one of the following formats:
        # <OFFICE> (<NAME>) (<CONS>)    (one occurrence)
        # <NAME> (<CONS>)
        # <OFFICE> (<NAME>)
        # <NAME> (<OFFICE>)             (also rare)
        # <NAME>

        # Names are typically fullnames: firstname + " " + lastname
        #                            or: title + " " + lastname
        #                            or: title + " " + firstname + " " + lastname

        # First, check the first part:

        m = re.search('^([^\(]*)(.*)',speaker_name)
        first_part = m.group(1).strip()
        bracketed_parts = m.group(2).strip()

        all_matching_ids = ()

        ids_from_first_part = memberList.match_string_somehow(first_part,speaker_date,party,False)
        if ids_from_first_part == None:
            return None
        else:
            if len(ids_from_first_part) == 1:
                return ids_from_first_part
            # Otherwise, we try to refine this...
            ids_so_far = ids_from_first_part

        while len(bracketed_parts) > 0:
            m = re.search('\(([^\)]*)(\)(.*)|$)',bracketed_parts)
            if not m:
                break
            bracketed_part = m.group(1).strip()
            # print "   Got bracketed part: "+bracketed_part
            ids_from_bracketed_part = memberList.match_string_somehow(bracketed_part,speaker_date,party,False)
            if ids_from_bracketed_part != None:
                if len(ids_from_bracketed_part) == 1:
                    return ids_from_bracketed_part
                elif len(ids_from_bracketed_part) == 0:
                    pass
                else:
                    if len(ids_so_far) > 0:
                        # Work out the intersection...
                        ids_so_far = filter(lambda x: x in ids_from_bracketed_part,ids_so_far)
                        if len(ids_so_far) == 1:
                            return ids_so_far
                    else:
                        ids_so_far = ids_from_bracketed_part
                # Otherwise, we try to refine this...
            else:
                return None

            if m.group(3):
                bracketed_parts = m.group(3).strip()
            else:
                bracketed_parts = ''

        return ids_so_far

    # This will return a list of person ID strings or None.  If there
    # are no matches, the list will be empty.  If we recognize a valid
    # speaker, but that person is not an MSP (e.g. The Convener,
    # Members, the Lord Advocate, etc.) then we return None.

    # (In fact, it's not at all clear that distinguishing the empty
    # list and None cases is actually useful.)

    # FIXME: use Set instead of lists

    def match_string_somehow(self,s,date,party,just_name):
        s = re.sub('\s{2,}', ' ', s)

        member_ids = []

        # Sometimes the names are written Lastname, FirstNames
        # (particularly in the reports of divisions.

        comma_match = re.match('^([^,]*), (.*)',s)
        if comma_match:
            rearranged = comma_match.group(2) + " " + comma_match.group(1)
            rearranged_result = self.match_string_somehow(rearranged,date,party,just_name)
            if rearranged_result != None:
                if len(rearranged_result) > 0:
                    return rearranged_result
            else:
                return None

        # ... otherwise just carry on without any rearragement.

        if not just_name:

            office_name = s.replace('The ', '')
            office_matches = self.offices.get(office_name)
            if office_matches:
                for o in office_matches:
                    if date and ( date < o['start_date'] or 'end_date' not in o.keys() or date >= o['end_date'] ):
                        continue
                    member_ids.append(o['person_id'])
                if len(member_ids) == 1:
                    return member_ids[0]

        fullname_matches = self.fullnames.get(s)
        if fullname_matches:
            for m in fullname_matches:
                if date and date < m['start_date'] or date > m['end_date']:
                    continue
                # get the full membership details so we can check the start_reason
                mem = self.members.get(m['id'])
                if re.search('The Presiding Officer',s) and mem['start_reason'] != 'became_presiding_officer':
                    # There's some ambiguity about which of the
                    # presiding officers it is in this case...
                    continue
                if m['id'] not in member_ids:
                    member_ids.append(m['id'])
            if len(member_ids) == 1:
                return map(self.membertoperson, member_ids)

        # Now check if this begins with a title:

        title_match = re.search('^(Mr|Mgr|Sir|Ms|Mrs|Miss|Lord|Dr) (.*)',s)
        if title_match:
            title = title_match.group(1)
            rest_of_name = title_match.group(2)

            if rest_of_name == 'Home Robertson':
                rest_of_name = 'John Home Robertson'

            if rest_of_name == 'John Munro' or rest_of_name == 'Munro':
                rest_of_name = 'John Farquhar Munro'

            # We should probably deal with these by using the title
            # attributes from sp-members.xml

            if rest_of_name.lower() == 'macdonald':
                if title == 'Ms':
                    rest_of_name = 'Margo MacDonald'

            if title == 'Dr' and rest_of_name == 'Jackson':
                rest_of_name = 'Sylvia Jackson'

            fullname_matches = self.fullnames.get(rest_of_name)
            if fullname_matches:
                for m in fullname_matches:
                    if date and date < m['start_date'] or date > m['end_date']:
                        continue
                    if m['id'] not in member_ids:
                        member_ids.append(m['id'])
                if len(member_ids) == 1:
                    return map(self.membertoperson, member_ids)

            # Or if there's a single word, then this is probably just
            # a last name:

            if re.match('^[^ ]+$',rest_of_name):
                lastname_matches = self.lastnames.get(rest_of_name)
                if lastname_matches:
                    for m in lastname_matches:
                        if date and date < m['start_date'] or date > m['end_date']:
                            continue
                        if m['id'] not in member_ids:
                            member_ids.append(m['id'])
                    if len(member_ids) == 1:
                        return map(self.membertoperson, member_ids)

        if not just_name:

            constituency_matches = self.constoidmap.get(s)
            if constituency_matches:
                for c in constituency_matches:
                    # print "       Got constituency id: "+c['id']
                    members = self.considtomembermap.get(c['id'])
                    for m in members:
                        if date and date < m['start_date'] or date > m['end_date']:
                            continue
                        if m['id'] not in member_ids:
                            member_ids.append(m['id'])
                    if len(member_ids) == 1:
                        return map(self.membertoperson, member_ids)

        # Just return the string for people that aren't members, but
        # we know are ones we understand.

        if re.search('(Some [mM]embers|A [mM]ember|Several [mM]embers|Members)',s):
            # print "Got some general group of people..."
            return None

        if s in ('The Deputy Convener', 'The Convener'):
            return None

        return map(self.membertoperson, member_ids)

    def reloadJSON(self):
        super(MemberList, self).reloadJSON()

        sp_dir = os.path.dirname(__file__)
        self.import_constituencies("sp-constituencies.json")
        self.import_people_json()

        start_date = None
        end_date = None

        self.offices = { }
        with open(os.path.join(members_dir, 'sp-ministers.json')) as fp:
            offices_json = fp.read()
            offices = json.loads(offices_json)

        for office in offices:
            self.offices.setdefault(office['role'], []).append(office)

    def list(self, date=None):
        if not date:
            date = datetime.date.today().isoformat()
        matches = self.members.values()
        ids = []
        for m in matches:
            if 'start_date' in m and date >= m["start_date"] and date <= m["end_date"]:
                ids.append(m["id"])
        return ids

    def list_all_dates(self):
        matches = self.members.values()
        ids = []
        for m in matches:
            ids.append(m["id"])
        return ids

memberList = MemberList()
