#!/usr/bin/python2.4

import xml.sax
import re
import os

from mtimes import get_file_mtime
from mtimes import filenames_modified_after

def find_quotation_from_text(sxp,date,text,minimum_substring_length=20):
    substrings = re.split('\s*[,\.\[\]:]+\s*',text)
    long_enough_substrings = filter( lambda e: len(e) > minimum_substring_length, substrings )
    regular_expressions = map( lambda e: re.compile(re.escape(e)), long_enough_substrings )
    return sxp.find_id_for_quotation( str(date), regular_expressions )

def find_speech_with_trailing_spid(sxp,date,spid):
    return sxp.find_id_for_quotation( str(date), [ re.compile('\(\s*'+spid+'\s*\)\s*$') ] )

class ScrapedXMLParser(xml.sax.handler.ContentHandler):

    def __init__(self,file_template=None):
        self.parser = xml.sax.make_parser()
        self.parser.setContentHandler(self)
        if not file_template:
            self.file_templates = [ "../../../parldata/scrapedxml/sp/sp%s.xml",
                                    "../../../parldata/scrapedxml/sp-written/spwa%s.xml",
                                    "../../../parldata/scrapedxml/debates/debates%s.xml" ]
        elif (file_template.__class__ == str) or (file_template.__class__ == unicode):
            self.file_templates = [ file_template ]
        elif (file_template.__class__ == list):
            self.file_templates = file_template
        else:
            raise Exception, "Unknown type of parameter ("+str(file_template.__class__)+") passed to ScrapedXMLParser"

    def find_all_ids_for_quotation(self,date_string,regexp_list,mtime_after=None):
        # Return an array of pairs, where the first of each pair is
        # the gid and the second is the match object.
        self.regexp_list = regexp_list
        self.ids_with_quote = { }
        self.ids_with_matches = []
        files_to_look_in = map( lambda t: t % date_string, self.file_templates )
        if mtime_after:
            files_to_look_in = filenames_modified_after(files_to_look_in,mtime_after)
        files_that_existed = 0
        for filename in files_to_look_in:
            if os.path.exists(filename):
                files_that_existed += 1
                self.parser.parse(filename)
        if files_that_existed == 0:
            return None
        else:
            return self.ids_with_matches

    def find_id_for_quotation(self,date_string,regexp_list):
        self.regexp_list = regexp_list
        self.ids_with_quote = { }
        self.ids_with_matches = []
        files_to_look_in = map( lambda t: t % date_string, self.file_templates )
        for filename in files_to_look_in:
            if os.path.exists(filename):
                self.parser.parse(filename)
        # Find the ID that most of the regexps match:
        max_occurences = 0
        id_to_return = None
        for k in self.ids_with_quote:
            occurences = self.ids_with_quote[k]
            if occurences > max_occurences:
                id_to_return = k
                max_occurences = occurences
        return id_to_return
            
    def startElement(self,name,attr):
        if name == "ques" or name == "repl" or name == "speech":
            self.element_id = attr["id"]

    def characters(self,c):
        for r in self.regexp_list:
            m = re.search(r,c)
            if m:                
                self.ids_with_quote.setdefault(self.element_id,0)
                self.ids_with_quote[self.element_id] += 1
                self.ids_with_matches.append( (self.element_id,m) )

# sxp = ScrapedXMLParser()
# sxp.find_id_for_quotation( "2004-02-25", [ re.compile("given that justice must be not only swift"),
#                                            re.compile("He also said that justice must") ] )

class WrittenAnswerParser(xml.sax.handler.ContentHandler):

    def __init__(self):
        self.parser = xml.sax.make_parser()
        self.parser.setContentHandler(self)
        self.file_template = "../../../parldata/scrapedxml/sp-written/spwa%s.xml"

    def find_spids_and_holding_dates(self,date_string,verbose,mtime_after):
        self.h = {}
        self.current_date = date_string
        filename = self.file_template % date_string
        if os.path.exists(filename):
            if mtime_after and get_file_mtime(filename) < mtime_after:
                return self.h
            print filename
            self.parser.parse(filename)
            if verbose and len(self.h) == 0:
                print "  Warning: no questions found in "+filename            
        return self.h

    def startElement(self,name,attr):
        if name == "ques":
            spid = attr["spid"]
            gid = attr["id"]
            holding_date_string = None
            if attr.has_key("holdingdate"):
                holding_date_string = attr["holdingdate"]
            self.h.setdefault(spid,[])
            v = (self.current_date,spid,holding_date_string,gid)
            a = self.h[spid]
            if v not in self.h[spid]:
                a.append(v)
