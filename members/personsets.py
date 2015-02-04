#! /usr/bin/env python
# vim:sw=4:ts=4:et:nowrap

# Groups sets of MPs and offices together into person sets.  Updates
# people.xml to reflect the new sets.  Reuses person ids from people.xml,
# or allocates new larger ones.

import xml.sax
import datetime
import sys
import re
import os

sys.path.append("../pyscraper")
from resolvemembernames import memberList

date_today = datetime.date.today().isoformat()

# People who have been both MPs and lords
lordsmpmatches = {
    "uk.org.publicwhip/lord/100851" : "Jenny Tonge [Richmond Park]",
    "uk.org.publicwhip/lord/100855" : "Nigel Jones [Cheltenham]",
    "uk.org.publicwhip/lord/100866" : "Chris Smith [Islington South and Finsbury]",
    "uk.org.publicwhip/lord/100022" : "Paddy Ashdown [Yeovil]",
    "uk.org.publicwhip/lord/100062" : "Betty Boothroyd [West Bromwich West]",
    "uk.org.publicwhip/lord/100082" : "Peter Brooke [Cities of London and Westminster]",
    "uk.org.publicwhip/lord/100104" : "Dale Campbell-Savours [Workington]",
    "uk.org.publicwhip/lord/100128" : "David Clark [South Shields]",
    "uk.org.publicwhip/lord/100144" : "Robin Corbett [Birmingham, Erdington]",
    "uk.org.publicwhip/lord/100208" : "Ronnie Fearn [Southport]",
    "uk.org.publicwhip/lord/100222" : "Norman Fowler [Sutton Coldfield]",
    "uk.org.publicwhip/lord/100244" : "Llin Golding [Newcastle-under-Lyme]",
    "uk.org.publicwhip/lord/100264" : "Bruce Grocott [Telford]",
    "uk.org.publicwhip/lord/100288" : "Michael Heseltine [Henley]",
    "uk.org.publicwhip/lord/100338" : "Barry Jones [Alyn and Deeside]",
    "uk.org.publicwhip/lord/100348" : "Tom King [Bridgwater]",
    "uk.org.publicwhip/lord/100378" : "Richard Livsey [Brecon and Radnorshire]",
    "uk.org.publicwhip/lord/100398" : "John MacGregor [South Norfolk]",
    "uk.org.publicwhip/lord/100407" : "Robert Maclennan [Caithness, Sutherland and Easter Ross]",
    "uk.org.publicwhip/lord/100410" : "Ken Maginnis [Fermanagh and South Tyrone]",
    "uk.org.publicwhip/lord/101150" : "Ken Maginnis [Fermanagh and South Tyrone]",
    "uk.org.publicwhip/lord/100426" : "Ray Michie [Argyll and Bute]",
    "uk.org.publicwhip/lord/100443" : "John Morris [Aberavon]",
    "uk.org.publicwhip/lord/100493" : "Tom Pendry [Stalybridge and Hyde]",
    "uk.org.publicwhip/lord/100518" : "Giles Radice [North Durham]",
    "uk.org.publicwhip/lord/100542" : "George Robertson [Hamilton South]",
    "uk.org.publicwhip/lord/100549" : "Jeff Rooker [Birmingham, Perry Barr]",
    "uk.org.publicwhip/lord/100588" : "Robert Sheldon [Ashton-under-Lyne]",
    "uk.org.publicwhip/lord/100631" : "Peter Temple-Morris [Leominster]",
    "uk.org.publicwhip/lord/100793" : "Peter Snape [West Bromwich East]",
    "uk.org.publicwhip/lord/100799" : "John Maxton [Glasgow Cathcart]",
    "uk.org.publicwhip/lord/100809" : "Ted Rowlands [Merthyr Tydfil and Rhymney]",
    "uk.org.publicwhip/lord/100843" : "Archy Kirkwood [Roxburgh and Berwickshire]",
    "uk.org.publicwhip/lord/100844" : "Ann Taylor [Dewsbury]",
    "uk.org.publicwhip/lord/100845" : "Martin O'Neill [Ochil]",
    "uk.org.publicwhip/lord/100846" : "Paul Tyler [North Cornwall]",
    "uk.org.publicwhip/lord/100847" : "Estelle Morris [Birmingham, Yardley]",
    "uk.org.publicwhip/lord/100848" : "Alan Howarth [Newport East]",
    "uk.org.publicwhip/lord/100849" : "Derek Foster [Bishop Auckland]",
    "uk.org.publicwhip/lord/100850" : "David Chidgey [Eastleigh]",
    "uk.org.publicwhip/lord/100852" : "George Foulkes [Carrick, Cumnock and Doon Valley]",
    "uk.org.publicwhip/lord/100853" : "Archie Hamilton [Epsom and Ewell]",
    "uk.org.publicwhip/lord/100856" : "Gillian Shephard [South West Norfolk]",
    "uk.org.publicwhip/lord/100857" : "Tony Banks [West Ham]",
    "uk.org.publicwhip/lord/100858" : "Nicholas Lyell [North East Bedfordshire]",
    "uk.org.publicwhip/lord/100860" : "Dennis Turner [Wolverhampton South East]",
    "uk.org.publicwhip/lord/100862" : "Virginia Bottomley [South West Surrey]",
    "uk.org.publicwhip/lord/100863" : "Brian Mawhinney [North West Cambridgeshire]",
    "uk.org.publicwhip/lord/100864" : "Lynda Clark [Edinburgh Pentlands]",
    "uk.org.publicwhip/lord/100865" : "Clive Soley [Ealing, Acton and Shepherd's Bush]",
    "uk.org.publicwhip/lord/100867" : "Irene Adams [Paisley North]",
    "uk.org.publicwhip/lord/100869" : "Donald Anderson [Swansea East]",
    "uk.org.publicwhip/lord/100870" : "Jean Corston [Bristol East]",
    "uk.org.publicwhip/lord/100871" : "Alastair Goodlad [Eddisbury]",
    "uk.org.publicwhip/lord/100873" : "Jack Cunningham [Copeland]",
    "uk.org.publicwhip/lord/100910" : "David Trimble [Upper Bann]",
    "uk.org.publicwhip/lord/100967" : "David Trimble [Upper Bann]", # changed party
    "uk.org.publicwhip/lord/100930" : "Keith Bradley [Manchester, Withington]",
    "uk.org.publicwhip/lord/100345" : "John D Taylor [Strangford]",
    "uk.org.publicwhip/lord/100907" : "Brian Cotter [Weston-Super-Mare]",
    "uk.org.publicwhip/lord/100981" : "Peter Mandelson [Hartlepool]",
    "uk.org.publicwhip/lord/100997" : "Michael Martin [Glasgow Springburn / Glasgow North East]",
    "uk.org.publicwhip/lord/100861" : "Lewis Moonie [Kirkcaldy]",
    "uk.org.publicwhip/lord/101015" : "John Gummer [Suffolk Coastal]",
    "uk.org.publicwhip/lord/101017" : "Thomas McAvoy [Glasgow Rutherglen / Rutherglen and Hamilton West]",
    "uk.org.publicwhip/lord/101018" : "Jim Knight [South Dorset]",
    "uk.org.publicwhip/lord/101020" : "John Maples [Stratford-on-Avon]",
    "uk.org.publicwhip/lord/101027" : "Don Touhig [Islwyn]",
    "uk.org.publicwhip/lord/101029" : "John Hutton [Barrow and Furness]",
    "uk.org.publicwhip/lord/101030" : "Paul Boateng [Brent South]",
    "uk.org.publicwhip/lord/101032" : "Ian Paisley [North Antrim]",
    "uk.org.publicwhip/lord/101034" : "John McFall [Dumbarton / West Dunbartonshire]",
    "uk.org.publicwhip/lord/101036" : "Hilary Armstrong [North West Durham]",
    "uk.org.publicwhip/lord/101039" : "Phil Willis [Harrogate and Knaresborough]",
    "uk.org.publicwhip/lord/101040" : "Quentin Davies [Grantham and Stamford]",
    "uk.org.publicwhip/lord/101041" : "Angela Smith [Basildon]",
    "uk.org.publicwhip/lord/101042" : "John Prescott [Kingston upon Hull East]",
    "uk.org.publicwhip/lord/101043" : "Michael Spicer [West Worcestershire]",
    "uk.org.publicwhip/lord/101044" : "Michael Wills [North Swindon]",
    "uk.org.publicwhip/lord/101046" : "Helen Liddell [Airdrie and Shotts]",
    "uk.org.publicwhip/lord/101048" : "Angela Browning [Tiverton and Honiton]",
    "uk.org.publicwhip/lord/101053" : "Tim Boswell [Daventry]",
    "uk.org.publicwhip/lord/101057" : "Michael Howard [Folkestone and Hythe]",
    "uk.org.publicwhip/lord/101060" : "Matthew Taylor [Truro and St Austell]",
    "uk.org.publicwhip/lord/101061" : "John Reid [Hamilton North and Bellshill / Airdrie and Shotts]",
    "uk.org.publicwhip/lord/101063" : "Beverley Hughes [Stretford and Urmston]",
    "uk.org.publicwhip/lord/101065" : "Richard Allan [Sheffield, Hallam]",
    "uk.org.publicwhip/lord/101067" : "Des Browne [Kilmarnock and Loudoun]",
    "uk.org.publicwhip/lord/101074" : "Michael Ancram [Devizes]",
    "uk.org.publicwhip/lord/101080" : "Patrick Cormack [South Staffordshire]",
    "uk.org.publicwhip/lord/101085" : "Susan Kramer [Richmond Park]",
    "uk.org.publicwhip/lord/101090" : "Richard Spring [West Suffolk]",
    "uk.org.publicwhip/lord/101098" : "Howard Flight [Arundel and South Downs]",
    "uk.org.publicwhip/lord/101100" : "Michael Lord [Central Suffolk and North Ipswich]",
    "uk.org.publicwhip/lord/101108" : "Dafydd Wigley [Caernarfon]",
    "uk.org.publicwhip/lord/101118" : "Oona King [Bethnal Green and Bow]",
    "uk.org.publicwhip/lord/101130" : "David Maclean [Penrith and The Border]",
    "uk.org.publicwhip/lord/101169" : "Ian Wrigglesworth [Teesside Thornaby / Stockton South]",
    "uk.org.publicwhip/lord/101175" : "Matthew Carrington [Fulham]",
}

# Put people who change party AND were MPs multple times in table above e.g. David Trimble
lordlordmatches = {
	"uk.org.publicwhip/lord/100931":"uk.org.publicwhip/lord/100160",  # Lord Dahrendorf changes party
	"uk.org.publicwhip/lord/100906":"uk.org.publicwhip/lord/100281",  # Lord Haskins changes party
	"uk.org.publicwhip/lord/100901":"uk.org.publicwhip/lord/100831",  # Bishop of Southwell becomes Bishop of Southwell and Nottingham
	"uk.org.publicwhip/lord/100711":"uk.org.publicwhip/lord/100106",  # Archbishop Carey becomes XB Lord
	"uk.org.publicwhip/lord/100830":"uk.org.publicwhip/lord/100265",  # Bishop of Guildford becomes of Chelmsford
	"uk.org.publicwhip/lord/100872":"uk.org.publicwhip/lord/100736",  # Bishop of Wakefield becomes of Manchester
    "uk.org.publicwhip/lord/100937":"uk.org.publicwhip/lord/100479",  # Bishop of Oxford becomes XB Lord
    "uk.org.publicwhip/lord/100942":"uk.org.publicwhip/lord/100677",  # Lord Wedderburn changes party
    "uk.org.publicwhip/lord/100943":"uk.org.publicwhip/lord/100924",  # As does Lord Boyd...
    "uk.org.publicwhip/lord/100944":"uk.org.publicwhip/lord/100491",  # And Perason
    "uk.org.publicwhip/lord/100945":"uk.org.publicwhip/lord/100690",  # And Willoughby.
    "uk.org.publicwhip/lord/100959":"uk.org.publicwhip/lord/100147",  # And Cox
    "uk.org.publicwhip/lord/100978":"uk.org.publicwhip/lord/100716",  # Viscount Cranborne inherits Marquess of Salisbury
    "uk.org.publicwhip/lord/100993":"uk.org.publicwhip/lord/100957",  # Lord Jones of Brum
    "uk.org.publicwhip/lord/101146":"uk.org.publicwhip/lord/100284",  # Baroness Hayman
    "uk.org.publicwhip/lord/101147":"uk.org.publicwhip/lord/100284",  # "
    "uk.org.publicwhip/lord/101148":"uk.org.publicwhip/lord/100827",  # Baroness D'Souza
    "uk.org.publicwhip/lord/101149":"uk.org.publicwhip/lord/100797",  # Baroness Morgan of Drefelin
    "uk.org.publicwhip/lord/101151":"uk.org.publicwhip/lord/100067",  # Baron Brabazon of Tara
    "uk.org.publicwhip/lord/101152":"uk.org.publicwhip/lord/100581",  # Baron Sewel
    "uk.org.publicwhip/lord/101153":"uk.org.publicwhip/lord/100628",  # Baron Taylor of Warwick
	"uk.org.publicwhip/lord/101156":"uk.org.publicwhip/lord/100105",  # Archbishop of Canterbury getting life peerage
    # XXX: Must be a way to do party changes automatically!
    # XXX: And the key:value ordering here is very suspect
}

ni_mp_matches = {
    "uk.org.publicwhip/member/90123":"Sammy Wilson [East Antrim]",
    "uk.org.publicwhip/member/90074":"William McCrea [South Antrim]",
    "uk.org.publicwhip/member/90198":"William McCrea [South Antrim]",
    "uk.org.publicwhip/member/90111":"John D Taylor [Strangford]",
    "uk.org.publicwhip/member/90186":"John D Taylor [Strangford]",
    "uk.org.publicwhip/member/90040":"Mark Durkan [Foyle]",
    "uk.org.publicwhip/member/90161":"Mark Durkan [Foyle]",
    "uk.org.publicwhip/member/90275":"Mark Durkan [Foyle]",
    "uk.org.publicwhip/member/90455":"Paul Maskey [Belfast West]",
    "uk.org.publicwhip/member/90456":"Francie Molloy [Mid Ulster]",
}
ni_lord_matches = {
    "uk.org.publicwhip/member/90005":"uk.org.publicwhip/lord/100007",
    "uk.org.publicwhip/member/90006":"uk.org.publicwhip/lord/100007",
    "uk.org.publicwhip/member/90242":"uk.org.publicwhip/lord/100007",
    "uk.org.publicwhip/member/90111":"uk.org.publicwhip/lord/100345",
    "uk.org.publicwhip/member/90186":"uk.org.publicwhip/lord/100345",
    "uk.org.publicwhip/member/90091":"uk.org.publicwhip/lord/100922",
    "uk.org.publicwhip/member/90210":"uk.org.publicwhip/lord/100922",
    "uk.org.publicwhip/member/90322":"uk.org.publicwhip/lord/100922",
    "uk.org.publicwhip/member/90457":"uk.org.publicwhip/lord/100922",
    "uk.org.publicwhip/member/90257":"uk.org.publicwhip/lord/100934",
    # William Hay
    "uk.org.publicwhip/member/90416":"uk.org.publicwhip/lord/101235",
    "uk.org.publicwhip/member/90355":"uk.org.publicwhip/lord/101235",
    "uk.org.publicwhip/member/90287":"uk.org.publicwhip/lord/101235",
    "uk.org.publicwhip/member/90178":"uk.org.publicwhip/lord/101235",
    "uk.org.publicwhip/member/90055":"uk.org.publicwhip/lord/101235",
}
# XXX: Should be possible to adapt manualmatches to do this sort of thing...
ni_ni_matches = {
    "Mitchel McLaughlin [Foyle]":"Mitchel McLaughlin [South Antrim]",
    "Alex Maskey [Belfast West]":"Alex Maskey [Belfast South]",
    "Pam Lewis [South Antrim]": "Pam Brown [South Antrim]",
    "Pam Cameron [South Antrim]": "Pam Brown [South Antrim]",
}

sp_lord_matches = {
    # Lord James Douglas-Hamilton
    "uk.org.publicwhip/member/80026": "uk.org.publicwhip/lord/100579",
    "uk.org.publicwhip/member/80261": "uk.org.publicwhip/lord/100579",
    # Sir David Steel
    "uk.org.publicwhip/member/80242": "uk.org.publicwhip/lord/100608",
    "uk.org.publicwhip/member/80277": "uk.org.publicwhip/lord/100608",
    # Lord Jack McConnell
    "uk.org.publicwhip/member/80078": "uk.org.publicwhip/lord/101023",
    "uk.org.publicwhip/member/80201": "uk.org.publicwhip/lord/101023",
    "uk.org.publicwhip/member/80353": "uk.org.publicwhip/lord/101023",
    # Lord Nicol Stephen
    "uk.org.publicwhip/member/80115": "uk.org.publicwhip/lord/101127",
    # Lord Purvis of Tweed
    "uk.org.publicwhip/member/80101": "uk.org.publicwhip/lord/101179",
    "uk.org.publicwhip/member/80378": "uk.org.publicwhip/lord/101179",
    # Baroness Goldie
    "uk.org.publicwhip/member/80040": "uk.org.publicwhip/lord/101197",
    "uk.org.publicwhip/member/80163": "uk.org.publicwhip/lord/101197",
    "uk.org.publicwhip/member/80319": "uk.org.publicwhip/lord/101197",
    "uk.org.publicwhip/member/80537": "uk.org.publicwhip/lord/101197",
}

sp_mp_matches = {
    # Alasdair Morgan
    "uk.org.publicwhip/member/80089": "Alasdair Morgan [Galloway and Upper Nithsdale]",
    "uk.org.publicwhip/member/80213": "Alasdair Morgan [Galloway and Upper Nithsdale]",
    "uk.org.publicwhip/member/80366": "Alasdair Morgan [Galloway and Upper Nithsdale]",
    # Alex Salmond
    "uk.org.publicwhip/member/80233": "Alex Salmond [Banff and Buchan]",
    "uk.org.publicwhip/member/80382": "Alex Salmond [Banff and Buchan]",
    "uk.org.publicwhip/member/80457": "Alex Salmond [Banff and Buchan]",
    # Andrew Welsh
    "uk.org.publicwhip/member/80125": "Andrew Welsh [Angus]",
    "uk.org.publicwhip/member/80255": "Andrew Welsh [Angus]",
    "uk.org.publicwhip/member/80401": "Andrew Welsh [Angus]",
    # Ben Wallace
    "uk.org.publicwhip/member/80251": "Ben Wallace [Lancaster and Wyre / Wyre and Preston North]",
    # David Mundell
    "uk.org.publicwhip/member/80217": "David Mundell [Dumfriesshire, Clydesdale and Tweeddale]",
    "uk.org.publicwhip/member/80265": "David Mundell [Dumfriesshire, Clydesdale and Tweeddale]",
    # Dennis Canavan
    "uk.org.publicwhip/member/80017": "Dennis Canavan [Falkirk West]",
    "uk.org.publicwhip/member/80139": "Dennis Canavan [Falkirk West]",
    # Donald Dewar
    "uk.org.publicwhip/member/80147": "Donald Dewar [Glasgow Anniesland]",
    # Donald Gorrie
    "uk.org.publicwhip/member/80042": "Donald Gorrie [Edinburgh West]",
    "uk.org.publicwhip/member/80164": "Donald Gorrie [Edinburgh West]",
    # Henry McLeish
    "uk.org.publicwhip/member/80205": "Henry McLeish [Central Fife]",
    # Jim Wallace
    "uk.org.publicwhip/member/80123": "Jim Wallace [Orkney and Shetland]",
    "uk.org.publicwhip/member/80252": "Jim Wallace [Orkney and Shetland]",
    # John Home Robertson
    "uk.org.publicwhip/member/80047": "John Home Robertson [East Lothian]",
    "uk.org.publicwhip/member/80172": "John Home Robertson [East Lothian]",
    # John McAllion
    "uk.org.publicwhip/member/80198": "John McAllion [Dundee East]",
    # John Swinney
    "uk.org.publicwhip/member/80120": "John Swinney [North Tayside]",
    "uk.org.publicwhip/member/80247": "John Swinney [North Tayside]",
    "uk.org.publicwhip/member/80397": "John Swinney [North Tayside]",
    "uk.org.publicwhip/member/80451": "John Swinney [North Tayside]",
    # Malcolm Chisholm
    "uk.org.publicwhip/member/80018": "Malcolm Chisholm [Edinburgh North and Leith]",
    "uk.org.publicwhip/member/80140": "Malcolm Chisholm [Edinburgh North and Leith]",
    "uk.org.publicwhip/member/80296": "Malcolm Chisholm [Edinburgh North and Leith]",
    "uk.org.publicwhip/member/80439": "Malcolm Chisholm [Edinburgh North and Leith]",
    # Margaret Ewing
    "uk.org.publicwhip/member/80151": "Margaret Ewing [Moray]",
    "uk.org.publicwhip/member/80263": "Margaret Ewing [Moray]",
    # Roseanna Cunningham
    "uk.org.publicwhip/member/80021": "Roseanna Cunningham [Perth]",
    "uk.org.publicwhip/member/80143": "Roseanna Cunningham [Perth]",
    "uk.org.publicwhip/member/80301": "Roseanna Cunningham [Perth]",
    "uk.org.publicwhip/member/80452": "Roseanna Cunningham [Perth]",
    # Sam Galbraith
    "uk.org.publicwhip/member/80158": "Sam Galbraith [Strathkelvin and Bearsden]",

    # Lord James Douglas-Hamilton
    # Not in the database of MPs, only Lords [Lord James Douglas-Hamilton Edinburgh West]
    # Only an MP until 1997 (?)
    # "uk.org.publicwhip/member/80026" : ""
    # "uk.org.publicwhip/member/80261" : ""

    # Phil Gallie
    # Not in the database (lost seat in 1997)
    # "uk.org.publicwhip/member/80035": "Phil Gallie [Ayr]",
    # "uk.org.publicwhip/member/80159": "Phil Gallie [Ayr]",
    
    # George Reid lost his seat in 1979
    # "uk.org.publicwhip/member/80103": "George Reid [Clackmannan and East Stirlingshire]",
    # "uk.org.publicwhip/member/80228": "George Reid [Clackmannan and East Stirlingshire]",
    # "uk.org.publicwhip/member/80272": "George Reid [Clackmannan and East Stirlingshire]",
    
}

# People who have been MPs for two different constituencies.  The like of
# Michael Portillo will eventually appear here.
manualmatches = {
    "Shaun Woodward [St Helens South]" : "Shaun Woodward [St Helens South / Witney]",
    "Shaun Woodward [Witney]" : "Shaun Woodward [St Helens South / Witney]",

    "George Galloway [Bethnal Green and Bow]" : "George Galloway [Bradford West / Bethnal Green and Bow / Glasgow Kelvin]",
    "George Galloway [Glasgow Kelvin]" : "George Galloway [Bradford West / Bethnal Green and Bow / Glasgow Kelvin]",
    "George Galloway [Bradford West]" : "George Galloway [Bradford West / Bethnal Green and Bow / Glasgow Kelvin]",

    # Returned to maiden name
    "Anne Picking [East Lothian]" : "Anne Moffat [East Lothian]",

    # Scottish boundary changes 2005
    "Menzies Campbell [North East Fife]" : "Menzies Campbell [North East Fife / Fife North East]",
    "Menzies Campbell [Fife North East]" : "Menzies Campbell [North East Fife / Fife North East]",
    "Ann McKechin [Glasgow North]" : "Ann McKechin [Glasgow North / Glasgow Maryhill]",
    "Ann McKechin [Glasgow Maryhill]" : "Ann McKechin [Glasgow North / Glasgow Maryhill]",
    "Frank Doran [Aberdeen Central]" : "Frank Doran [Aberdeen Central / Aberdeen North]",
    "Frank Doran [Aberdeen North]" : "Frank Doran [Aberdeen Central / Aberdeen North]",
    "Tom Harris [Glasgow Cathcart]" : "Tom Harris [Glasgow Cathcart / Glasgow South]",
    "Tom Harris [Glasgow South]" : "Tom Harris [Glasgow Cathcart / Glasgow South]",
    "John McFall [Dumbarton]" : "John McFall [Dumbarton / West Dunbartonshire]",
    "John McFall [West Dunbartonshire]" : "John McFall [Dumbarton / West Dunbartonshire]",
    "Jimmy Hood [Clydesdale]" : "Jimmy Hood [Clydesdale / Lanark and Hamilton East]",
    "Jimmy Hood [Lanark and Hamilton East]" : "Jimmy Hood [Clydesdale / Lanark and Hamilton East]",
    "Ian Davidson [Glasgow Pollok]" : "Ian Davidson [Glasgow Pollok / Glasgow South West]",
    "Ian Davidson [Glasgow South West]" : "Ian Davidson [Glasgow Pollok / Glasgow South West]",
    "Gordon Brown [Kirkcaldy and Cowdenbeath]" : "Gordon Brown [Kirkcaldy and Cowdenbeath / Dunfermline East]",
    "Gordon Brown [Dunfermline East]" : "Gordon Brown [Kirkcaldy and Cowdenbeath / Dunfermline East]",
    "Michael Martin [Glasgow Springburn]" : "Michael Martin [Glasgow Springburn / Glasgow North East]",
    "Michael Martin [Glasgow North East]" : "Michael Martin [Glasgow Springburn / Glasgow North East]",
    "Sandra Osborne [Ayr, Carrick and Cumnock]" : "Sandra Osborne [Ayr, Carrick and Cumnock / Ayr]",
    "Sandra Osborne [Ayr]" : "Sandra Osborne [Ayr, Carrick and Cumnock / Ayr]",
    "Jim Sheridan [West Renfrewshire]" : "Jim Sheridan [West Renfrewshire / Paisley and Renfrewshire North]",
    "Jim Sheridan [Paisley and Renfrewshire North]" : "Jim Sheridan [West Renfrewshire / Paisley and Renfrewshire North]",
    "Robert Smith [Aberdeenshire West and Kincardine]" : "Robert Smith [Aberdeenshire West and Kincardine / West Aberdeenshire and Kincardine]",
    "Robert Smith [West Aberdeenshire and Kincardine]" : "Robert Smith [Aberdeenshire West and Kincardine / West Aberdeenshire and Kincardine]",
    "Charles Kennedy [Ross, Skye and Inverness West]" : "Charles Kennedy [Ross, Skye and Inverness West / Ross, Skye and Lochaber]",
    "Charles Kennedy [Ross, Skye and Lochaber]" : "Charles Kennedy [Ross, Skye and Inverness West / Ross, Skye and Lochaber]",
    "Eric Joyce [Falkirk West]" : "Eric Joyce [Falkirk West / Falkirk]",
    "Eric Joyce [Falkirk]" : "Eric Joyce [Falkirk West / Falkirk]",
    "David Marshall [Glasgow Shettleston]" : "David Marshall [Glasgow Shettleston / Glasgow East]",
    "David Marshall [Glasgow East]" : "David Marshall [Glasgow Shettleston / Glasgow East]",
    "Pete Wishart [North Tayside]" : "Pete Wishart [North Tayside / Perth and North Perthshire]",
    "Pete Wishart [Perth and North Perthshire]" : "Pete Wishart [North Tayside / Perth and North Perthshire]",
    "David Cairns [Greenock and Inverclyde]" : "David Cairns [Greenock and Inverclyde / Inverclyde]",
    "David Cairns [Inverclyde]" : "David Cairns [Greenock and Inverclyde / Inverclyde]",
    "Michael Connarty [Linlithgow and East Falkirk]" : "Michael Connarty [Linlithgow and East Falkirk / Falkirk East]",
    "Michael Connarty [Falkirk East]" : "Michael Connarty [Linlithgow and East Falkirk / Falkirk East]",
    "John Robertson [Glasgow North West]" : "John Robertson [Glasgow North West / Glasgow Anniesland]",
    "John Robertson [Glasgow Anniesland]" : "John Robertson [Glasgow North West / Glasgow Anniesland]",
    "Douglas Alexander [Paisley and Renfrewshire South]" : "Douglas Alexander [Paisley and Renfrewshire South / Paisley South]",
    "Douglas Alexander [Paisley South]" : "Douglas Alexander [Paisley and Renfrewshire South / Paisley South]",
    "Russell Brown [Dumfries and Galloway]" : "Russell Brown [Dumfries and Galloway / Dumfries]",
    "Russell Brown [Dumfries]" : "Russell Brown [Dumfries and Galloway / Dumfries]",
    "Alistair Darling [Edinburgh Central]" : "Alistair Darling [Edinburgh Central / Edinburgh South West]",
    "Alistair Darling [Edinburgh South West]" : "Alistair Darling [Edinburgh Central / Edinburgh South West]",
    "Rosemary McKenna [Cumbernauld, Kilsyth and Kirkintilloch East]" : "Rosemary McKenna [Cumbernauld, Kilsyth and Kirkintilloch East / Cumbernauld and Kilsyth]",
    "Rosemary McKenna [Cumbernauld and Kilsyth]" : "Rosemary McKenna [Cumbernauld, Kilsyth and Kirkintilloch East / Cumbernauld and Kilsyth]",
    "John Reid [Hamilton North and Bellshill]" : "John Reid [Hamilton North and Bellshill / Airdrie and Shotts]",
    "John Reid [Airdrie and Shotts]" : "John Reid [Hamilton North and Bellshill / Airdrie and Shotts]",
    "Adam Ingram [East Kilbride, Strathaven and Lesmahagow]" : "Adam Ingram [East Kilbride, Strathaven and Lesmahagow / East Kilbride]",
    "Adam Ingram [East Kilbride]" : "Adam Ingram [East Kilbride, Strathaven and Lesmahagow / East Kilbride]",
    "Tom Clarke [Coatbridge, Chryston and Bellshill]" : "Tom Clarke [Coatbridge, Chryston and Bellshill / Coatbridge and Chryston]",
    "Tom Clarke [Coatbridge and Chryston]" : "Tom Clarke [Coatbridge, Chryston and Bellshill / Coatbridge and Chryston]",
    "Michael Moore [Tweeddale, Ettrick and Lauderdale]" : "Michael Moore [Tweeddale, Ettrick and Lauderdale / Berwickshire, Roxburgh and Selkirk]",
    "Michael Moore [Berwickshire, Roxburgh and Selkirk]" : "Michael Moore [Tweeddale, Ettrick and Lauderdale / Berwickshire, Roxburgh and Selkirk]",
    "Rachel Squire [Dunfermline and West Fife]" : "Rachel Squire [Dunfermline and West Fife / Dunfermline West]",
    "Rachel Squire [Dunfermline West]" : "Rachel Squire [Dunfermline and West Fife / Dunfermline West]",
    "Christopher Fraser [Mid Dorset and North Poole]" : "Christopher Fraser [Mid Dorset and North Poole / South West Norfolk]",
    "Christopher Fraser [South West Norfolk]" : "Christopher Fraser [Mid Dorset and North Poole / South West Norfolk]",
    "Gavin Strang [Edinburgh East]" : "Gavin Strang [Edinburgh East / Edinburgh East and Musselburgh]",
    "Gavin Strang [Edinburgh East and Musselburgh]" : "Gavin Strang [Edinburgh East / Edinburgh East and Musselburgh]",
    "John MacDougall [Glenrothes]" : "John MacDougall [Glenrothes / Central Fife]",
    "John MacDougall [Central Fife]" : "John MacDougall [Glenrothes / Central Fife]",
    "Thomas McAvoy [Glasgow Rutherglen]" : "Thomas McAvoy [Glasgow Rutherglen / Rutherglen and Hamilton West]",
    "Thomas McAvoy [Rutherglen and Hamilton West]" : "Thomas McAvoy [Glasgow Rutherglen / Rutherglen and Hamilton West]",
    "Brian H Donohoe [Central Ayrshire]" : "Brian H Donohoe [Central Ayrshire / Cunninghame South]",
    "Brian H Donohoe [Cunninghame South]" : "Brian H Donohoe [Central Ayrshire / Cunninghame South]",
    "Mohammad Sarwar [Glasgow Govan]" : "Mohammad Sarwar [Glasgow Govan / Glasgow Central]",
    "Mohammad Sarwar [Glasgow Central]" : "Mohammad Sarwar [Glasgow Govan / Glasgow Central]",

# All possible 2010 general election MPs changing constituency.
# Doesn't matter if they actually win or not, can remove the ones who don't afterwards
    "Hywel Williams [Caernarfon]" : "Hywel Williams [Caernarfon / Arfon]",
    "Hywel Williams [Arfon]" : "Hywel Williams [Caernarfon / Arfon]",
    "John Baron [Billericay]" : "John Baron [Billericay / Basildon and Billericay]",
    "John Baron [Basildon and Billericay]" : "John Baron [Billericay / Basildon and Billericay]",
    "Simon Hughes [North Southwark and Bermondsey]" : "Simon Hughes [North Southwark and Bermondsey / Bermondsey and Old Southwark]",
    "Simon Hughes [Bermondsey and Old Southwark]" : "Simon Hughes [North Southwark and Bermondsey / Bermondsey and Old Southwark]",
    "Roger Godsiff [Birmingham, Sparkbrook and Small Heath]" : "Roger Godsiff [Birmingham, Sparkbrook and Small Heath / Birmingham, Hall Green]",
    "Roger Godsiff [Birmingham, Hall Green]" : "Roger Godsiff [Birmingham, Sparkbrook and Small Heath / Birmingham, Hall Green]",
    "Stephen McCabe [Birmingham, Hall Green]" : "Stephen McCabe [Birmingham, Hall Green / Birmingham, Selly Oak]",
    "Stephen McCabe [Birmingham, Selly Oak]" : "Stephen McCabe [Birmingham, Hall Green / Birmingham, Selly Oak]",
    "Graham Stringer [Manchester, Blackley]" : "Graham Stringer [Manchester, Blackley / Blackley and Broughton]",
    "Graham Stringer [Blackley and Broughton]" : "Graham Stringer [Manchester, Blackley / Blackley and Broughton]",
    "Sarah Teather [Brent East]" : "Sarah Teather [Brent East / Brent Central]",
    "Sarah Teather [Brent Central]" : "Sarah Teather [Brent East / Brent Central]",
    "Ian Liddell-Grainger [Bridgwater]" : "Ian Liddell-Grainger [Bridgwater / Bridgwater and West Somerset]",
    "Ian Liddell-Grainger [Bridgwater and West Somerset]" : "Ian Liddell-Grainger [Bridgwater / Bridgwater and West Somerset]",
    "Keith Simpson [Mid Norfolk]" : "Keith Simpson [Mid Norfolk / Broadland]",
    "Keith Simpson [Broadland]" : "Keith Simpson [Mid Norfolk / Broadland]",
    "Simon Burns [West Chelmsford]" : "Simon Burns [West Chelmsford / Chelmsford]",
    "Simon Burns [Chelmsford]" : "Simon Burns [West Chelmsford / Chelmsford]",
    "Greg Hands [Hammersmith and Fulham]" : "Greg Hands [Hammersmith and Fulham / Chelsea and Fulham]",
    "Greg Hands [Chelsea and Fulham]" : "Greg Hands [Hammersmith and Fulham / Chelsea and Fulham]",
    "Douglas Carswell [Harwich]" : "Douglas Carswell [Harwich / Clacton]",
    "Douglas Carswell [Clacton]" : "Douglas Carswell [Harwich / Clacton]",
    "Jon Cruddas [Dagenham]" : "Jon Cruddas [Dagenham / Dagenham and Rainham]",
    "Jon Cruddas [Dagenham and Rainham]" : "Jon Cruddas [Dagenham / Dagenham and Rainham]",
    "Patrick McLoughlin [West Derbyshire]" : "Patrick McLoughlin [West Derbyshire / Derbyshire Dales]",
    "Patrick McLoughlin [Derbyshire Dales]" : "Patrick McLoughlin [West Derbyshire / Derbyshire Dales]",
    "Elfyn Llwyd [Meirionnydd Nant Conwy]" : "Elfyn Llwyd [Meirionnydd Nant Conwy / Dwyfor Meirionnydd]",
    "Elfyn Llwyd [Dwyfor Meirionnydd]" : "Elfyn Llwyd [Meirionnydd Nant Conwy / Dwyfor Meirionnydd]",
    "Maria Eagle [Liverpool, Garston]" : "Maria Eagle [Liverpool, Garston / Garston and Halewood]",
    "Maria Eagle [Garston and Halewood]" : "Maria Eagle [Liverpool, Garston / Garston and Halewood]",
    "Andy Slaughter [Ealing, Acton and Shepherd's Bush]" : "Andy Slaughter [Ealing, Acton and Shepherd's Bush / Hammersmith]",
    "Andy Slaughter [Hammersmith]" : "Andy Slaughter [Ealing, Acton and Shepherd's Bush / Hammersmith]",
    "Glenda Jackson [Hampstead and Highgate]" : "Glenda Jackson [Hampstead and Highgate / Hampstead and Kilburn]",
    "Glenda Jackson [Hampstead and Kilburn]" : "Glenda Jackson [Hampstead and Highgate / Hampstead and Kilburn]",
    "Bernard Jenkin [North Essex]" : "Bernard Jenkin [North Essex / Harwich and North Essex]",
    "Bernard Jenkin [Harwich and North Essex]" : "Bernard Jenkin [North Essex / Harwich and North Essex]",
    "Bill Wiggin [Leominster]" : "Bill Wiggin [Leominster / North Herefordshire]",
    "Bill Wiggin [North Herefordshire]" : "Bill Wiggin [Leominster / North Herefordshire]",
    "Angela Watkinson [Upminster]" : "Angela Watkinson [Upminster / Hornchurch and Upminster]",
    "Angela Watkinson [Hornchurch and Upminster]" : "Angela Watkinson [Upminster / Hornchurch and Upminster]",
    "Jeremy Wright [Rugby and Kenilworth]" : "Jeremy Wright [Rugby and Kenilworth / Kenilworth and Southam]",
    "Jeremy Wright [Kenilworth and Southam]" : "Jeremy Wright [Rugby and Kenilworth / Kenilworth and Southam]",
    "Malcolm Rifkind [Kensington and Chelsea]" : "Malcolm Rifkind [Kensington and Chelsea / Kensington / Edinburgh Pentlands]",
    "Malcolm Rifkind [Kensington]" : "Malcolm Rifkind [Kensington and Chelsea / Kensington / Edinburgh Pentlands]",
    "Malcolm Rifkind [Edinburgh Pentlands]" : "Malcolm Rifkind [Kensington and Chelsea / Kensington / Edinburgh Pentlands]",
    "George Howarth [Knowsley North and Sefton East]" : "George Howarth [Knowsley North and Sefton East / Knowsley]",
    "George Howarth [Knowsley]" : "George Howarth [Knowsley North and Sefton East / Knowsley]",
    "Andrew Robathan [Blaby]" : "Andrew Robathan [Blaby / South Leicestershire]",
    "Andrew Robathan [South Leicestershire]" : "Andrew Robathan [Blaby / South Leicestershire]",
    "Jim Dowd [Lewisham West]" : "Jim Dowd [Lewisham West / Lewisham West and Penge]",
    "Jim Dowd [Lewisham West and Penge]" : "Jim Dowd [Lewisham West / Lewisham West and Penge]",
    "John Whittingdale [Maldon and East Chelmsford]" : "John Whittingdale [Maldon and East Chelmsford / Maldon]",
    "John Whittingdale [Maldon]" : "John Whittingdale [Maldon and East Chelmsford / Maldon]",
    "Mark Lancaster [North East Milton Keynes]" : "Mark Lancaster [North East Milton Keynes / Milton Keynes North]",
    "Mark Lancaster [Milton Keynes North]" : "Mark Lancaster [North East Milton Keynes / Milton Keynes North]",
    "Edward Balls [Normanton]" : "Edward Balls [Normanton / Morley and Outwood]",
    "Edward Balls [Morley and Outwood]" : "Edward Balls [Normanton / Morley and Outwood]",
    "Nick Brown [Newcastle upon Tyne East and Wallsend]" : "Nick Brown [Newcastle upon Tyne East and Wallsend / Newcastle upon Tyne East]",
    "Nick Brown [Newcastle upon Tyne East]" : "Nick Brown [Newcastle upon Tyne East and Wallsend / Newcastle upon Tyne East]",
    "Yvette Cooper [Pontefract and Castleford]" : "Yvette Cooper [Pontefract and Castleford / Normanton, Pontefract and Castleford]",
    "Yvette Cooper [Normanton, Pontefract and Castleford]" : "Yvette Cooper [Pontefract and Castleford / Normanton, Pontefract and Castleford]",
    "James Brokenshire [Hornchurch]" : "James Brokenshire [Hornchurch / Old Bexley and Sidcup]",
    "James Brokenshire [Old Bexley and Sidcup]" : "James Brokenshire [Hornchurch / Old Bexley and Sidcup]",
    "Angela Smith [Sheffield, Hillsborough]" : "Angela Smith [Sheffield, Hillsborough / Penistone and Stocksbridge]",
    "Angela Smith [Penistone and Stocksbridge]" : "Angela Smith [Sheffield, Hillsborough / Penistone and Stocksbridge]",
    "Alison Seabeck [Plymouth, Devonport]" : "Alison Seabeck [Plymouth, Devonport / Plymouth, Moor View]",
    "Alison Seabeck [Plymouth, Moor View]" : "Alison Seabeck [Plymouth, Devonport / Plymouth, Moor View]",
    "Jim Fitzpatrick [Poplar and Canning Town]" : "Jim Fitzpatrick [Poplar and Canning Town / Poplar and Limehouse]",
    "Jim Fitzpatrick [Poplar and Limehouse]" : "Jim Fitzpatrick [Poplar and Canning Town / Poplar and Limehouse]",
    "Mark Francois [Rayleigh]" : "Mark Francois [Rayleigh / Rayleigh and Wickford]",
    "Mark Francois [Rayleigh and Wickford]" : "Mark Francois [Rayleigh / Rayleigh and Wickford]",
    "Nick Hurd [Ruislip - Northwood]" : "Nick Hurd [Ruislip - Northwood / Ruislip, Northwood and Pinner]",
    "Nick Hurd [Ruislip, Northwood and Pinner]" : "Nick Hurd [Ruislip - Northwood / Ruislip, Northwood and Pinner]",
    "Shaun Woodward [St Helens South]" : "Shaun Woodward [St Helens South / St Helens South and Whiston]",
    "Shaun Woodward [St Helens South and Whiston]" : "Shaun Woodward [St Helens South / St Helens South and Whiston]",
    "Hazel Blears [Salford]" : "Hazel Blears [Salford / Salford and Eccles]",
    "Hazel Blears [Salford and Eccles]" : "Hazel Blears [Salford / Salford and Eccles]",
    "David Blunkett [Sheffield, Brightside]" : "David Blunkett [Sheffield, Brightside / Sheffield, Brightside and Hillsborough]",
    "David Blunkett [Sheffield, Brightside and Hillsborough]" : "David Blunkett [Sheffield, Brightside / Sheffield, Brightside and Hillsborough]",
    "Clive Betts [Sheffield, Attercliffe]" : "Clive Betts [Sheffield, Attercliffe / Sheffield South East]",
    "Clive Betts [Sheffield South East]" : "Clive Betts [Sheffield, Attercliffe / Sheffield South East]",
    "Liam Fox [Woodspring]" : "Liam Fox [Woodspring / North Somerset]",
    "Liam Fox [North Somerset]" : "Liam Fox [Woodspring / North Somerset]",
    "Jeremy Browne [Taunton]" : "Jeremy Browne [Taunton / Taunton Deane]",
    "Jeremy Browne [Taunton Deane]" : "Jeremy Browne [Taunton / Taunton Deane]",
    "Anne McIntosh [Vale of York]" : "Anne McIntosh [Vale of York / Thirsk and Malton]",
    "Anne McIntosh [Thirsk and Malton]" : "Anne McIntosh [Vale of York / Thirsk and Malton]",
    "Steve Webb [Northavon]" : "Steve Webb [Northavon / Thornbury and Yate]",
    "Steve Webb [Thornbury and Yate]" : "Steve Webb [Northavon / Thornbury and Yate]",
    "John Randall [Uxbridge]" : "John Randall [Uxbridge / Uxbridge and South Ruislip]",
    "John Randall [Uxbridge and South Ruislip]" : "John Randall [Uxbridge / Uxbridge and South Ruislip]",
    "Sharon Hodgson [Gateshead East and Washington West]" : "Sharon Hodgson [Gateshead East and Washington West / Washington and Sunderland West]",
    "Sharon Hodgson [Washington and Sunderland West]" : "Sharon Hodgson [Gateshead East and Washington West / Washington and Sunderland West]",
    "John Healey [Wentworth]" : "John Healey [Wentworth / Wentworth and Dearne]",
    "John Healey [Wentworth and Dearne]" : "John Healey [Wentworth / Wentworth and Dearne]",
    "Karen Buck [Regent's Park and Kensington North]" : "Karen Buck [Regent's Park and Kensington North / Westminster North]",
    "Karen Buck [Westminster North]" : "Karen Buck [Regent's Park and Kensington North / Westminster North]",
    "Andrew Murrison [Westbury]" : "Andrew Murrison [Westbury / South West Wiltshire]",
    "Andrew Murrison [South West Wiltshire]" : "Andrew Murrison [Westbury / South West Wiltshire]",
    "Barbara Keeley [Worsley]" : "Barbara Keeley [Worsley / Worsley and Eccles South]",
    "Barbara Keeley [Worsley and Eccles South]" : "Barbara Keeley [Worsley / Worsley and Eccles South]",
    "Ben Wallace [Lancaster and Wyre]" : "Ben Wallace [Lancaster and Wyre / Wyre and Preston North]",
    "Ben Wallace [Wyre and Preston North]" : "Ben Wallace [Lancaster and Wyre / Wyre and Preston North]",
    "Hugh Bayley [City of York]" : "Hugh Bayley [City of York / York Central]",
    "Hugh Bayley [York Central]" : "Hugh Bayley [City of York / York Central]",
    "John Cryer [Hornchurch]" : "John Cryer [Hornchurch / Leyton and Wanstead]",
    "John Cryer [Leyton and Wanstead]" : "John Cryer [Hornchurch / Leyton and Wanstead]",
    "Geoffrey Clifton-Brown [Cotswold]" : "Geoffrey Clifton-Brown [Cotswold / The Cotswolds]",
    "Geoffrey Clifton-Brown [The Cotswolds]" : "Geoffrey Clifton-Brown [Cotswold / The Cotswolds]",
    "Stephen Twigg [Enfield, Southgate]" : "Stephen Twigg [Enfield, Southgate / Liverpool, West Derby]",
    "Stephen Twigg [Liverpool, West Derby]" : "Stephen Twigg [Enfield, Southgate / Liverpool, West Derby]",
    "Geraint Davies [Croydon Central]" : "Geraint Davies [Croydon Central / Swansea West]",
    "Geraint Davies [Swansea West]" : "Geraint Davies [Croydon Central / Swansea West]",
    "Jonathan Evans [Brecon and Radnor]" : "Jonathan Evans [Brecon and Radnor / Cardiff North]",
    "Jonathan Evans [Cardiff North]" : "Jonathan Evans [Brecon and Radnor / Cardiff North]",
    "Christopher Leslie [Shipley]": "Christopher Leslie [Shipley / Nottingham East]",
    "Christopher Leslie [Nottingham East]": "Christopher Leslie [Shipley / Nottingham East]",

    "Ian Wrigglesworth [Teesside Thornaby]" : "Ian Wrigglesworth [Teesside Thornaby / Stockton South]",
    "Ian Wrigglesworth [Stockton South]" : "Ian Wrigglesworth [Teesside Thornaby / Stockton South]",

    }

# Cases we want to specially match - add these in as we need them
class MultipleMatchException(Exception):
    pass

class PersonSets(xml.sax.handler.ContentHandler):

    def __init__(self):
        self.personsets=[] # what we are building - array of (sets of ids belonging to one person)

        self.fullnamescons={} # MPs "Firstname Lastname Constituency" --> person set (link to entry in personsets)
        self.fullnames={} # "Firstname Lastname" --> set of MPs (not link to entry in personsets)
        self.lords={} # Lord ID -> Attr
        self.lordspersonset={} # Lord ID --> person set
        self.member_ni={}
        self.member_ni_personset={}
        self.member_sp={}
        self.member_sp_personset={}
        self.ministermap={}

        self.historichansardtoid = {} # Historic Hansard Person ID -> MPs

        self.old_idtoperson={} # ID (member/lord/office) --> Person ID in last version of file
        self.last_person_id=None # largest person ID previously used
        self.in_person=None

        parser = xml.sax.make_parser()
        parser.setContentHandler(self)
        parser.parse("people.xml")
        parser.parse("all-members.xml")
        parser.parse("all-members-2010.xml")
        parser.parse("peers-ucl.xml")
        parser.parse("ni-members.xml")
        parser.parse("sp-members.xml")
        parser.parse("ministers.xml")
        parser.parse("ministers-2010.xml")
        parser.parse("royals.xml")

    def outputxml(self, fout):
        for personset in self.personsets:
            # OK, we generate a person id based on the mp id.

            # Find what person id we used for this set last time
            personid = None
            for attr in personset:
                # moffice ids are unstable in some cases, so we ignore
                if not re.match("uk.org.publicwhip/moffice/", attr["id"]):
                    if attr["id"] in self.old_idtoperson:
                        newpersonid = self.old_idtoperson[attr["id"]]
                        if personid and newpersonid <> personid:
                                raise Exception, "%s : Two members now same person, were different %s, %s" % (attr["id"], personid, newpersonid)
                        personid = newpersonid
            if not personid:
                self.last_person_id = self.last_person_id + 1
                personid = "uk.org.publicwhip/person/%d" % self.last_person_id

            # Get their final name
            maxdate = "1000-01-01"
            attr = None
            maxname = None
            for attr in personset:
                if attr["fromdate"]=='' or attr["fromdate"] >= maxdate:
                    if attr.has_key("firstname"):
                        # MPs or MLAs
                        maxdate = attr["fromdate"]
                        maxname = "%s %s" % (attr["firstname"], attr["lastname"])
                        if attr['title'] == 'Lord':
                            maxname = 'Lord' + maxname
                    elif attr.has_key("lordname") or attr.has_key("lordofname"):
                        # Lords (this should be in function!)
                        maxdate = attr["fromdate"]
                        maxname = []
                        if not attr["lordname"]:
                            maxname.append("The")
                        maxname.append(attr["title"])
                        if attr["lordname"]:
                            maxname.append(attr["lordname"])
                        if attr["lordofname"]:
                            maxname.append("of")
                            maxname.append(attr["lordofname"])
                        maxname = " ".join(maxname)
            if not maxname:
                raise Exception, "Unknown maxname %s" % attr['id']

            # Output the XML (sorted)
            fout.write('<person id="%s" latestname="%s">\n' % (personid.encode("latin-1"), maxname.encode("latin-1")))
            current = {}
            for attr in personset:
                if attr["fromdate"] <= date_today <= attr["todate"]:
                    current[attr["id"]] = ' current="yes"'
                else:
                    current[attr["id"]] = ''
			ofidl = [ str(attr["id"]) for attr in personset ]
			ofidl.sort()
            for ofid in ofidl:
                fout.write('    <office id="%s"%s/>\n' % (ofid, current[ofid]))
            fout.write('</person>\n')

    #def crosschecks(self):
    #    # check MP date ranges don't overlap
    #    for personset in self.fullnamescons.values():
    #        dateset = map(lambda attr: (attr["fromdate"], attr["todate"]), personset)
    #        dateset.sort(lambda x, y: cmp(x[0], y[0]))
    #        prevtodate = None
    #        for fromdate, todate in dateset:
    #            if len(fromdate) == 4: fromdate = '%s-01-01' % fromdate
    #            if len(todate) == 4: todate = '%s-12-31' % todate
    #            assert fromdate < todate, "date ranges bad %s %s" % (fromdate, todate)
    #            if prevtodate:
    #                assert prevtodate < fromdate, "date ranges overlap %s %s %s" % (prevtodate, fromdate, todate)
    #            prevtodate = todate

    # put ministerialships into each of the sets, based on matching matchid values
    # this works because the members code forms a basis to which ministerialships get attached
    def mergeministers(self):
        for pset in self.personsets:
            for a in pset.copy():
                memberid = a["id"]
                for moff in self.ministermap.get(memberid, []):
                    pset.add(moff)

    # put lords into each of the sets
    def mergelordsandothers(self):
        for lord_id, attr in sorted(self.lords.iteritems()):
            if lord_id in lordsmpmatches:
                mp = lordsmpmatches[lord_id]
                self.fullnamescons[mp].add(attr)
            elif lord_id in lordlordmatches:
                lordidold = lordlordmatches[lord_id]
                self.lordspersonset[lordidold].add(attr)
            else:
                newset = set()
                newset.add(attr)
                self.personsets.append(newset) # master copy of person sets
                self.lordspersonset[lord_id] = newset
 
        items = self.member_ni.items()
        items.sort(key=lambda x : x[1]['lastname'])
        for member_id, attr in items:
            cancons = memberList.canonicalcons(attr['constituency'], attr['fromdate'])
            lookup = "%s %s [%s]" % (attr['firstname'], attr['lastname'], cancons)
            if member_id in ni_mp_matches:
                mp = ni_mp_matches[member_id]
                self.fullnamescons[mp].add(attr)
            elif lookup in ni_ni_matches:
                ni = ni_ni_matches[lookup]
                self.member_ni_personset[ni].add(attr)
            elif member_id in ni_lord_matches:
                lord = ni_lord_matches[member_id]
                self.lordspersonset[lord].add(attr)
            elif lookup in self.fullnamescons and lookup != 'Roy Beggs [East Antrim]' and lookup != 'Mark Durkan [Foyle]':
                self.fullnamescons[lookup].add(attr)
            elif lookup in self.member_ni_personset:
                self.member_ni_personset[lookup].add(attr)
            else:
                newset = set()
                newset.add(attr)
                self.personsets.append(newset)
                self.member_ni_personset[lookup] = newset

        items = self.member_sp.items()
        items.sort(key=lambda x : x[1]['lastname'])
        for member_id, attr in items:

            # Since some Westminster constituencies have the same
            # names as Scottish Parliament constituencies, we may get
            # some clashes unless we mangle the SP name a bit.  I
            # don't think this breaks anything else, but ICBW.
            
            cancons = memberList.canonicalcons("sp: "+attr['constituency'], attr['fromdate'])
            lookup = "%s %s" % (attr['firstname'], attr['lastname'])
            if member_id in sp_mp_matches:
                mp = sp_mp_matches[member_id]
                self.fullnamescons[mp].add(attr)
            elif member_id in sp_lord_matches:
                lord = sp_lord_matches[member_id]
                self.lordspersonset[lord].add(attr)
            elif lookup in self.member_sp_personset:
                self.member_sp_personset[lookup].add(attr)
            else:
                newset = set()
                newset.add(attr)
                self.personsets.append(newset)
                self.member_sp_personset[lookup] = newset

    # Look for people of the same name, but their constituency differs
#    def findotherpeoplewhoaresame(self):
#        goterror = False
#
#        for (name, nameset) in self.fullnames.iteritems():
#            # Find out ids of MPs that we have
#            ids = set(map(lambda attr: attr["id"], nameset))
#
#            # This name matcher includes fuzzier alias matches (e.g. Michael Foster ones)...
#            fuzzierids =  memberList.fullnametoids(name, None)
#
#            # ... so it should be a superset of the ones we have that just match canonical name
#            assert fuzzierids.issuperset(ids), "Not a superset %s %s" % (ids, fuzzierids)
#            fuzzierids = list(fuzzierids)
#
#            # hunt for pairs whose constituencies differ, and don't overlap in time
#            # (as one person can't hold office twice at once)
#            for id1 in range(len(fuzzierids)):
#                attr1 = memberList.getmember(fuzzierids[id1])
#                cancons1 = memberList.canonicalcons(attr1["constituency"], attr1["fromdate"])
#                for id2 in range(id1 + 1, len(fuzzierids)):
#                    attr2 = memberList.getmember(fuzzierids[id2])
#                    cancons2 = memberList.canonicalcons(attr2["constituency"], attr2["fromdate"])
#                    # check constituencies differ
#                    if cancons1 != cancons2:
#
#                        # Check that there is no MP with the same name/constituency
#                        # as one of the two, and who overlaps in date with the other.
#                        # That would mean they can't be the same person, as nobody
#                        # can be MP twice at once (and I think the media would
#                        # notice that!)
#                        match = False
#                        for id3 in range(len(fuzzierids)):
#                            attr3 = memberList.getmember(fuzzierids[id3])
#                            cancons3 = memberList.canonicalcons(attr3["constituency"], attr3["fromdate"])
#
#                            if cancons2 == cancons3 and \
#                                ((attr1["fromdate"] <= attr3["fromdate"] <= attr1["todate"])
#                                or (attr3["fromdate"] <= attr1["fromdate"] <= attr3["todate"])):
#                                #print "matcha %s %s %s (%s) %s to %s" % (attr3["id"], attr3["firstname"], attr3["lastname"], attr3["constituency"], attr3["fromdate"], attr3["todate"])
#                                match = True
#                            if cancons1 == cancons3 and \
#                                ((attr2["fromdate"] <= attr3["fromdate"] <= attr2["todate"])
#                                or (attr3["fromdate"] <= attr2["fromdate"] <= attr3["todate"])):
#                                #print "matchb %s %s %s (%s) %s to %s" % (attr3["id"], attr3["firstname"], attr3["lastname"], attr3["constituency"], attr3["fromdate"], attr3["todate"])
#                                match = True
#
#                        if not match:
#                            # we have a differing cons, but similar name name
#                            # check not in manual match overload
#                            fullnameconskey1 = "%s %s [%s]" % (attr1["firstname"], attr1["lastname"], cancons1)
#                            fullnameconskey2 = "%s %s [%s]" % (attr2["firstname"], attr2["lastname"], cancons2)
#                            if fullnameconskey1 in manualmatches and fullnameconskey2 in manualmatches \
#                                and manualmatches[fullnameconskey1] == manualmatches[fullnameconskey2]:
#                                pass
#                            else:
#                                goterror = True
#                                print "these are possibly the same person: "
#                                print " %s %s %s (%s) %s to %s" % (attr1["id"], attr1["firstname"], attr1["lastname"], attr1["constituency"], attr1["fromdate"], attr1["todate"])
#                                print " %s %s %s (%s) %s to %s" % (attr2["id"], attr2["firstname"], attr2["lastname"], attr2["constituency"], attr2["fromdate"], attr2["todate"])
#                                #  print in this form for handiness "Shaun Woodward [St Helens South]" : "Shaun Woodward [St Helens South / Witney]",
#                                print '"%s %s [%s]" : "%s %s [%s / %s]",' % (attr1["firstname"], attr1["lastname"], attr1["constituency"], attr1["firstname"], attr1["lastname"], attr1["constituency"], attr2["constituency"])
#                                print '"%s %s [%s]" : "%s %s [%s / %s]",' % (attr2["firstname"], attr2["lastname"], attr2["constituency"], attr1["firstname"], attr1["lastname"], attr1["constituency"], attr2["constituency"])
#
#        return goterror

    def startElement(self, name, attr):
        if name == "person":
            assert not self.in_person
            self.in_person = attr["id"]
            numeric_id = int(re.match("uk.org.publicwhip/person/(\d+)$", attr["id"]).group(1))
            if not self.last_person_id or self.last_person_id < numeric_id:
                self.last_person_id = numeric_id
        elif name == "office":
            assert self.in_person
            assert attr["id"] not in self.old_idtoperson
            self.old_idtoperson[attr["id"]] = self.in_person

        elif name == "member":
            assert not self.in_person

            if 'hansard_cons_id' in attr:
                cancons = memberList.conshansardtoid[attr['hansard_cons_id']]
                cancons = memberList.considtonamemap[cancons]
            else:
                cancons = memberList.canonicalcons(attr["constituency"], attr["fromdate"])
                cancons2 = memberList.canonicalcons(attr["constituency"], attr["todate"])
                assert cancons == cancons2

            # index by "Firstname Lastname Constituency"
            fullnameconskey = "%s %s [%s]" % (attr["firstname"], attr["lastname"], cancons)
            if fullnameconskey in manualmatches:
                fullnameconskey = manualmatches[fullnameconskey]

            if 'hansard_person_id' in attr:
                hansard_person_id = attr['hansard_person_id']
                if hansard_person_id not in self.historichansardtoid:
                    newset = set()
                    self.personsets.append(newset)
                    self.historichansardtoid[hansard_person_id] = newset
                self.historichansardtoid[hansard_person_id].add(attr.copy())
                if fullnameconskey not in self.fullnamescons:
                    self.fullnamescons[fullnameconskey] = self.historichansardtoid[hansard_person_id]
            else:
                if fullnameconskey not in self.fullnamescons:
                    newset = set()
                    self.personsets.append(newset) # master copy of person sets
                    self.fullnamescons[fullnameconskey] = newset # store link here
			    # MAKE A COPY.  (The xml documentation warns that the attr object can be reused, so shouldn't be put into your structures if it's not a copy).
                self.fullnamescons[fullnameconskey].add(attr.copy())

            fullnamekey = "%s %s" % (attr["firstname"], attr["lastname"])
            self.fullnames.setdefault(fullnamekey, set()).add(attr.copy())

        elif name == "lord":
            assert attr['id'] not in self.lords
            self.lords[attr['id']] = attr.copy()

        elif name == "royal":
            newset = set()
            newset.add(attr)
            self.personsets.append(newset)

		elif name == "moffice":
            assert not self.in_person

			#assert attr["id"] not in self.ministermap
			if attr.has_key("matchid"):
				self.ministermap.setdefault(attr["matchid"], set()).add(attr.copy())

        elif name == "member_ni":
            assert not self.in_person
            assert attr['id'] not in self.member_ni
            self.member_ni[attr['id']] = attr.copy()

        elif name == "member_sp":
            assert not self.in_person
            assert attr['id'] not in self.member_sp
            self.member_sp[attr['id']] = attr.copy()

    def endElement(self, name):
        if name == "person":
            self.in_person = None
        pass

# the main code
personSets = PersonSets()
#personSets.crosschecks()
#if personSets.findotherpeoplewhoaresame():
#    print
#    print "If they are, correct it with the manualmatches array"
#    print "Or add another array to show people who appear to be but are not"
#    print
#    sys.exit(1)
personSets.mergelordsandothers()
personSets.mergeministers()

tempfile = "temppeople.xml"
fout = open(tempfile, "w")
fout.write("""<?xml version="1.0" encoding="ISO-8859-1"?>

<!--

Contains a unique identifier for each person, and a list of ids
of offices which they have held.

Generated exclusively by personsets.py, don't hand edit it just now
(it would be such a pain to manually match up all these ids)

-->

<publicwhip>""")

personSets.outputxml(fout)
fout.write("</publicwhip>\n")
fout.close()

# overwrite people.xml
os.rename("temppeople.xml", "people.xml")


