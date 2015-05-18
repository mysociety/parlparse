import json
import os
import re

members_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'members'))

class ResolverBase(object):
    def __init__(self):
        self.reloadJSON()

    def reloadJSON(self):
        self.members = {} # ID --> membership
        self.persons = {} # ID --> person
        self.fullnames = {} # "Firstname Lastname" --> memberships
        self.lastnames = {} # Surname --> memberships

        self.constoidmap = {} # constituency name --> cons attributes (with date and ID)
        self.considtonamemap = {} # cons ID --> name
        self.considtomembermap = {} # cons ID --> memberships
        self.conshansardtoid = {} # Historic Hansard cons ID -> our cons ID
        self.historichansard = {} # Historic Hansard commons membership ID -> MPs

        self.parties = {} # party --> memberships
        self.membertopersonmap = {} # member ID --> person ID
        self.persontomembermap = {} # person ID --> memberships

    def import_constituencies(self, file):
        data = json.load(open(os.path.join(members_dir, file)))
        for con in data:
            if 'hansard_id' in con:
                self.conshansardtoid[con['hansard_id']] = con['id']

            attr = {
                'id': con['id'],
                'start_date': con['start_date'],
                'end_date': con.get('end_date', '9999-12-31'),
            }
            if len(attr['start_date']) == 4:
                attr['start_date'] = '%s-01-01' % attr['start_date']
            if len(attr['end_date']) == 4:
                attr['end_date'] = '%s-12-31' % attr['end_date']

            for name in con['names']:
                if not con['id'] in self.considtonamemap:
                    self.considtonamemap[con['id']] = name
                self.constoidmap.setdefault(name, []).append(attr)
                nopunc = self.strip_punctuation(name)
                self.constoidmap.setdefault(nopunc, []).append(attr)

    def strip_punctuation(self, cons):
        nopunc = cons.replace(',','').replace('-','').replace(' ','').lower().strip()
        return nopunc

    def import_people_json(self):
        data = json.load(open(os.path.join(members_dir, 'people.json')))
        posts = {post['id']: post for post in data['posts']}
        orgs = {org['id']: org for org in data['organizations']}
        for mship in data['memberships']:
            self.import_people_membership(mship, posts, orgs)
        for person in data['persons']:
            self.import_people_names(person)

    def import_people_membership(self, mship, posts, orgs):
        if 'post_id' not in mship or posts[mship['post_id']]['organization_id'] != self.import_organization_id:
            return

        if mship["id"] in self.membertopersonmap:
            raise Exception, "Same member id %s appeared twice" % mship["id"]
        self.membertopersonmap[mship["id"]] = mship['person_id']
        self.persontomembermap.setdefault(mship['person_id'], []).append(mship["id"])

        if self.members.get(mship["id"]):
            raise Exception, "Repeated identifier %s in members JSON file" % mship["id"]
        self.members[mship["id"]] = mship

        if 'end_date' not in mship:
            mship['end_date'] = '9999-12-31'

        # index by constituency
        mship['constituency'] = posts[mship['post_id']]['area']['name']
        consids = self.constoidmap[mship['constituency']]
        consid = None
        # find the constituency id for this person
        mship_start_date = len(mship['start_date'])==4 and ('%s-01-01' % mship['start_date']) or mship['start_date']
        mship_end_date = len(mship['end_date'])==4 and ('%s-12-31' % mship['end_date']) or mship['end_date']
        for cons in consids:
            if (cons['start_date'] <= mship_start_date and
                mship_start_date <= mship_end_date and
                mship_end_date <= cons['end_date']):
                if consid and consid != cons['id']:
                    raise Exception, "Two constituency ids %s %s overlap with MP %s" % (consid, cons['id'], mship['id'])
                consid = cons['id']
        if not consid:
            raise Exception, "Constituency '%s' not found" % mship["constituency"]
        # check name in members file is same as default in cons file
        backformed_cons = self.considtonamemap[consid]
        if backformed_cons != mship["constituency"]:
            raise Exception, "Constituency '%s' in members file differs from first constituency '%s' listed in cons file" % (mship["constituency"], backformed_cons)

        # check first date ranges don't overlap, MPs only
        # Only check modern MPs as we might have overlapping data previously
        if self.import_organization_id == 'house-of-commons':
            for cons in self.considtomembermap.get(consid, []):
                if cons['end_date'] < '1997-05-01': continue
                if cons['start_date'] <= mship['start_date'] <= cons['end_date'] \
                    or cons['start_date'] <= mship['end_date'] <= cons['end_date'] \
                    or mship['start_date'] <= cons['start_date'] <= mship['end_date'] \
                    or mship['start_date'] <= cons['end_date'] <= mship['end_date']:
                    raise Exception, "%s %s Two MP entries for constituency %s with overlapping dates" % (mship, cons, consid)
        # then add in
        self.considtomembermap.setdefault(consid, []).append(mship)

        # ... and by party
        if 'on_behalf_of_id' in mship:
            mship['party'] = orgs[mship['on_behalf_of_id']]['name']
            self.parties.setdefault(mship['party'], []).append(mship)

        if 'hansard_id' in mship:
            self.historichansard.setdefault(int(mship['hansard_id']), []).append(mship)

    def import_people_names(self, person):
        if person['id'] not in self.persontomembermap:
            return
        self.persons[person['id']] = person
        memberships = map(lambda x: self.members[x], self.persontomembermap[person['id']])
        for other_name in person.get('other_names', []):
            if other_name.get('note') == 'Main':
                self.import_people_main_name(other_name, memberships)
            elif other_name.get('note') == 'Alternate':
                self.import_people_alternate_name(person, other_name, memberships)

    def import_people_main_name(self, name, memberships):
        mships = [m for m in memberships if m['start_date'] <= name.get('end_date', '9999-12-31') and m['end_date'] >= name.get('start_date', '1000-01-01')]
        if not mships: return

        try:
            family_name = name["family_name"]
            given_name = name["given_name"]
        except:
            family_name = name['lordname']
            if name['lordofname']:
                family_name += ' of ' + name['lordofname']
            given_name = name['honorific_prefix']
        compoundname = '%s %s' % (given_name, family_name)
        no_initial = ''
        fnnomidinitial = re.findall('^(\S*)\s\S$', given_name)
        if fnnomidinitial:
            no_initial = fnnomidinitial[0] + " " + family_name
        initial_name = ''
        if self.import_organization_id != 'house-of-commons' and given_name:
            initial_name = given_name[0] + " " + family_name

        for m in mships:
            newattr = {'id': m['id'], 'person_id': m['person_id']}
            # merge date ranges - take the smallest range covered by
            # the membership, and the alias's range (if it has one)
            newattr['start_date'] = max(m['start_date'], name.get('start_date', '1000-01-01'))
            newattr['end_date'] = min(m['end_date'], name.get('end_date', '9999-12-31'))
            self.fullnames.setdefault(compoundname, []).append(newattr)
            if no_initial:
                self.fullnames.setdefault(no_initial, []).append(newattr)
            if initial_name:
                self.fullnames.setdefault(initial_name, []).append(newattr)
            self.lastnames.setdefault(family_name, []).append(newattr)

    def import_people_alternate_name(self, person, other_name, memberships):
        if other_name.get('organization_id') not in (None, self.import_organization_id): return
        mships = [m for m in memberships if m['start_date'] <= other_name.get('end_date', '9999-12-31') and m['end_date'] >= other_name.get('start_date', '1000-01-01')]
        for m in mships:
            newattr = {'id': m['id'], 'person_id': m['person_id']}
            # merge date ranges - take the smallest range covered by
            # the membership, and the alias's range (if it has one)
            newattr['start_date'] = max(m['start_date'], other_name.get('start_date', '1000-01-01'))
            newattr['end_date'] = min(m['end_date'], other_name.get('end_date', '9999-12-31'))
            if other_name.get('family_name'):
                self.lastnames.setdefault(other_name['family_name'], []).append(newattr)
            else:
                self.fullnames.setdefault(other_name['name'], []).append(newattr)

    # Used by Commons and NI
    def name_on_date(self, person_id, date):
        person = self.persons[person_id]
        for nm in person['other_names']:
            if nm['note'] != 'Main': continue
            if nm.get('start_date', '0000-00-00') <= date <= nm.get('end_date', '9999-12-31'):
                if 'family_name' in nm:
                    name = nm["family_name"]
                    if nm.get('given_name'):
                        name = nm["given_name"] + " " + name
                    if nm.get('honorific_prefix'):
                        name = nm["honorific_prefix"] + " " + name
                else: # Lord (e.g. Lord Morrow in NI)
                    name = nm['honorific_prefix']
                    if nm['lordname']:
                        name += ' %s' % nm['lordname']
                    if nm['lordofname']:
                        name += ' of %s' % nm['lordofname']
                return name
        raise Exception, 'No found for %s on %s' % (person['id'], date)

    def membertoperson(self, memberid):
        return self.membertopersonmap[memberid]
