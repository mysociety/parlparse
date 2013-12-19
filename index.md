---
layout: page
title: Overview
---

###### What can I find here?

Structured versions of publicly available data from the UK parliament, and the
source code that was used to generate the data. This is the engine of clever
stuff which runs <a href="http://www.theyworkforyou.com">TheyWorkForYou.com</a>
and <a href="http://www.publicwhip.org.uk">The Public Whip</a>. You might find
the <a href="http://www.theyworkforyou.com/api">TheyWorkForYou API</a> easier to
use.

###### What's all this 'ukparse' stuff?

Parliament Parser is the only part of a potentially larger United Kingdom Parser
project. If you make any other screen scrapers of UK institutions we're happy to
provide hosting.

###### Who do I talk to?

Contact Matthew Somerville at <a
href="mailto:team&#64;theyworkforyou.com">team&#64;theyworkforyou.com</a>, with
any questions. Or join the <a
href="https://secure.mysociety.org/admin/lists/mailman/listinfo/developers-
public ">mySociety public email list</a>, and say hello don't be shy.

<hr>

### Members of Parliament

Structured data about Members of Parliament. These are all XML files, open them
in any text editor, XML viewer or some spreadsheets. In the files there are
comments with more information. Data for MPs is for the 1997, 2001 and 2005
parliaments. Data for Lords goes back to the major reform in 1999.

#### all-members.xml / all-members-2010.xml / peers-ucl.xml

List of all MPs (across two files) and list of all Lords. Includes their name
and party. For MPs, also their constituency, and for Lords, also their peerage
type and their county. There is a unique identifier for each entry. Each entry
is a continuous period of holding office, loyal to the same party. An MP who was
in two parliaments, or in one parliament then later became a Lord, will appear
twice. An MP who also changed party will appear three times. Dates of deaths,
byelections and party changes or whip revocations are recorded.

{% highlight xml %}
<member
    id="uk.org.publicwhip/member/1656"
    house="commons"
    title="" firstname="Emily" lastname="Thornberry"
    constituency="Islington South &amp; Finsbury" party="Lab"
    fromdate="2005-05-05" todate="9999-12-31"
    fromwhy="general_election" towhy="still_in_office"
/>

<lord
    id="uk.org.publicwhip/lord/100633"
    house="lords"
    forenames="Margaret"
    forenames_full="Margaret Hilda"
    title="Baroness" lordname="Thatcher" lordofname=""
    lordofname_full="Kesteven"
    county="the County of Lincolnshire"
    peeragetype="L" affiliation="Con"
    fromdate="1992" todate="9999-12-31"
    ex_MP="yes"
/>
{% endhighlight %}

#### rest.cgi

A programmer's interface for matching names. This uses the `all-members.xml`,
`member-aliases.xml` and `constituencies.xml` to match MP names.

#### people.xml

Links together groups of MPs from all-members.xml and Lords from peers-ucl.xml
who are the same real world person. Usually this is because they have the same
name and are in the same constituency. Sometimes someone changes constituency
between two parliaments, such as Shaun Woodward (Witney) and Shaun Woodward (St
Helens South). This file records that they are the same person. Also includes
offices from `ministers.xml` which were held by that person.

{% highlight xml %}
<person id="uk.org.publicwhip/person/10597" latestname="Paddy Tipping">
    <office id="uk.org.publicwhip/member/1282"/>
    <office id="uk.org.publicwhip/member/1815"/>
    <office id="uk.org.publicwhip/member/597"/>
    <office id="uk.org.publicwhip/moffice/226"/>
</person>
{% endhighlight %}

#### ministers.xml

Contains ministerial  positions and the department they were in.  Each one has a
date range, the MP or Lord became a minister at some time on the start day, and
stopped being one at some time on the end day. The matchid field is one sample
MP or Lord office which that person also held. Alternatively, use the
`people.xml` file to find out which person held the ministerial post.

{% highlight xml %}
<moffice id="uk.org.publicwhip/moffice/327"
    name="Ivor Caplin"
    matchid="uk.org.publicwhip/member/784"
    dept="HM Treasury" position="Assistant Whip"
    fromdate="2001-06-12" todate="2003-06-13"
    source="newlabministers2003-10-15">
</moffice>
{% endhighlight %}

#### member-aliases.xml

List of alternative names for MPs. Includes abbreviations, misspellings and name
changes due to marriage. Either canonical names from the `all-members.xml` file
above are given, or the constituency or surname where appropriate.

{% highlight xml %}
<alias fullname="Andrew Bennett" alternate="Andrew F Bennett" />
<alias lastname="MacKay" alternate="Mackay" />
<alias constituency="Worcester" alternate="Michael John Foster" />
<alias fullname="Tony Wright" alternate="Anthony Wright" />
{% endhighlight %}

#### constituencies.xml

List of Parliamentary constituencies. Includes alternative spellings of each
constituency. When boundaries change, a new identifier is given to the
constituency even if it has the same name. They are also ranged with dates when
they were in effect.

{% highlight xml %}
<constituency id="uk.org.publicwhip/cons/212"
    fromdate="1000-01-01" todate="2005-05-04">
    <name text="Edinburgh, Pentlands"/>
    <name text="Edinburgh Pentlands"/>
</constituency>
{% endhighlight %}

#### websites.xml, guardian-links.xml, bbc-links.xml, edm-links.xml, wikipedia-commons.xml, wikipedia-lords.xml

Various links to external websites which have information about MPs and Lords,
including biographies on Wikipedia, and each MPs own website. Indexed by MP or
Lord identifier.

{% highlight xml %}
<personinfo id="uk.org.publicwhip/person/10197" mp_website="http://www.frankfield.com" />

<personinfo id="uk.org.publicwhip/person/10006"
    guardian_mp_summary="http://politics.guardian.co.uk/person/0,,-35,00.html" />
<consinfo canonical="East Surrey"
    guardian_election_results="http://politics.guardian.co.uk/hoc/constituency/0,,-906,00.html" />
<memberinfo id="uk.org.publicwhip/member/692" swing_to_lose_seat="14.0" />
<memberinfo id="uk.org.publicwhip/member/692" majority_in_seat="13203" />

<memberinfo id="uk.org.publicwhip/member/1224"
    bbc_profile_url="http://news.bbc.co.uk/1/shared/mpdb/html/55.stm" />

<memberinfo id="uk.org.publicwhip/member/687"
    edm_ais_url="http://edm.ais.co.uk/weblink/html/member.html/mem=AbbottSlAsHcOdEsTrInGDiane" />

<memberinfo id="uk.org.publicwhip/lord/100007"
    wikipedia_url="http://en.wikipedia.org/wiki/John_Alderdice%2C_Baron_Alderdice" />
{% endhighlight %}

#### Register of Members Interests (`scrapedxml/regmem`)

MPs declare conflicts of interest, and sources of their income. Separate XML file for each release of the register.

{% highlight xml %}
<regmem personid="uk.org.publicwhip/person/10029"
    memberid="uk.org.publicwhip/member/719" membername="Hugh Bayley"
    date="2005-04-11">
    <category type="4" name="Sponsorship or financial or material support">
        <item>I sponsor a parliamentary pass for a research assistant paid by
        the Royal African Society to enable her to work in support of the
        Africa All-Party Parliamentary Group, which I chair.</item>
    </category>
</regmem>
{% endhighlight %}

#### expenses200304.xml, expenses200203.xml, expenses200102.xml

How much each MP claimed as expenses from parliament for travel and so on.

#### Voting Record

Attendance, rebellion rate and individual votes in divisions are available from
the [Public Whip project](http://publicwhip.owl/project/data.php).

<hr>

### Hansard Reports

#### Debates (Commons), Debates (Lords), Westminster Hall

XML files containing Debates in the main chambers and in Westminster Hall from
the start of the 2001 parliament (Commons) or 1999 reform (Lords). Speeches and
the speaker are labelled with unique identifiers, as are divisions and how each
MP or Lord voted.

{% highlight xml %}
<speech id="uk.org.publicwhip/debate/2003-06-26.1219.2"
    speakerid="uk.org.publicwhip/member/931" speakername="Peter Hain" colnum="1219"
    time="12:32:00"
    url="http://www.publications.parliament.uk/pa/cm200203/
    cmhansrd/vo030626/debtext/30626-10.htm#30626-10_spnew16">
<p>I am a Cabinet Minister and I support the Government's policies. He can ask
me another question along those lines next time, and continue to do so.</p>
</speech>

<major-heading id="uk.org.publicwhip/debate/2003-06-26.1220.0" nospeaker="true"
    colnum="1220" time="12:32:00"
    url="http://www.publications.parliament.uk/pa/cm200203/
    cmhansrd/vo030626/debtext/30626-10.htm#30626-10_head0">
CAP Reform
</major-heading>
{% endhighlight %}

#### Written Answers (Commons), Written Answers (Lords)

XML files containing Written Answers to questions MPs and Lords have asked
ministers. Data from the start of the 2001 parliament (Commons) or 1999 reform
(Lords). Questions and replies are clearly distinguished, and speakers labelled
with their unique identifier.

{% highlight xml %}
<minor-heading id="uk.org.publicwhip/wrans/2005-06-29.7913.h"
    oldstyleid="uk.org.publicwhip/wrans/2005-06-29.1624W.6" nospeaker="True"
    colnum="1624W"  url="http://www.publications.parliament.uk/pa/cm200506/
    cmhansrd/cm050629/text/50629w24.htm#50629w24.html_wqn8">
New Schools
</minor-heading>

<ques id="uk.org.publicwhip/wrans/2005-06-29.7913.q0"
    oldstyleid="uk.org.publicwhip/wrans/2005-06-29.1624W.7"
    speakerid="uk.org.publicwhip/member/1642" speakername="Francis Maude"
    colnum="1624W"  url="http://www.publications.parliament.uk/pa/cm200506/
    cmhansrd/cm050629/text/50629w24.htm#50629w24.html_wqn8">
<p qnum="7913">To ask the Secretary of State for Education and Skills how many
new <i>(a)</i> primary and <i>(b)</i> secondary schools were built in each
English county in each of the last eight years.</p>
</ques>

<reply id="uk.org.publicwhip/wrans/2005-06-29.7913.r0"
    oldstyleid="uk.org.publicwhip/wrans/2005-06-29.1624W.8"
    speakerid="uk.org.publicwhip/member/1776" speakername="Jacqui Smith"
    colnum="1624W"  url="http://www.publications.parliament.uk/pa/cm200506/
    cmhansrd/cm050629/text/50629w24.htm#50629w24.html_spnew8">
<p>The construction of new schools is decided upon by each local authority in
accordance with its asset management plan. Figures on how many new <i>(a)</i>
primary and <i>(b)</i> secondary schools were built in each English county in
each of the last eight years are not held centrally.</p>
</reply>
{% endhighlight %}

#### Written Ministerial Statements (Commons), Written Ministerial Statements (Lords)

XML files containing statements which ministers made to the houses in writing.
These are a bit like press releases, but in parliamentary language.

<hr>

### Getting the Data

**Warning: There is a *lot* of data, downloading it all may take a while.**

The easiest way to get hold of the data is via rsync to
`data.theyworkforyou.com::parldata`. You can see what's available by running:

`rsync data.theyworkforyou.com::parldata`

You can then use rsync to retrieve content as necessary. Check `man rsync` for
more information on the available options.

We strongly recommend that where possible you use `--exclude '.svn' --exclude
'tmp/'` switches, as these are used for processing and versioning, and aren't
relevant to the data. A command to download the complete dataset is:

`rsync -az --progress --exclude '.svn' --exclude 'tmp/' data.theyworkforyou.com::parldata .`

<hr>

### Running the Parser

Python code downloads data from the UK parliament website, stores it as an HTML
file for each day, and parses those files into XML files. To run this parser
yourself, you'll need the following...

* Parser source code - you can get this from SVN:

  `svn co http://project.knowledgeforge.net/ukparse/svn/trunk/parlparse`

  On Windows, use TortoiseSVN and the same URL.

* Python - Under Windows download Python 2.4. Unix-based operating systems
probably have Python already installed, but you may need to upgrade to Python
2.4. You also need the mxDateTime module by eGenix, go to downloads on that
page. Under Debian this is in the package python2.4-egenix-mxdatetime.

* Patch and Diff - The parser has a preprocessor which applies patches to Hansard
to fix uncommon errors. This is done using the tools "patch" and "diff", which
will be installed by default if you are using Unix. On Windows you can download
them from GNU utilities for win32.

#### Instructions

Use the command line and change to the pyscraper directory. The script called
`lazyrunall.py` in there does all of the screen scraping from Hansard. Run it with
no parameters to find out its syntax. Then do something like this, include a
date limit as the parser gives errors if you go too far back.

`./lazyrunall.py --from 2001-06-01 scrape parse debates wrans`

That will screen scrape back to the start of the 2001 parliament, writing the
files in `parldata/cmpages`. Then it will parse these files into XML files and put
them in `parldata/scrapedxml`. On Unix the parldata folder is in your home
directory, on Windows it will be in the same folder as the publicwhip folder
which contains the source code.

The command above will gather both debates and written answers (wrans). You can run a command again and it will lazily make only those files which weren't downloaded/parsed last time. When you are done, you should have lots of XML files in the `parldata/scrapedxml/debates` folder.

What to fix - Ask us for help or ideas if you're extending or improving the parser. Send us patches for even tiny changes you make to get it running on your machine. There's lots of stuff left to do.
