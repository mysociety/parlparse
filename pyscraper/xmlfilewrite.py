#! /usr/bin/python
# vim:sw=8:ts=8:nowrap

def WriteXMLHeader(fout, encoding="ISO-8859-1", output_unicode=False):
	header = '<?xml version="1.0" encoding="%s"?>\n' % encoding
	if output_unicode:
		header = unicode(header)
	fout.write(header)

	# These entity definitions for latin-1 chars are from here:
	# http://www.w3.org/TR/REC-html40/sgml/entities.html
	# also available at: http://www.csparks.com/CharacterEntities.html
	entities = '''

<!DOCTYPE publicwhip
[
<!ENTITY ndash   "&#8211;">
<!ENTITY mdash   "&#8212;">
<!ENTITY iexcl   "&#161;">
<!ENTITY divide  "&#247;">
<!ENTITY euro    "&#8364;">
<!ENTITY trade   "&#8482;">
<!ENTITY bull    "&#8226;">
<!ENTITY lsquo   "&#8216;">
<!ENTITY rsquo   "&#8217;">
<!ENTITY sbquo   "&#8218;">
<!ENTITY ldquo   "&#8220;">
<!ENTITY rdquo   "&#8221;">
<!ENTITY bdquo   "&#8222;">
<!ENTITY dagger  "&#8224;">

<!ENTITY Ouml   "&#214;" >
<!ENTITY szlig  "&#223;" >
<!ENTITY agrave "&#224;" >
<!ENTITY aacute "&#225;" >
<!ENTITY acirc  "&#226;" >
<!ENTITY atilde "&#227;" >
<!ENTITY auml   "&#228;" >
<!ENTITY ccedil "&#231;" >
<!ENTITY egrave "&#232;" >
<!ENTITY eacute "&#233;" >
<!ENTITY ecirc  "&#234;" >
<!ENTITY euml   "&#235;" >
<!ENTITY iacute "&#237;" >
<!ENTITY icirc  "&#238;" >
<!ENTITY iuml	"&#239;" >
<!ENTITY ntilde "&#241;" >
<!ENTITY nbsp   "&#160;" >
<!ENTITY oacute "&#243;" >
<!ENTITY ocirc  "&#244;" >
<!ENTITY ouml   "&#246;" >
<!ENTITY oslash "&#248;" >
<!ENTITY uacute "&#250;" >
<!ENTITY uuml   "&#252;" >
<!ENTITY thorn  "&#254;" >

<!ENTITY pound  "&#163;" >
<!ENTITY sect   "&#167;" >
<!ENTITY copy   "&#169;" >
<!ENTITY reg    "&#174;" >
<!ENTITY deg    "&#176;" >
<!ENTITY plusmn "&#177;" >
<!ENTITY sup2   "&#178;" >
<!ENTITY micro  "&#181;" >
<!ENTITY para   "&#182;" >
<!ENTITY middot "&#183;" >
<!ENTITY ordm   "&#186;" >
<!ENTITY frac14 "&#188;" >
<!ENTITY frac12 "&#189;" >
<!ENTITY frac34 "&#190;" >
<!ENTITY oelig "&#339;" >
<!ENTITY aelig  "&#230;" >

]>

'''

	if output_unicode:
		entities = unicode(entities)

	fout.write(entities)
