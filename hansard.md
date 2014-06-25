---
layout: page
title: Hansard Reports
---

### Debates (Commons), Debates (Lords), Westminster Hall

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

### Written Answers (Commons), Written Answers (Lords)

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

### Written Ministerial Statements (Commons), Written Ministerial Statements (Lords)

XML files containing statements which ministers made to the houses in writing.
These are a bit like press releases, but in parliamentary language.

## Getting the Data

### By Browsing

You can browse the list of available files and download them individually at:

[http://www.theyworkforyou.com/pwdata/scrapedxml/](http://www.theyworkforyou.com/pwdata/scrapedxml/)

### By git

**Warning: There is a *lot* of data, downloading it all may take a while.**

This is currently not available, we hope to have it back soon.

### By rsync

**Warning: There is a *lot* of data, downloading it all may take a while.**

The easiest way to get hold of all the data currently stored for Hansard is
via rsync to `data.theyworkforyou.com::parldata`. You can see what's available
by running:

`rsync data.theyworkforyou.com::parldata`

You can then use rsync to retrieve content as necessary. Check `man rsync` for
more information on the available options.

We strongly recommend that where possible you use `--exclude '.svn' --exclude
'tmp/'` switches, as these are used for processing and versioning, and aren't
relevant to the data. A command to download the complete dataset is:

`rsync -az --progress --exclude '.svn' --exclude 'tmp/' data.theyworkforyou.com::parldata .`
