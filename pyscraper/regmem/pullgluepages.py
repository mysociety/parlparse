#! /usr/bin/env python3

import glob
import os.path
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime

import miscfuncs
from bs4 import BeautifulSoup

toppath = miscfuncs.toppath

# Pulls in register of members interests, glues them together, removes comments,
# and stores them on the disk

# output directories
pwcmdirs = os.path.join(toppath, "cmpages")
pwcmregmem = os.path.join(pwcmdirs, "regmem")
pwldregmem = os.path.join(pwcmdirs, "ldregmem")

tempfilename = tempfile.mktemp("", "pw-gluetemp-", miscfuncs.tmppath)


class AppURLopener(urllib.request.FancyURLopener):
    version = os.getenv("USER_AGENT")


opener = AppURLopener()


# Scrape everything from the contents page
def GlueByContents(fout, url_contents, regmemdate, remote):
    if remote:
        ur = opener.open(url_contents)
    else:
        ur = open(url_contents)
    sr = ur.read()
    ur.close()

    soup = BeautifulSoup(sr, "lxml")
    mps = soup.find("a", attrs={"name": "A"}).parent.find_next_siblings("p")
    for p in mps:
        url = urllib.parse.urljoin(url_contents, p.a["href"])
        # print(" reading " + url)
        if remote:
            parts = urllib.parse.urlparse(url)
            parts = parts._replace(path=urllib.parse.quote(parts.path))
            ur = opener.open(parts.geturl())
        else:
            url = urllib.parse.quote(url)
            ur = open(url)
        sr = ur.read().decode("utf-8")
        ur.close()

        if remote and ur.code == 404:
            print("failed to fetch %s - skipping" % url)
            continue

        # write the marker telling us which page this comes from
        lt = time.gmtime()
        fout.write(
            '<page url="%s" scrapedate="%s" scrapetime="%s"/>\n'
            % (url, time.strftime("%Y-%m-%d", lt), time.strftime("%X", lt))
        )

        sr = re.sub("<p([^>]*)/>", r"<p\1></p>", sr)
        soup_mp = BeautifulSoup(sr, "lxml")
        try:
            page = soup_mp.find("h1").find_next_siblings(lambda t: t.name != "div")
        except:
            print("Problem with " + url.decode("utf-8"))
        page = "\n".join([str(p) for p in page]) + "\n"
        miscfuncs.WriteCleanText(fout, page)


def GlueByNext(fout, url, regmemdate):
    # loop which scrapes through all the pages following the nextlinks
    starttablewritten = False
    matcheddate = False
    if re.search("ldreg", url):
        matcheddate = True
    sections = 0
    while 1:
        # print " reading " + url
        ur = opener.open(url)
        sr = ur.read().decode("utf-8")
        ur.close()
        sections += 1

        # check date
        if not matcheddate:
            dateinpage = re.search("current as at\s*<[bB]>(.*)</[bB]>", sr)
            if not dateinpage:
                raise Exception("Not found date marker")
            dateinpage = dateinpage.group(1).replace("&nbsp;", " ")
            dateinpage = datetime.strptime(dateinpage, "%d %B %Y").date().isoformat()
            if dateinpage != regmemdate:
                raise Exception(
                    "Date in page is %s, expected %s - update the URL list in regmempullgluepages.py"
                    % (dateinpage, regmemdate)
                )
            matcheddate = True

        # write the marker telling us which page this comes from
        lt = time.gmtime()
        fout.write(
            '<page url="%s" scrapedate="%s" scrapetime="%s"/>\n'
            % (url, time.strftime("%Y-%m-%d", lt), time.strftime("%X", lt))
        )

        # split by sections
        hrsections = re.split(
            '<TABLE border=0 width="90%">|'
            + "</TABLE>\s*?<!-- end of variable data -->|"
            + "<!-- end of variable data -->\s*</TABLE>"
            + "(?i)",
            sr,
        )

        # write the body of the text
        #       for i in range(0,len(hrsections)):
        #           print "------"
        #           print hrsections[i]
        text = hrsections[2]
        m = re.search("<TABLE .*?>([\s\S]*)</TABLE>", text)
        if m:
            text = m.group(1)
        m = re.search("<TABLE .*?>([\s\S]*)", text)
        if m:
            text = m.group(1)
        if not starttablewritten and re.search("COLSPAN=4", text):
            text = "<TABLE>\n" + text
            starttablewritten = True
        miscfuncs.WriteCleanText(fout, text)

        # find the lead on with the footer
        footer = hrsections[3]

        nextsectionlink = re.findall(
            '<A href="([^>]*?)"><IMG border=0\s+align=top src="/pa/img/next(?:grn|drd).gif" ALT="next page"></A>',
            footer,
        )
        if not nextsectionlink:
            break
        if len(nextsectionlink) > 1:
            raise Exception("More than one Next Section!!!")
        url = urllib.parse.urljoin(url, nextsectionlink[0])

    # you evidently didn't find any links
    assert sections > 10

    fout.write("</TABLE>")


# read through our index list of daydebates
def GlueAllType(pcmdir, cmindex, fproto, forcescrape, remote):
    if not os.path.isdir(pcmdir):
        os.mkdir(pcmdir)

    for dnu in cmindex:
        # make the filename
        dgf = os.path.join(pcmdir, (fproto % dnu[0]))

        if forcescrape:
            if os.path.isfile(dgf):
                os.remove(dgf)

        # hansard index page
        url = dnu[1]

        # If already got file, skip
        if os.path.exists(dgf):
            continue

        # now we take out the local pointer and start the gluing
        dtemp = open(tempfilename, "w")
        if dnu[0] > "2010-09-01":
            GlueByContents(dtemp, url, dnu[0], remote)
        else:
            GlueByNext(dtemp, url, dnu[0])

        # close and move
        dtemp.close()
        os.rename(tempfilename, dgf)


# Get index of all regmem pages from the index
def FindRegmemPages(remote):
    if not remote:
        urls = []
        dir = os.path.join(pwcmdirs, "regmem-pages")
        contents = sorted(glob.glob(dir + "/*/contents.htm"))
        for url in contents:
            m = re.search("(\d\d)(\d\d)(\d\d)", url)
            date = "20%s-%s-%s" % m.groups()
            urls.append((date, url))
        return urls

    corrections = {
        "/pa/cm/cmregmem/060214/memi02.htm": "2006-02-13",
        "/pa/cm/cmregmem/051101/memi02.htm": "2005-11-01",
        "/pa/cm/cmregmem/925/part1contents.htm": "2013-01-18",
    }
    urls = []
    idxurl = "https://www.parliament.uk/mps-lords-and-offices/standards-and-financial-interests/parliamentary-commissioner-for-standards/registers-of-interests/register-of-members-financial-interests/"
    ur = opener.open(idxurl)
    content = ur.read()
    if b"Cloudflare" in content:
        sys.exit("Cloudflare please wait page, cannot proceed")
    ur.close()

    soup = BeautifulSoup(content, "lxml")
    soup = soup.find(attrs="main-body").find("ul")
    ixurls = [
        urllib.parse.urljoin(idxurl, ix["href"]) for ix in soup.find_all("a", href=True)
    ]

    for ixurl in ixurls:
        ur = opener.open(ixurl)
        content = ur.read().decode("utf-8")
        ur.close()

        # <B>14&nbsp;May&nbsp;2001&nbsp;(Dissolution)</B>
        content = content.replace("&nbsp;", " ")

        # 2016-03-11 bad HTML, missing '<tr>'
        content = re.sub(
            "<td>\s*</td>\s*<td nowrap><b>Register of Members' Financial Interests - as at 7th March 2016</b></td>",
            "<tr>\g<0>",
            content,
        )
        # And similar 2004-12-03
        content = re.sub(
            '<td>\s*</td>\s*<td><a href="041203/memi02.htm"><b>3 December 2004</b></a></td>',
            "<tr>\g<0>",
            content,
        )

        soup = BeautifulSoup(content, "lxml")

        if soup.find(text=re.compile("^Contents$(?i)")):
            # An immediate register page.
            # Remove comments
            content = re.sub("<!--.*?-->(?s)", "", content)

            alldates = re.findall(
                "(?i)<(?:b|strong)>(\d+[a-z]* [A-Z][a-z]* \d\d\d\d)", content
            )
            if len(alldates) != 1:
                print(alldates)
                raise Exception(
                    "Date match failed, expected one got %d\n%s" % (len(alldates), url)
                )

            date = datetime.strptime(alldates[0], "%d %B %Y").date().isoformat()
            if (date, ixurl) not in urls:
                urls.append((date, ixurl))
        elif re.search("Session 201[79]|Session 20[2-9]", content):
            allurl_soups = soup.find_all(
                "a", href=re.compile("(memi02|part1contents|/contents\.htm)")
            )
            for url_soup in allurl_soups:
                url = url_soup["href"]
                url = urllib.parse.urljoin(ixurl, url)
                date = re.sub("^.*(\d\d)(\d\d)(\d\d).*", r"20\1-\2-\3", url)
                url_path = urllib.parse.urlparse(url)[2]
                if url_path in corrections:
                    date = corrections[url_path]
                if (date, url) not in urls:
                    urls.append((date, url))
        else:
            allurl_soups = soup.find_all(
                "a", href=re.compile("(memi02|part1contents|/contents\.htm)")
            )
            for url_soup in allurl_soups:
                row_content = (
                    url_soup.find_parent("tr").encode_contents().decode("utf-8")
                )
                url = url_soup["href"]
                # print url
                if url == "060324/memi02.htm":
                    # fix broken URL
                    url = "/pa/cm/cmregmem/" + url

                url = urllib.parse.urljoin(ixurl, url)

                alldates = re.findall(
                    "\d+[a-z]*\s+[A-Z][a-z]*\s+\d\d\d\d", row_content, re.DOTALL
                )
                if len(alldates) != 1:
                    print(alldates)
                    raise Exception(
                        "Date match failed, expected one got %d\n%s"
                        % (len(alldates), url)
                    )

                url_path = urllib.parse.urlparse(url)[2]
                if url_path in corrections:
                    date = corrections[url_path]
                else:
                    alldates[0] = re.sub("\s+", " ", alldates[0])
                    alldates[0] = re.sub("(?<=\d)(st|nd|rd|th)", "", alldates[0])
                    date = datetime.strptime(alldates[0], "%d %B %Y").date().isoformat()

                if (date, url) not in urls:
                    urls.append((date, url))

    return urls


###############
# main function
###############
def RegmemPullGluePages(options):
    # make the output directory
    if not os.path.isdir(pwcmdirs):
        os.mkdir(pwcmdirs)

    # When these were hardcoded originally:
    # http://www.publications.parliament.uk/pa/cm/cmhocpap.htm#register
    # urls = [
    #        ('2004-01-31', 'http://www.publications.parliament.uk/pa/cm/cmregmem/memi02.htm'),
    #        ('2003-12-04', 'http://www.publications.parliament.uk/pa/cm200203/cmregmem/memi02.htm')
    #        ]

    urls = FindRegmemPages(options.remote)

    # discard URLs with dates outside of specified range
    urls = [x for x in urls if x[0] >= options.datefrom and x[0] <= options.dateto]

    # bring in and glue together parliamentary register of members interests and put into their own directories.
    # third parameter is a regexp, fourth is the filename (%s becomes the date).
    GlueAllType(pwcmregmem, urls, "regmem%s.html", options.forcescrape, options.remote)


if __name__ == "__main__":
    RegmemPullGluePages(False)
