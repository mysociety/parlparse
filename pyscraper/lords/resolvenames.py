import json
import os.path
import string
import re
from contextexception import ContextException
import mx.DateTime

from base_resolver import ResolverBase

titleconv = {  'L.':'Lord',
               'B.':'Baroness',
               'Abp.':'Archbishop',
               'Bp.':'Bishop',
               'V.':'Viscount',
               'E.':'Earl',
               'D.':'Duke',
               'M.':'Marquess',
               'C.':'Countess',
               'Ly.':'Lady',
            }

# more tedious stuff to do: "earl of" and "sitting as" cases

hontitles = [ 'Lord  ?Bishop', 'Bishop', 'Marquess', 'Lord', 'Baroness', 'Viscount', 'Earl', 'Countess', 
          'Lord Archbishop', 'Archbishop', 'Duke', 'Lady' ]
hontitleso = string.join(hontitles, '|')

honcompl = re.compile('(?:(%s)|(%s) \s*(.*?))(?:\s+of\s+(.*))?$' % (hontitleso, hontitleso))

rehonorifics = re.compile('(?: [CKO]BE| DL| TD| QC| KCMG| KCB)+$')

class LordsList(ResolverBase):
    import_organization_id = 'house-of-lords'

    def reloadJSON(self):
        super(LordsList, self).reloadJSON()

        self.lordnames={} # "lordnames" --> lords
        self.aliases={} # Corrections to full names

        self.import_people_json()

    def import_people_membership(self, mship, posts, orgs):
        if 'organization_id' not in mship or mship['organization_id'] != self.import_organization_id:
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

    def import_people_main_name(self, name, memberships):
        mships = [m for m in memberships if m['start_date'] <= name.get('end_date', '9999-12-31') and m['end_date'] >= name.get('start_date', '1000-01-01')]
        if not mships: return
        lname = name["lordname"] or name["lordofname"]
        lname = re.sub("\.", "", lname)
        assert lname
        attr = {
            "id": m["id"],
            "title": name["honorific_prefix"],
            "lordname": name.get("lordname", ""),
            "lordofname": name.get("lordofname", ""),
        }
        for m in mships:
            newattr = attr.copy()
            newattr['start_date'] = max(m['start_date'], name.get('start_date', '1000-01-01'))
            newattr['end_date'] = min(m['end_date'], name.get('end_date', '9999-12-31'))
            self.lordnames.setdefault(lname, []).append(newattr)

    def import_people_alternate_name(self, person, other_name, memberships):
        if 'name' not in other_name: return  # Only full names in Lords aliases
        self.aliases[other_name['name']] = person['id']

    # main matching function
    def GetLordID(self, ltitle, llordname, llordofname, loffice, stampurl, sdate, bDivision):
        if ltitle == "Lord Bishop":
            ltitle = "Bishop"
        if ltitle == "Lord Archbishop":
            ltitle = "Archbishop"

        llordofname = string.replace(llordofname, ".", "")
        llordname = string.replace(llordname, ".", "")
        llordname = re.sub('&#(039|146|8217);', "'", llordname)

        llordofname = llordofname.strip()
        llordname = llordname.strip()

        # TODO: Need a Lords version of member-aliases.xml I guess
        if ltitle == "Bishop" and llordofname == "Southwell" and sdate>='2005-07-01':
            llordofname = "Southwell and Nottingham"
        if ltitle == "Bishop" and llordname == "Southwell" and sdate>='2005-07-01':
            llordname = "Southwell and Nottingham"

        lname = llordname or llordofname
        assert lname
        lmatches = self.lordnames.get(lname, [])

        # match to successive levels of precision for identification
        res = [ ]
        for lm in lmatches:
            if lm["title"] != ltitle:  # mismatch title
                continue
            if llordname and llordofname: # two name case
                if (lm["lordname"] == llordname) and (lm["lordofname"] == llordofname):
                    if lm["start_date"] <= sdate <= lm["end_date"]:
                        res.append(lm)
                continue

            # skip onwards if we have a double name
            if lm["lordname"] and lm["lordofname"]:
                continue

            # single name cases (name and of-name)
            # this is the case where they correspond (both names, or both of-names) correctly
            lmlname = lm["lordname"] or lm["lordofname"]
            if (llordname and lm["lordname"]) or (llordofname and lm["lordofname"]):
                if lname == lmlname:
                    if lm["start_date"] <= sdate <= lm["end_date"]:
                        res.append(lm)
                continue

            # cross-match
            if lname == lmlname:
                if lm["start_date"] <= sdate <= lm["end_date"]:
                    if lm["lordname"] and llordofname:
                        #if not IsNotQuiet():
                        print "cm---", ltitle, lm["lordname"], lm["lordofname"], llordname, llordofname
                        raise ContextException("lordofname matches lordname in lordlist", stamp=stampurl, fragment=lname)
                    else:
                        assert lm["lordofname"] and llordname
                        # of-name distinction lost in division lists
                        if not bDivision:
                            raise ContextException("lordname matches lordofname in lordlist", stamp=stampurl, fragment=lname)
                    res.append(lm)
                elif ltitle != "Bishop" and ltitle != "Archbishop" and (ltitle, lname) != ("Duke", "Norfolk"):
                    print lm
                    raise ContextException("wrong dates on lords with same name", stamp=stampurl, fragment=lname)

        if not res:
            raise ContextException("unknown lord %s %s %s %s" % (ltitle, llordname, llordofname, stampurl), stamp=stampurl, fragment=lname)

        assert len(res) == 1
        return self.membertoperson(res[0]["id"])


    def GetLordIDfname(self, name, loffice, sdate, stampurl=None):
        name = re.sub("^The ", "", name)
        name = name.replace(' Of ', ' of ')

        if name in self.aliases:
            return self.aliases[name]

        if name == "Queen":
            return "uk.org.publicwhip/person/13935"

        hom = honcompl.match(name)
        if not hom:
            raise ContextException("lord name format failure on '%s'" % name, stamp=stampurl, fragment=name)

        # now we have a speaker, try and break it up
        ltit = hom.group(1)
        if not ltit:
            ltit = hom.group(2)
            lname = hom.group(3)
        else:
            lname = ""

        ltit = re.sub("  ", " ", ltit)
        lplace = ""
        if hom.group(4):
            lplace = re.sub("  ", " ", hom.group(4))
            lplace = rehonorifics.sub("", lplace)

        lname = re.sub("^De ", "de ", lname)
        lname = rehonorifics.sub("", lname)

        return self.GetLordID(ltit, lname, lplace, loffice, stampurl, sdate, False)


    def MatchRevName(self, fss, sdate, stampurl):
        assert fss
        lfn = re.match('(.*?)(?: of (.*?))?, ? ?((?:L|B|Abp|Bp|V|E|D|M|C|Ly)\.?)$', fss)
        if not lfn:
            print "$$$%s$$$" % fss
            raise ContextException("No match of format in MatchRevName", stamp=stampurl, fragment=fss)
        shorttitle = lfn.group(3)
        if shorttitle[-1] != '.':
            shorttitle += "."
        ltitle = titleconv[shorttitle]
        llordname = string.replace(lfn.group(1), ".", "")
        llordname = string.replace(llordname, "&#039;", "'")
        llordname = re.sub("^De ", "de ", llordname)
        fullname = '%s %s' % (ltitle, llordname)
        llordofname = ""
        if lfn.group(2):
            llordofname = string.replace(lfn.group(2), ".", "")
            fullname = '%s of %s' % (fullname, llordofname)

        if fullname in self.aliases:
            return self.aliases[fullname]

        return self.GetLordID(ltitle, llordname, llordofname, "", stampurl, sdate, True)


# Construct the global singleton of class which people will actually use
lordsList = LordsList()
