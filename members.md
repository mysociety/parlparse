---
layout: page
title: Members of Parliament
---

Structured data about Members of Parliament. These are JSON or XML files, so
you can open them in a text editor or similar. In the files there are comments
with more information. MP data goes back to the start of Hansard at the start
of the 19th century (including data from Parliament's historic Hansard
project), data for Lords goes back to the major reform in 1999, and data for
the devolved assemblies goes back to their creation.

These files can all be found in the
[GitHub repository members directory](https://github.com/mysociety/parlparse/tree/master/members).

## people.json

Data of all MPs, Lords, MSPs and MLAs covered by the project, in [Popolo
format](http://www.popoloproject.com), including names (and alternate names
such as misspellings or name changes), party, constituency (non-Lords), and
peerage information (Lords). There is a unique identifier for each element.
Each membership is a continuous period of holding office, loyal to the same
party. An MP who was in two parliaments, or in one parliament then later became
a Lord, will have two memberships associated with the same person. An MP who
also changed party will have three memberships. Dates of deaths, byelections
and party changes are recorded.

{% highlight json %}
{
  "id": "uk.org.publicwhip/member/1656",
  "name": {
    "family_name": "Thornberry",
    "given_name": "Emily"
  },
  "on_behalf_of_id": "labour",
  "person_id": "uk.org.publicwhip/person/11656",
  "post_id": "uk.org.publicwhip/cons/310",
  "start_date": "2005-05-05",
  "start_reason": "general_election"
  "end_date": "2010-04-12",
  "end_reason": "general_election_standing",
},

{
  "id": "uk.org.publicwhip/lord/100633",
  "identifiers": [
    {
      "identifier": "L",
      "scheme": "peeragetype"
    }
  ],
  "label": "Peer",
  "name": {
    "additional_name": "Margaret Hilda",
    "county": "the County of Lincolnshire",
    "given_name": "Margaret",
    "honorific_prefix": "Baroness",
    "lordname": "Thatcher",
    "lordofname": "",
    "lordofname_full": "Kesteven"
  },
  "on_behalf_of_id": "conservative",
  "organization_id": "house-of-lords",
  "person_id": "uk.org.publicwhip/person/12975",
  "role": "Peer",
  "start_date": "1992"
  "end_date": "2013-04-08",
  "end_reason": "died",
},
{% endhighlight %}

### ministers.json / ministers-2010.json

Contains ministerial positions and the department they were in. Each one
includes an ID, date range, and the person ID.

{% highlight json %}
{
  "id": "uk.parliament.data/Member/591/GovernmentPost/661",
  "source": "datadotparl/governmentpost",
  "role": "The Prime Minister",
  "person_id": "uk.org.publicwhip/person/10068",
  "organization_id": "house-of-commons",
  "start_date": "2007-06-28",
  "end_date": "2010-05-06"
},
{% endhighlight %}

### constituencies.json / sp-constituencies.json

List of constituencies, including alternative spellings.

{% highlight json %}
{
  "hansard_id": "232",
  "id": "uk.org.publicwhip/cons/212",
  "start_date": "1950",
  "end_date": "2005-05-04",
  "names": [
    "Edinburgh Pentlands",
    "Edinburgh, Pentlands"
  ]
},
{% endhighlight %}

### websites.xml, bbc-links.xml, wikipedia-*.xml, wikipedia-lords.xml

Various links to external websites which have information about MPs and Lords,
including biographies on Wikipedia, and each MP's own website. Indexed by
person ID.

{% highlight xml %}
<personinfo id="uk.org.publicwhip/person/10197" mp_website="http://www.frankfield.com" />

<personinfo id="uk.org.publicwhip/person/10777"
    bbc_profile_url="http://news.bbc.co.uk/democracylive/hi/representatives/profiles/25752.stm" />

<personinfo id="uk.org.publicwhip/person/10001"
    wikipedia_url="http://en.wikipedia.org/wiki/Diane_Abbott" />
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

### expenses*.xml

How much each MP claimed as expenses from parliament for travel and so on.

### Voting Record

Attendance, rebellion rate and individual votes in divisions are available from
the [Public Whip project](http://www.publicwhip.org.uk/project/data.php).

<hr>

## Getting the Data

### By Browsing

You can browse the list of available files and download them individually at:

[https://github.com/mysociety/parlparse/tree/master/members](https://github.com/mysociety/parlparse/tree/master/members)

### From GitHub

You can check out a copy of all the latest members data from GitHub using:

`git clone https://github.com/mysociety/parlparse`
