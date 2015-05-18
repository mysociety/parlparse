#! /usr/bin/python
# vim:sw=4:ts=4:et:nowrap

# Converts names of MPs into unique identifiers

import json
import re
import string
import copy
import sys
import datetime
import os

from parlphrases import parlPhrases
from contextexception import ContextException
from base_resolver import ResolverBase

# These we don't necessarily match to a speaker id, deliberately
regnospeakers = "Hon\.? Members|Members of the House of Commons|" + \
        "Deputy? ?Speaker|Second Deputy Chairman(?i)|Speaker-Elect|" + \
        "The Chairman|First Deputy Chairman|Temporary Chairman|" + \
        "An hon. Member"

reChairman = "The Chairman|Chairman|The Chair"

# Work out the absolute path of the 'members' directory from
# '__file__', so that we can import this module from any current
# directory:
members_path = os.path.abspath(os.path.join(os.path.split(__file__)[0],'..','members'))


class MemberList(ResolverBase):
    import_organization_id = 'house-of-commons'

    def reloadJSON(self):
        super(MemberList, self).reloadJSON()

        self.debatedate=None
        self.debatenamehistory=[] # recent speakers in debate
        self.debateofficehistory={} # recent offices ("The Deputy Prime Minister")
        # keep track of the chairman in committees
        self.chairman = None

        # "rah" here is a typo in division 64 on 13 Jan 2003 "Ancram, rah Michael"
        self.titles = "Dr |Hon |hon |rah |rh |right hon |Mrs |Ms |Mr |Miss |Mis |Rt Hon |Reverend |The Rev |The Reverend |Sir |Dame |Rev |Prof |Professor |Earl of |Canon "
        self.retitles = re.compile('^(?:%s)' % self.titles)
        self.rejobs = re.compile('^%s$' % parlPhrases.regexpjobs)

        self.honourifics = " MP| CBE| OBE| KBE| DL| MBE| QC| BEM| rh| RH| Esq| QPM| JP| FSA| Bt| B.Ed \(Hons\)| TD";
        self.rehonourifics = re.compile('(?:%s)$' % self.honourifics)

        self.import_constituencies("constituencies.json")
        self.import_people_json()
        self.import_minister_json("ministers.json")
        self.import_minister_json("ministers-2010.json")

    def member_full_name(self, id, date, include_cons=False):
        m = self.members[id]
        name = self.name_on_date(self.membertoperson(id), date)
        if include_cons:
            name += " (%s) " % m['constituency']
        return name

    def import_minister_json(self, file):
        data = json.load(open(os.path.join(members_path, file)))
        for mship in data['memberships']:
            # we load these two positions and alias them into fullnames,
            # as they are often used in wrans instead of fullnames, with
            # no way of telling.
            if mship.get('role') in ("Solicitor General", "Advocate General for Scotland", "Attorney General", "The Solicitor-General", "The Attorney-General"):
                person = mship['person_id']
                if person not in self.persontomembermap: continue  # Not an MP
                # find all the member ids for this person
                ids = self.persontomembermap[person]
                for id in ids:
                    m = self.members[id]
                    # add ones which overlap the membership dates to the alias
                    newattr = {'id': m['id'], 'person_id': m['person_id']}
                    early = max(m['start_date'], mship.get('start_date', '1000-01-01'))
                    late = min(m['end_date'], mship.get('end_date', '9999-12-31'))
                    # sometimes the ranges don't overlap
                    if early <= late:
                        newattr['start_date'] = early
                        newattr['end_date'] = late
                        self.fullnames.setdefault(mship["role"], []).append(newattr)
                        # print mship["role"], early, late, mship['name']

    def partylist(self):
        return self.parties.keys()

    def currentmpslist(self):
        today = datetime.date.today().isoformat()
        return self.mpslistondate(today)

    def mpslistondate(self, date):
        matches = self.members.values()
        ids = []
        for m in matches:
            if date >= m["start_date"] and date <= m["end_date"]:
                ids.append(m["id"])
        return ids

	# useful to have this function out there
    def striptitles(self, text):
        # Remove dots, but leave a space between them
        text = text.replace(".", " ")
        text = text.replace(",", " ")
        text = text.replace("&nbsp;", " ")
        text = text.replace("  ", " ")

        # Remove initial titles (may be several)
        titletotal = 0
        titlegot = 1
        while titlegot > 0:
            (text, titlegot) = self.retitles.subn("", text)
            titletotal = titletotal + titlegot

        # Remove final honourifics (may be several)
        # e.g. for "Mr Menzies Campbell QC CBE" this removes " QC CBE" from the end
        honourtotal = 0
        honourgot = 1
        while honourgot > 0:
            (text, honourgot) = self.rehonourifics.subn("", text)
            honourtotal = honourtotal + honourgot

        return text.strip(), titletotal

    # date can be none, will give more matches
    def fullnametoids(self, tinput, date):
        text, titletotal = self.striptitles(tinput)

        # Find unique identifier for member
        ids = set()
        matches = self.fullnames.get(text, None)
        if not matches and titletotal > 0:
            matches = self.lastnames.get(text, None)

        # If a speaker, then match against the special speaker parties
        if not matches and (text == "Speaker" or text == "The Speaker"):
            matches = self.parties.get("Speaker", None)
        if not matches and (text == "Deputy Speaker" or text == "Deputy-Speaker" or text == "Madam Deputy Speaker"):
            matches = self.parties.get("Deputy Speaker", None)

        if matches:
            for attr in matches:
                if (date == None) or (date >= attr["start_date"] and date <= attr["end_date"]):
                    ids.add(attr["id"])
                # Special case Mr MacDougall questions answered after he died
                if attr["id"]=='uk.org.publicwhip/member/1992' and date >= '2008-09-01' and date <= '2008-09-30':
                    ids.add(attr["id"])
        return ids

    # Returns id, name, corrected constituency
    # Returns id, corrected name, corrected constituency
    # alwaysmatchcons says it is an error to have an unknown/mismatching constituency
    # (rather than just treating cons as None if the cons is unknown)
    # date or cons can be None
    def matchfullnamecons(self, fullname, cons, date, alwaysmatchcons = True):
        origfullname = fullname
        fullname = self.basicsubs(fullname)
        fullname = fullname.strip()
        if cons:
            cons = self.strip_punctuation(cons)
        ids = self.fullnametoids(fullname, date)

        consids = self.constoidmap.get(cons, None)
        if alwaysmatchcons and cons and not consids:
            raise Exception, "Unknown constituency %s" % cons

        if consids and (len(ids) > 1 or alwaysmatchcons):
            newids = set()
            for consattr in consids:
                if date == None or (consattr["start_date"] <= date and date <= consattr["end_date"]):
                    consid = consattr['id']
                    matches = self.considtomembermap[consid]
                    for m in matches:
                        if (date == None) or (date >= m["start_date"] and date <= m["end_date"]):
                            if m["id"] in ids:
                                newids.add(m["id"])
            ids = newids

		# fail cases
        if len(ids) == 0:
            return None, None, None
        if len(ids) > 1:
            # only error for case where cons is present, others case happens too much
            if cons:
                errstring = 'Matched multiple times: %s : %s : %s : %s - perhaps constituency spelling is not known' % (fullname, cons or "[nocons]", date, ids.__str__())
                # actually, even no-cons case happens too often
                # (things like ministerships, with name in brackets after them)
                print errstring
                #raise ContextException(errstring, fragment=origfullname)
            lids = list(ids)  # I really hate the Set type
            lids = map(self.membertoperson, lids)
            lids.sort()
            return None, "MultipleMatch", tuple(lids)

        for lid in ids: # pop is no good as it changes the set
            pass
        remadename = self.member_full_name(lid, date)
        remadecons = self.members[lid]["constituency"]
        return self.membertoperson(lid), remadename, remadecons

    # Exclusively for WMS
    def matchwmsname(self, office, fullname, date):
        if not fullname:
            # They might (rarely) come through without an office name.
            bracket = self.basicsubs(office)
            brackids = self.fullnametoids(office, date)
            if brackids and len(brackids) == 1:
                id = brackids.pop()
                remadename = self.member_full_name(id, date)
                return 'person_id="%s" speakername="%s"' % (self.membertoperson(id), remadename)

        office = self.basicsubs(office)
        speakeroffice = ' speakeroffice="%s"' % office
        fullname = self.basicsubs(fullname)
        ids = self.fullnametoids(fullname, date)

#        rebracket = office
#        rebracket += " (" + fullname + ")"
        if len(ids) == 0:
#            if not re.search(regnospeakers, office):
#               raise Exception, "No matches %s" % (rebracket)
            return 'person_id="unknown" error="No match" speakername="%s"%s' % (fullname, speakeroffice)
        if len(ids) > 1:
            names = ""
            for id in ids:
                names += self.member_full_name(id, date, True)
#            if not re.search(regnospeakers, office):
#                raise Exception, "Multiple matches %s, possibles are %s" % (rebracket, names)
            return 'person_id="unknown" error="Matched multiple times" speakername="%s"%s' % (fullname, speakeroffice)

        for id in ids:
            pass

        remadename = self.member_full_name(id, date)
        return 'person_id="%s" speakername="%s"%s' % (self.membertoperson(id), remadename, speakeroffice)


    # Lowercases a surname, getting cases like these right:
    #     CLIFTON-BROWN to Clifton-Brown
    #     MCAVOY to McAvoy
    def lowercaselastname(self, name):
        words = re.split("( |-|')", name)
        words = [ string.capitalize(word) for word in words ]

        def handlescottish(word):
            if (re.match("Mc[a-z]", word)):
                return word[0:2] + string.upper(word[2]) + word[3:]
            if (re.match("Mac[a-z]", word)):
                return word[0:3] + string.upper(word[3]) + word[4:]
            return word
        words = map(handlescottish, words)

        return string.join(words , "")

    def fixnamecase(self, name):
        return self.lowercaselastname(name)

    # Replace common annoying characters
    def basicsubs(self, txt):
        txt = txt.replace("&#150;", "-")
        txt = txt.replace("&#039;", "'")
        txt = txt.replace("&#39;", "'")
        txt = txt.replace("&#146;", "'")
        txt = txt.replace("&nbsp;", " ")
        txt = txt.replace("&rsquo;", "'")
        txt = txt.replace("&#8217;", "'")
        txt = re.sub("\s{2,10}", " ", txt)  # multiple spaces
        return txt

    # Resets history - exclusively for debates pages
    # The name history stores all recent names:
    #   Mr. Stephen O'Brien (Eddisbury)
    # So it can match them when listed in shortened form:
    #   Mr. O'Brien
    def cleardebatehistory(self):
        # TODO: Perhaps this is a bit loose - how far back in the history should
        # we look?  Perhaps clear history every heading?  Currently it uses the
        # entire day.  Check to find the maximum distance back Hansard needs
        # to rely on.
        self.debatenamehistory = []
        self.debateofficehistory = {}

    # Matches names - exclusively for debates pages
    def matchdebatename(self, input, bracket, date, typ):
        speakeroffice = ""
        input = self.basicsubs(input)

        # Clear name history if date change
        self.date_setup(date)
  
        if input == "The Queen":
            return 'person_id="uk.org.publicwhip/person/13935" speakername="The Queen"'

        # Sometimes no bracketed component: Mr. Prisk
        ids = self.fullnametoids(input, date)
        # Different types of brackets...
        if bracket:
            # Sometimes name in brackets:
            # The Minister for Industry and the Regions (Jacqui Smith)
            bracket = self.basicsubs(bracket)
            brackids = self.fullnametoids(bracket, date)
            if brackids:
                speakeroffice = ' speakeroffice="%s" ' % input

                # If so, intersect those matches with ones from the first part
                # (some offices get matched in first part - like Mr. Speaker)
                if len(ids) == 0 or (len(brackids) == 1 and re.search("speaker(?i)", input)):
                    ids = brackids
                else:
                    ids = ids.intersection(brackids)

            # Sometimes constituency in brackets: Malcolm Bruce (Gordon)
            consids = self.constoidmap.get(bracket, None)
            if consids:
                # Search for constituency matches, and intersect results with them
                newids = set()
                for cons in consids:
                    if cons["start_date"] <= date and date <= cons["end_date"]:
                        consid = cons['id']
                        matches = self.considtomembermap.get(consid, None)
                        if matches:
                            for m in matches:
                                if date >= m["start_date"] and date <= m["end_date"]:
                                    if m["id"] in ids:
                                        newids.add(m["id"])
                ids = newids


        # If ambiguous (either form "Mr. O'Brien" or full name, ambiguous due
        # to missing constituency) look in recent name match history
        if len(ids) > 1:

            # search through history, starting at the end

            # [1:] here we misses the first entry, i.e. it misses the previous
            # speaker.  This is necessary for example here:
            #     http://www.publications.parliament.uk/pa/cm200304/cmhansrd/cm040127/debtext/40127-08.htm#40127-08_spnew13
            # Mr. Clarke refers to Charles Clarke, even though it immediately
            # follows a Mr. Clarke in the form of Kenneth Clarke.  By ignoring
            # the previous speaker, we correctly match the one before.  As the
            # same person never speaks twice in a row, this shouldn't cause
            # trouble.

            ix = len(self.debatenamehistory) - 2
            while ix >= 0:
                x = self.debatenamehistory[ix]
                if x in ids:
                    # first match, use it and exit
                    ids = set([x,])
                    break
                ix -= 1

            # In Westminster Hall, there can be a suspension to go and vote in
            # a divison in the main chamber on something about which they
            # haven't heard the debate, and then the same person keeps talking,
            # so it's possible the same person speaks twice in a row.
            if ix == -1 and typ == 'westminhall' and self.debatenamehistory[-1] in ids:
                ids = set([self.debatenamehistory[-1],])


        # Special case - the AGforS is referred to as just the AG after first appearance
        office = input
        if office == "The Advocate-General":
            office = "The Advocate-General for Scotland"
        # Office name history ("The Deputy Prime Minster (John Prescott)" is later
        # referred to in the same day as just "The Deputy Prime Minister")
        officeids = self.debateofficehistory.get(office, None)
        if officeids:
            if len(ids) == 0:
                ids = officeids

        # Match between office and name - store for later use in the same days text
        if speakeroffice <> "":
            if input in ('The Temporary Chair', 'Madam Deputy Speaker'):
                self.debateofficehistory[input] = set(ids)
            else:
                self.debateofficehistory.setdefault(input, set()).update(ids)

        # Put together original in case we need it
        rebracket = input
        if bracket:
            rebracket += " (" + bracket + ")"

        # Return errors
        if len(ids) == 0:
            if not re.search(regnospeakers, input):
                raise Exception, "No matches %s" % (rebracket)
            self.debatenamehistory.append(None) # see below
            return 'person_id="unknown" error="No match" speakername="%s"' % (rebracket)
        if len(ids) > 1:
            names = ""
            for id in ids:
                names += self.member_full_name(id, date, True)
            if not re.search(regnospeakers, input):
                raise Exception, "Multiple matches %s, possibles are %s" % (rebracket, names)
            self.debatenamehistory.append(None) # see below
            return 'person_id="unknown" error="Matched multiple times" speakername="%s"' % (rebracket)

        # Extract the one id remaining
        for id in ids:
            pass

        # In theory this would be a useful check - in practice it is no good, as in motion
        # text and the like it breaks.  It finds a few errors though.
        # (note that we even store failed matches as None above, so they count
        # as a speaker for the purposes of this check working)
        #if len(self.debatenamehistory) > 0 and self.debatenamehistory[-1] == id and not self.isspeaker(id):
        #    raise Exception, "Same person speaks twice in a row %s" % rebracket

        # Store id in history for this day
        self.debatenamehistory.append(id)

        # Return id and name as XML attributes
        remadename = self.member_full_name(id, date)
        if self.members[id]["party"] == "Speaker" and re.search("Speaker", input):
            remadename = input
        if self.members[id]["party"] == "Deputy Speaker" and re.search("Deputy Speaker", input):
            remadename = input
        return 'person_id="%s" speakername="%s"%s' % (self.membertoperson(id), remadename, speakeroffice)


    def mpnameexists(self, input, date):
        ids = self.fullnametoids(input, date)

        if len(ids) > 0:
            return 1

        if re.match('Mr\. |Mrs\. |Miss |Dr\. ', input):
            print ' potential missing MP name ' + input

        return 0

    def isspeaker(self, id):
        if self.members[id]["party"] == "Speaker":
            return True
        if self.members[id]["party"] == "Deputy Speaker":
            return True
        return False

    def date_setup(self, date):
        """Clears the debate history if a new date is supplied"""
        if self.debatedate != date:
            self.debatedate = date
            self.cleardebatehistory()
            
    def intersect_constituency(self, text, ids, date):
        """Return the intersection of a set of ids with any
        constituency matches for a text fragment
        """
        
        consids = self.constoidmap.get(text, None)
        if consids:
            # Search for constituency matches, and intersect results with them
            newids = set()
            for cons in consids:
                if cons["start_date"] <= date and date <= cons["end_date"]:
                    consid = cons['id']
                    # get any mps
                    matches = self.considtomembermap.get(consid, None)
                        
                    if matches:
                        for m in matches:
                            if date >= m["start_date"] and date <= m["end_date"]:
                                if m["id"] in ids:
                                    newids.add(m["id"])
            ids = newids
        
        return ids    
            
    def disambiguate_from_history(self, ids):
        # search through history, starting at the end

        # [1:] here we miss the first entry, i.e. it misses the previous
        # speaker.  This is necessary for example here:
        #     http://www.publications.parliament.uk/pa/cm200304/cmhansrd/cm040127/debtext/40127-08.htm#40127-08_spnew13
        # Mr. Clarke refers to Charles Clarke, even though it immediately
        # follows a Mr. Clarke in the form of Kenneth Clarke.  By ignoring
        # the previous speaker, we correctly match the one before.  As the
        # same person never speaks twice in a row, this shouldn't cause
        # trouble.
        # this looking back two can sometimes fail if a speaker is interrupted
        # by something procedural, and then picks up his thread straight after himself
        # (eg in westminsterhall if there is a suspension to go vote in a division in the main chamber on something about which they haven't heard the debate)
        
        ix = len(self.debatenamehistory) - 2
        while ix >= 0:
            x = self.debatenamehistory[ix]
            
            if x in ids:
                # first match, use it and exit
                ids = set([x,])
                break
            ix -= 1
        return ids
        
    def set_chairman(self, chairman):
        chairman = self.basicsubs(chairman)
        chairman = self.fixnamecase(chairman)
        chairman = chairman.strip()
        self.chairman = chairman
        
    def get_chairman(self):
        return self.chairman
    
    def matchcttename(self, input, bracket, date):
        """Generates an XML fragment for use in describing a committee member
        in Public Bill Committee Debates. 
        input: A string extracted from a committee member list, expected to be a name
        bracket: A string extracted from a bracket directly following input in the 
            original document
        date: The date of the debate - used to narrow name matches 
        """
        self.date_setup(date)
        input = self.basicsubs(input)
        ids = self.fullnametoids(input, date)
        
        # Bracket should be constituency
        if bracket: ids = self.intersect_constituency(bracket, ids, date)
        
        # If ambiguous (either form "Mr. O'Brien" or full name, ambiguous due
        # to missing constituency) look in recent name match history
        if len(ids) > 1: ids = self.disambiguate_from_history(ids)    

        if len(ids) == 0 and re.search(reChairman, input) and self.chairman:
            ids =  self.fullnametoids(self.chairman, date)
            if len(ids) == 0:
                raise ContextException, "Couldn't match Committee Chairman %s" % self.chairman
            
        if len(ids) == 0:
            if not re.search(regnospeakers, input):
                raise ContextException, "No matches %s" % (input)
            return ' person_id="unknown" error="No match" '
        if len(ids) > 1:
            names = ""
            for id in ids:
                names += id + " " + self.member_full_name(id, date, True)
            raise ContextException, "Multiple matches %s, possibles are %s" % (input, names)
            return ' person_id="unknown" error="Matched multiple times" '

        for id in ids:
            pass
    
        # we can use the committee member names to help resolve ambiguities 
        # in the following debate
        self.debatenamehistory.append(id)
        remadename = self.member_full_name(id, date)
        ret = """ person_id="%s" membername="%s" """ % (self.membertoperson(id), remadename)
        return ret.encode('ascii', 'xmlcharrefreplace')
    
    def matchcttedebatename(self, input, bracket, date, external_speakers=False):
        """Match a name from a Public Bill Committee debate and generate an XML 
        fragment for use in a speech tag
        input - name text to be matched
        bracket - extra text extracted from a bracket following the name
        date - date of document input comes from 
        external_speakers - flag indicating that we are expecting external speakers,
        if true, ContextExceptions are not thrown for no matches"""
        
        speakeroffice = ""
        input = self.basicsubs(input)
        # clear debate history if name change
        self.date_setup(date)
        # Sometimes no bracketed component: Mr. Prisk
        ids = self.fullnametoids(input, date)
        
        # Different types of brackets...
        if bracket:
            # Sometimes name in brackets:
            # The Minister for Industry and the Regions (Jacqui Smith)
            bracket = self.basicsubs(bracket)
            brackids = self.fullnametoids(bracket, date)
            if brackids:
                speakeroffice = ' speakeroffice="%s" ' % input.strip()

                # If so, intersect those matches with ones from the first part
                # (some offices get matched in first part - like Mr. Speaker)
                if len(ids) == 0:
                    ids = brackids
                else:
                    ids = ids.intersection(brackids)

            # Sometimes constituency in brackets: Malcolm Bruce (Gordon)
            ids = self.intersect_constituency(bracket, ids, date)
           
        # If ambiguous (either form "Mr. O'Brien" or full name, ambiguous due
        # to missing constituency) look in recent name match history
        if len(ids) > 1: ids = self.disambiguate_from_history(ids)

        # Office name history ("The Deputy Prime Minster (John Prescott)" is later
        # referred to in the same day as just "The Deputy Prime Minister")
        officeids = self.debateofficehistory.get(input, None)
        if officeids and len(ids) == 0:
             ids = officeids

        # Match between office and name - store for later use in the same days text
        if speakeroffice <> "":
            self.debateofficehistory.setdefault(input, set()).update(ids)

        # Chairman
        if len(ids) == 0 and re.search(reChairman, input) and self.chairman:
            #print "trying %s chair: %s" % (input, self.chairman)
            ids =  self.fullnametoids(self.chairman, date)
            if len(ids) == 0:
                raise ContextException, "Couldn't match Committee Chairman %s" % self.chairman
                
        # Put together original in case we need it
        rebracket = input
        if bracket: rebracket += " (" + bracket + ")"

        # Return errors
        if len(ids) == 0:
            if not re.search(regnospeakers, input) and not external_speakers:
                raise ContextException, "No matches %s" % (rebracket)
            self.debatenamehistory.append(None) # see below
            return 'person_id="unknown" error="No match" speakername="%s"' % (rebracket)
        if len(ids) > 1:
            names = ""
            for id in ids:
                names += self.member_full_name(id, date, True)
            if not re.search(regnospeakers, input):
                raise ContextException, "Multiple matches %s, possibles are %s" % (rebracket, names)
            self.debatenamehistory.append(None) # see below
            return 'person_id="unknown" error="Matched multiple times" speakername="%s"' % (rebracket)

        # Extract the one id remaining
        for id in ids:
            pass

        # Store id in history for this day
        self.debatenamehistory.append(id)
        remadename = self.member_full_name(id, date)
        ret = 'person_id="%s" speakername="%s"%s' % (self.membertoperson(id), remadename, speakeroffice)
        return ret.encode('ascii', 'xmlcharrefreplace')
    
    def canonicalcons(self, cons, date):
        consids = self.constoidmap.get(cons, None)
        if not consids:
            raise Exception, "Unknown constituency %s" % cons
        consid = None
        for consattr in consids:
            if consattr['start_date'] <= date and date <= consattr['end_date']:
                if consid:
                    raise Exception, "Two like-named constituency ids %s %s overlap with date %s" % (consid, consattr['id'], date)
                consid = consattr['id']
        if not consid in self.considtonamemap:
            raise Exception, "Not known name of consid %s cons %s date %s" % (consid, cons, date)
        return self.considtonamemap[consid]

    def getmember(self, memberid):
        return self.members[memberid]

    # Returns the set of members which are the same person in the same
    # parliament / byelection continuously in time.  i.e. We ignore
    # changing party.
    # There must be a simpler way of doing this function, too complex
    def getmembersoneelection(self, memberid):
        personid = self.membertopersonmap[memberid]
        members = self.persontomembermap[personid]

        ids = [memberid, ]
        def scanoneway(whystr, datestr, delta, whystrrev, datestrrev):
            id = memberid
            while 1:
                attr = self.getmember(id)
                if attr[whystr] != "changed_party":
                    break
                dayend = datetime.date(*map(int, attr[datestr].split("-")))
                dayafter = datetime.date.fromordinal(dayend.toordinal() + delta).isoformat()
                for m in members:
                    mattr = self.getmember(m)
                    if mattr[whystrrev] == "changed_party" and mattr[datestrrev] == dayafter:
                        id = mattr["id"]
                        break
                else:
                    raise Exception, "Couldn't find %s %s member party changed from %s date %s" % (whystr, attr[whystr], id, dayafter)

                ids.append(id)

        scanoneway("end_reason", "end_date", +1, "start_reason", "start_date")
        scanoneway("start_reason", "start_date", -1, "end_reason", "end_date")

        return ids
            
    # Historic ID -> ID
    def matchhistoric(self, hansard_id, date):
        ids = []
        for attr in self.historichansard[hansard_id]:
            attr_start_date = len(attr['start_date'])==4 and ('%s-01-01' % attr['start_date']) or attr['start_date']
            attr_end_date = len(attr['end_date'])==4 and ('%s-12-31' % attr['end_date']) or attr['end_date']
            #print hansard_id, attr_start_date, date, attr_end_date
            if attr_start_date <= date and date <= attr_end_date:
                ids.append(attr["id"])

        if len(ids) == 0:
            raise Exception, 'Could not find ID for Historic ID %s, date %s' % (hansard_id, date)
        if len(ids) > 1:
            raise Exception, 'Multiple results for Historic ID %s, date %s: %s' % (hansard_id, date, ','.join(ids))
        return ids[0]

# Construct the global singleton of class which people will actually use
memberList = MemberList()

