import datetime
import json
import os
import re
from typing import Iterable, Optional, TypeVar

from ..base_resolver import ResolverBase
from .common import non_tag_data_in, tidy_string

members_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..", "members")
)

T = TypeVar("T")


def first(iterable: Iterable[T]) -> T:
    for element in iterable:
        if element:
            return element
    return None


class MemberList(ResolverBase):
    import_organization_id = "scottish-parliament"

    # This will return a list of person ID strings or None.  If there
    # are no matches, the list will be empty.  If we recognize a valid
    # speaker, but that person is not an MSP (e.g. The Convener,
    # Members, the Lord Advocate, etc.) then we return None.

    # (In fact, it's not at all clear that distinguishing the empty
    # list and None cases is actually useful.)

    # FIXME: use Set instead of lists

    def match_whole_speaker(self, speaker_name, speaker_date):
        # lfp = codecs.open("/var/tmp/all-names",'a','utf-8')
        # lfp.write("%s\t%s\n"%(speaker_date,speaker_name))
        # lfp.close()

        # if speaker_date:
        #     print speaker_name+" [on date "+speaker_date + "]"
        # else:
        #     print speaker_date+" [no date]"

        party = ""
        m = re.match(
            "^(.*) \((Con|Lab|Labour|LD|SNP|SSP|Green|Ind|SSCUP|SCCUP|Sol)\s?\)(.*)$",
            speaker_name,
        )
        if m:
            speaker_name = m.group(1) + m.group(3)
            party = m.group(2)

        # print "party is: "+party

        # Now we should have one of the following formats:
        # <OFFICE> (<NAME>) (<CONS>)    (one occurrence)
        # <NAME> (<CONS>)
        # <OFFICE> (<NAME>)
        # <NAME> (<OFFICE>)             (also rare)
        # <question no.> <NAME> (<CONS>)
        # <NAME>

        # Names are typically fullnames: firstname + " " + lastname
        #                            or: title + " " + lastname
        #                            or: title + " " + firstname + " " + lastname

        # First, check the first part:

        m = re.search("^([^\(]*)(.*)", speaker_name)
        first_part = m.group(1).strip()
        bracketed_parts = m.group(2).strip()
        ids_from_first_part = memberList.match_string_somehow(
            first_part, speaker_date, party, False
        )

        if ids_from_first_part is None and bracketed_parts:
            ids_from_first_part = memberList.match_string_somehow(
                bracketed_parts, speaker_date, party, False
            )

        if ids_from_first_part is None:
            return None
        else:
            if len(ids_from_first_part) == 1:
                return ids_from_first_part
            # Otherwise, we try to refine this...
            ids_so_far = ids_from_first_part

        while len(bracketed_parts) > 0:
            m = re.search("\(([^\)]*)(\)(.*)|$)", bracketed_parts)
            if not m:
                break
            bracketed_part = m.group(1).strip()
            # print "   Got bracketed part: "+bracketed_part
            ids_from_bracketed_part = memberList.match_string_somehow(
                bracketed_part, speaker_date, party, False
            )
            if ids_from_bracketed_part is not None:
                if len(ids_from_bracketed_part) == 1:
                    return ids_from_bracketed_part
                elif len(ids_from_bracketed_part) == 0:
                    pass
                else:
                    if len(ids_so_far) > 0:
                        # Work out the intersection...
                        ids_so_far = [
                            x for x in ids_so_far if x in ids_from_bracketed_part
                        ]
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
                bracketed_parts = ""

        return ids_so_far

    # This will return a list of person ID strings or None.  If there
    # are no matches, the list will be empty.  If we recognize a valid
    # speaker, but that person is not an MSP (e.g. The Convener,
    # Members, the Lord Advocate, etc.) then we return None.

    # (In fact, it's not at all clear that distinguishing the empty
    # list and None cases is actually useful.)

    # FIXME: use Set instead of lists

    def match_string_somehow(self, s, date, party, just_name):
        # in the str '2. Sarah Boyack (Lothian) (Lab)' we want to remove the '2. ' bit
        s = re.sub(r"^\d+\.\s", "", s)

        s = re.sub("\s{2,}", " ", s)

        s = s.replace("O\u2019", "O'")
        if s == "Katy Clark" and date >= "2020-09-03":
            s = "Baroness Clark of Kilwinning"

        member_ids = []

        # Sometimes the names are written Lastname, FirstNames
        # (particularly in the reports of divisions.

        comma_match = re.match("^([^,]*), (.*)", s)
        if comma_match:
            rearranged = comma_match.group(2) + " " + comma_match.group(1)
            rearranged_result = self.match_string_somehow(
                rearranged, date, party, just_name
            )
            if rearranged_result is not None:
                if len(rearranged_result) > 0:
                    return rearranged_result
            else:
                return None

        # ... otherwise just carry on without any rearragement.

        if not just_name:
            office_name = s.replace("The ", "")
            office_matches = self.offices.get(office_name)
            if office_matches:
                for o in office_matches:
                    if date and (
                        date < o["start_date"]
                        or "end_date" not in list(o.keys())
                        or date >= o["end_date"]
                    ):
                        continue
                    member_ids.append(o["person_id"])
                if len(member_ids) == 1:
                    return member_ids[0]

        fullname_matches = self.fullnames.get(s)
        if fullname_matches:
            for m in fullname_matches:
                if date and date < m["start_date"] or date > m["end_date"]:
                    continue
                # get the full membership details so we can check the start_reason
                mem = self.members.get(m["id"])
                if (
                    re.search("The Presiding Officer", s)
                    and mem["start_reason"] != "became_presiding_officer"
                ):
                    # There's some ambiguity about which of the
                    # presiding officers it is in this case...
                    continue
                if m["id"] not in member_ids:
                    member_ids.append(m["id"])
            if len(member_ids) == 1:
                return list(map(self.membertoperson, member_ids))

        # Now check if this begins with a title:

        title_match = re.search("^(Mr|Mgr|Sir|Ms|Mrs|Miss|Lord|Dr\.?) (.*)", s)
        if title_match:
            title = title_match.group(1)
            rest_of_name = title_match.group(2)

            if rest_of_name == "Home Robertson":
                rest_of_name = "John Home Robertson"

            if rest_of_name == "John Munro" or rest_of_name == "Munro":
                rest_of_name = "John Farquhar Munro"

            # We should probably deal with these by using the title
            # attributes from sp-members.xml

            if rest_of_name.lower() == "macdonald":
                if title == "Ms":
                    rest_of_name = "Margo MacDonald"

            if title == "Dr" and rest_of_name == "Jackson":
                rest_of_name = "Sylvia Jackson"

            fullname_matches = self.fullnames.get(rest_of_name)
            if fullname_matches:
                for m in fullname_matches:
                    if date and date < m["start_date"] or date > m["end_date"]:
                        continue
                    if m["id"] not in member_ids:
                        member_ids.append(m["id"])
                if len(member_ids) == 1:
                    return list(map(self.membertoperson, member_ids))

            # Or if there's a single word, then this is probably just
            # a last name:

            if re.match("^[^ ]+$", rest_of_name):
                lastname_matches = self.lastnames.get(rest_of_name)
                if lastname_matches:
                    for m in lastname_matches:
                        if date and date < m["start_date"] or date > m["end_date"]:
                            continue
                        if m["id"] not in member_ids:
                            member_ids.append(m["id"])
                    if len(member_ids) == 1:
                        return list(map(self.membertoperson, member_ids))

        if not just_name:
            constituency_matches = self.constoidmap.get(s)
            if constituency_matches:
                for c in constituency_matches:
                    # print "       Got constituency id: "+c['id']
                    members = self.considtomembermap.get(c["id"])
                    for m in members:
                        if date and date < m["start_date"] or date > m["end_date"]:
                            continue
                        if m["id"] not in member_ids:
                            member_ids.append(m["id"])
                    if len(member_ids) == 1:
                        return list(map(self.membertoperson, member_ids))

        # Just return the string for people that aren't members, but
        # we know are ones we understand.

        if re.search("(Some [mM]embers|A [mM]ember|Several [mM]embers|Members)", s):
            # print "Got some general group of people..."
            return None

        if s in ("The Deputy Convener", "The Convener"):
            return None

        return list(map(self.membertoperson, member_ids))

    def reloadJSON(self):
        super(MemberList, self).reloadJSON()

        self.import_constituencies("sp-constituencies.json")
        self.import_people_json()

        self.offices = {}
        with open(os.path.join(members_dir, "sp-ministers.json")) as fp:
            offices_json = fp.read()
            offices = json.loads(offices_json)

        for office in offices:
            self.offices.setdefault(office["role"], []).append(office)

    def list(self, date=None):
        if not date:
            date = datetime.date.today().isoformat()
        ids = []
        for m in self.members.values():
            if "start_date" in m and date >= m["start_date"] and date <= m["end_date"]:
                ids.append(m["id"])
        return ids

    def list_all_dates(self):
        ids = []
        for m in self.members.values():
            ids.append(m["id"])
        return ids


memberList = MemberList()


member_vote_re = re.compile(
    """
        ^                               # Beginning of the string
        (?P<last_name>[^,\(\)0-9:]+)    # ... last name, >= 1 non-comma characters
        ,                               # ... then a comma
        \s*                             # ... and some greedy whitespace
        (?P<first_names>[^,\(\)0-9:]*?) # ... first names, a minimal match of any characters
        \s*\(\(?                        # ... an arbitrary amount of whitespace and an open banana
                                        #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9:]*?) # ... constituency, a minimal match of any characters
        \)\s*\(                         # ... close banana, whitespace, open banana
        (?P<party>\D*?)                 # ... party, a minimal match of any characters
        \)?                             # ... close banana (might be missing!)
    (?:\s*\[?Proxy[ ]vote[ ]cast[ ]by.*?\]?)? # ... optional proxy vote text
        $                               # ... end of the string
""",
    re.VERBOSE,
)

member_vote_fullname_re = re.compile(
    """
        ^                               # Beginning of the string
        (?P<full_name>[^,\(\)0-9:]+)    # ... full name, >= 1 non-comma characters
        \s*\(\(?                        # ... an arbitrary amout of whitespace and an open banana
                                        #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9:]*?) # ... constituency, a minimal match of any characters
        \)\s*\(                         # ... close banana, whitespace, open banana
        (?P<party>\D*?)                 # ... party, a minimal match of any characters
        \)                              # ... close banana
        $                               # ... end of the string
""",
    re.VERBOSE,
)

member_vote_just_constituency_re = re.compile(
    """
        ^                               # Beginning of the string
        (?P<last_name>[^,\(\)0-9:]+)    # ... last name, >= 1 non-comma characters
        ,                               # ... then a comma
        \s*                             # ... and some greedy whitespace
        (?P<first_names>[^,\(\)0-9:]*?) # ... first names, a minimal match of any characters
        \s*\(\(?                        # ... an arbitrary amout of whitespace and an open banana
                                        #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9:]*?) # ... constituency, a minimal match of any characters
        \)\s*                           # ... close banana, whitespace
        $                               # ... end of the string
""",
    re.VERBOSE,
)

SPEAKERS_DEBUG = False


def log_speaker(speaker, date, message):
    if SPEAKERS_DEBUG:
        with open("speakers.txt", "a") as fp:
            fp.write(str(date) + ": [" + message + "] " + speaker + "\n")


class IDCache:
    def __init__(self):
        self.cache = {}

    def check(self, key: Optional[str]) -> Optional[str]:
        if key is not None:
            return self.cache.get(key, None)
        else:
            return None

    def set(self, key: Optional[str], value: str):
        if key:
            self.cache[key] = value
        return value


id_cache = IDCache()


def get_unique_person_id(
    tidied_speaker: str, on_date: str, lookup_key: Optional[str] = None
):
    # check we haven't cached this one first
    if v := id_cache.check(lookup_key):
        return v

    ids = memberList.match_whole_speaker(tidied_speaker, str(on_date))
    if ids is None:
        # This special return value (None) indicates that the speaker
        # is something we know about, but not an MSP (e.g Lord
        # Advocate)
        return None
    elif len(ids) == 0:
        log_speaker(tidied_speaker, str(on_date), "missing")
        return None
    elif len(ids) == 1:
        # cache for future lookup
        return id_cache.set(lookup_key, ids[0])
    else:
        raise Exception(
            f"The speaker '{tidied_speaker}' could not be resolved, found: {ids}"
        )


def is_member_vote(element: str, vote_date: str, expecting_a_vote=True):
    """Returns a speaker ID if this looks like a member's vote in a division

    Otherwise returns None.  If it looks like a vote, but the speaker
    can't be identified, this throws an exception.  As an example:

    >>> is_member_vote('Something random...', '2012-11-12')
    >>> is_member_vote('Baillie, Jackie (Dumbarton) (Lab)', '2012-11-12')
    u'uk.org.publicwhip/member/80476'
    >>> is_member_vote('Alexander, Ms Wendy (Paisley North) (Lab)', '2010-05-12')
    u'uk.org.publicwhip/member/80281'
    >>> is_member_vote('Purvis, Jeremy (Tweeddale, Ettrick and Lauderdale)', '2005-05-18')
    u'uk.org.publicwhip/member/80101'

    Now some examples that should be ignored:

    >>> is_member_vote(': SP 440 (EC Ref No 11766/99, COM(99) 473 final)', '1999-11-23')
    >>> is_member_vote('SP 666 (EC Ref No 566 99/0225, COM(99) (CNS))', '2000-02-08')
    >>> is_member_vote('to promote a private bill, the company relied on its general power under section 10(1)(xxxii)', '2006-05-22')

    And one that should throw an exception:

    >>> is_member_vote('Lebowski, Jeffrey (Los Angeles) (The Dude)', '2012-11-12')
    Traceback (most recent call last):
      ...
    Exception: A voting member 'Jeffrey Lebowski (Los Angeles)' couldn't be resolved

    If expecting_a_vote is False, then don't throw an exception if
    the name can't be resolved:

    >>> is_member_vote('Lebowski, Jeffrey (Los Angeles) (The Dude)', '2012-11-12', expecting_a_vote=False)

    Also try resolving names that aren't comma-reversed:

    >>> is_member_vote('Brian Adam (North-East Scotland) (SNP)', '1999-11-09')
    u'uk.org.publicwhip/member/80129'

    """
    tidied = tidy_string(non_tag_data_in(element))

    def from_first_and_last(m):
        return m and "%s %s (%s)" % (
            m.group("first_names"),
            m.group("last_name"),
            m.group("constituency"),
        )

    def from_full(m):
        return m and m.group("full_name")

    vote_matches = (
        (member_vote_re, from_first_and_last),
        (member_vote_just_constituency_re, from_first_and_last),
        (member_vote_fullname_re, from_full),
    )

    reformed_name = first(
        processor(regexp.search(tidied)) for regexp, processor in vote_matches
    )

    if not reformed_name:
        return None
    person_id = get_unique_person_id(reformed_name, str(vote_date))

    if person_id is None and expecting_a_vote:
        print("reformed_name is:", reformed_name)
        print("vote_date is:", vote_date)
        raise Exception("A voting member '%s' couldn't be resolved" % (reformed_name,))
    else:
        return person_id
