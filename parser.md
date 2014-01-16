---
layout: page
title: Parser
---

The Parser is a collection of scripts which takes the raw information from Parliament
websites and turns it into the structured XML files.

## Running the Parser

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

### Instructions

Use the command line and change to the pyscraper directory. The script called
`lazyrunall.py` in there does all of the screen scraping from Hansard. Run it
with no parameters to find out its syntax. Then do something like this, include
a date limit as the parser gives errors if you go too far back.

`./lazyrunall.py --from 2001-06-01 scrape parse debates wrans`

That will screen scrape back to the start of the 2001 parliament, writing the
files in `parldata/cmpages`. Then it will parse these files into XML files and
put them in `parldata/scrapedxml`. On Unix the parldata folder is in your home
directory, on Windows it will be in the same folder as the publicwhip folder
which contains the source code.

The command above will gather both debates and written answers (wrans). You can
run a command again and it will lazily make only those files which weren't
downloaded/parsed last time. When you are done, you should have lots of XML
files in the `parldata/scrapedxml/debates` folder.
