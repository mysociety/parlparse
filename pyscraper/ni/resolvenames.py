import re
import datetime
from contextexception import ContextException

from base_resolver import ResolverBase

class MemberList(ResolverBase):
    deputy_speaker = None
    import_organization_id = 'northern-ireland-assembly'

    def reloadJSON(self):
        super(MemberList, self).reloadJSON()

        self.members = {
            "uk.org.publicwhip/member/454" : { 'given_name':'Paul', 'family_name':'Murphy', 'title':'', 'party':'Labour' },
            "uk.org.publicwhip/member/384" : { 'given_name':'John', 'family_name':'McFall', 'title':'', 'party':'Labour' },
        } # ID --> MLAs

        self.debatedate=None
        self.debatenamehistory=[] # recent speakers in debate
        self.debateofficehistory={} # recent offices ("The Deputy Prime Minister")

        self.retitles = re.compile('^(?:Rev |Dr |Mr |Mrs |Ms |Miss |Sir |Lord )+')
        self.rehonorifics = re.compile('(?: OBE| CBE| MP)+$')

        self.import_constituencies()
        self.import_people_json()

    def list(self, date=None, fro=None, to=None):
        if date == 'now':
            date = datetime.date.today().isoformat()
        if date:
            fro = to = date
        if not fro:
            fro = '1000-01-01'
        if not to:
            to = '9999-12-31'
        ids = []
        for m in self.members.values():
            if 'start_date' in m and to >= m["start_date"] and fro <= m["end_date"]:
                ids.append(self.membertoperson(m["id"]))
        return ids

    # useful to have this function out there
    def striptitles(self, text):
        text = text.replace("&rsquo;", "'").replace('\u2019', "'")
        text = text.replace("&nbsp;", " ")
        (text, titletotal) = self.retitles.subn("", text)
        text = self.rehonorifics.sub("", text)
        return text.strip(), titletotal

    # date can be none, will give more matches
    def fullnametoids(self, tinput, date):
        # Special case gender uniques
        if tinput == 'Mrs Bell': tinput = 'Mrs E Bell'

        text, titletotal = self.striptitles(tinput)

        # Special case for non-MLAs
        if text == 'P Murphy': return ["uk.org.publicwhip/member/454"]
        if text == 'McFall': return ["uk.org.publicwhip/member/384"]

        # Find unique identifier for member
        ids = set()
        matches = []
        matches.extend(self.fullnames.get(text, []))
        if not matches and titletotal > 0:
            matches = self.lastnames.get(text, None)

        # If a speaker, then match against the special speaker parties
        if text == "Speaker" or text == "The Speaker":
            matches.extend(self.parties.get("Speaker", []))
        if not matches and text in ('Deputy Speaker', 'Madam Deputy Speaker', 'The Deputy Speaker', 'The Principal Deputy Speaker', 'Madam Principal Deputy Speaker'):
            if not self.deputy_speaker:
                raise ContextException('Deputy speaker speaking, but do not know who it is')
            return self.fullnametoids(self.deputy_speaker, date)

        if matches:
            for m in matches:
                if (date == None) or (date >= m["start_date"] and date <= m["end_date"]):
                    ids.add(m["id"])
        return ids

    def setDeputy(self, deputy):
        if deputy == 'Mr Wilson':
            deputy = 'Mr J Wilson'
        self.deputy_speaker = deputy

    def match_person(self, input, date=None):
        ids = self.fullnametoids(input, date)
        ids = set(map(self.membertoperson, ids))
        if len(ids) == 0:
            raise ContextException("No match %s" % input)
        if len(ids) > 1:
            raise ContextException("Multiple matches %s, possibles are %s" % (input, ids))
        id = ids.pop()
        return id

    def match(self, input, date):
        # Clear name history if date change
        if self.debatedate != date:
            self.debatedate = date
            self.cleardebatehistory()
        speakeroffice = ''
        office = None
        input = re.sub(' \(Designate\)', '', input)
        match = re.match('(.*) \((.*?)\)\s*$', input)
        if match:
            office = match.group(1)
            speakeroffice = ' speakeroffice="%s"' % office
            input = match.group(2)
        ids = self.fullnametoids(input, date)
        if len(ids) == 0 and match:
            office = match.group(2)
            input = match.group(1)
            speakeroffice = ' speakeroffice="%s"' % office
            ids = self.fullnametoids(input, date)

        officeids = self.debateofficehistory.get(input, None)
        if officeids and len(ids) == 0:
            ids = officeids
        if office:
            self.debateofficehistory.setdefault(office, set()).update(ids)

        if len(ids) == 0:
            if not re.search('Some Members|A Member|Several Members|Members', input):
                # import pdb;pdb.set_trace()
                raise ContextException("No matches %s" % (input))
            return None, 'person_id="unknown" error="No match" speakername="%s"' % (input)
        if len(ids) > 1 and 'uk.org.publicwhip/member/90355' in ids:
            # Special case for 8th May, when Mr Hay becomes Speaker
            if input == 'Mr Hay':
                ids.remove('uk.org.publicwhip/member/90355')
            elif input == 'Mr Speaker':
                ids.remove('uk.org.publicwhip/member/90287')
            else:
                raise ContextException('Problem with Mr Hay!')
        elif len(ids) > 1 and 'uk.org.publicwhip/member/90449' in ids:
            # Special case for 2015-01-12, when Mr McLaughlin becomes Speaker
            if input == 'Mr Mitchel McLaughlin':
                ids.remove('uk.org.publicwhip/member/90497')
            elif input == 'Mr Principal Deputy Speaker':
                ids.remove('uk.org.publicwhip/member/90497')
            elif input == 'Mr Speaker':
                ids.remove('uk.org.publicwhip/member/90449')
            else:
                raise ContextException('Problem with Mr McLaughlin! Got "%s"' % input)
        elif len(ids) > 1:
            names = ""
            for id in ids:
                name = self.name_on_date(self.membertoperson(id), date)
                names += '%s %s (%s) ' % (id, name, self.members[id]["constituency"])
            raise ContextException("Multiple matches %s, possibles are %s" % (input, names))
            return None, 'person_id="unknown" error="Matched multiple times" speakername="%s"' % (input)
        for id in ids:
            pass
        person_id = self.membertoperson(id)
        remadename = self.name_on_date(person_id, date)
        if self.members[id]["party"] == "Speaker" and re.search("Speaker", input):
            remadename = input
        return person_id, 'person_id="%s" speakername="%s"%s' % (person_id, remadename, speakeroffice)

    def cleardebatehistory(self):
        self.debatenamehistory = []
        self.debateofficehistory = {}

    def getmember(self, memberid):
        return self.members[memberid]

memberList = MemberList()
