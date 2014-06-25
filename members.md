---
layout: page
title: Members of Parliament
---

Structured data about Members of Parliament. These are all XML files, open them
in any text editor, XML viewer or some spreadsheets. In the files there are
comments with more information. Data for MPs is for the 1997, 2001 and 2005
parliaments. Data for Lords goes back to the major reform in 1999.

### all-members.xml / all-members-2010.xml / peers-ucl.xml

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

### people.xml

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

### ministers.xml

Contains ministerial positions and the department they were in.  Each one has a
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

### member-aliases.xml

List of alternative names for MPs. Includes abbreviations, misspellings and name
changes due to marriage. Either canonical names from the `all-members.xml` file
above are given, or the constituency or surname where appropriate.

{% highlight xml %}
<alias fullname="Andrew Bennett" alternate="Andrew F Bennett" />
<alias lastname="MacKay" alternate="Mackay" />
<alias constituency="Worcester" alternate="Michael John Foster" />
<alias fullname="Tony Wright" alternate="Anthony Wright" />
{% endhighlight %}

### constituencies.xml

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

### websites.xml, guardian-links.xml, bbc-links.xml, edm-links.xml, wikipedia-commons.xml, wikipedia-lords.xml

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

### Register of Members Interests (`scrapedxml/regmem`)

MPs declare conflicts of interest, and sources of their income. Separate XML
file for each release of the register.

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

Unlike the other XML on this page, the register XML files are stored with the
[Hansard XML](hansard.html). You can find them by browsing the
[filesystem](http://www.theyworkforyou.com/pwdata/scrapedxml/regmem/). Alternatively, see the section on
[Getting the Data](hansard.html#getting_the_data).

### expenses200304.xml, expenses200203.xml, expenses200102.xml

How much each MP claimed as expenses from parliament for travel and so on.

### Voting Record

Attendance, rebellion rate and individual votes in divisions are available from
the [Public Whip project](http://publicwhip.owl/project/data.php).

<hr>

## Getting the Data

### By Browsing

You can browse the list of available files and download them individually at:

[https://github.com/mysociety/parlparse/tree/master/members](https://github.com/mysociety/parlparse/tree/master/members)

### From GitHub

You can check out a copy of all the latest members XML from GitHub using:

`git clone https://github.com/mysociety/parlparse`

<hr>

## Tools

### rest.cgi

A programmer's interface for matching names. This uses the `all-members.xml`,
`member-aliases.xml` and `constituencies.xml` to match MP names.
