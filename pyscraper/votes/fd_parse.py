# vim:sw=8:ts=8:et:nowrap

# This is an experimental library to try to assist parsing complicated and
# untidy files. It could be done with a large regular expression, but
# experience shows that it then becomes unmanageably difficult.

import sys
import re


standard_patterns={}

# utility functions

def sub(template, values):
	s=re.sub('%\((?P<word>[a-zA-Z]*)(?P<no>\d*)\)',lambda s: values[s.groupdict()['word']](s.groupdict()['no']),template)
	if re.search('%\(',s):
		raise Exception, "Unbalanced %% ( expression in %s" % template
	else:
		return s

def clean(s):
	'''clean removes HTML tags etc from a string

	In order to generate valid XML, there can be no tags etc in the
	value of an attribute.'''

	s=s.replace('<i>','')
	s=s.replace('</i>','')
	
	s=s.replace('&nbsp;',' ')
	s=s.replace('&','&amp;')

	s=s.replace('\x99','&#214')

	return s

def debug(s):
	#print s
	pass

def str_concat(a,b):
	return a + b

def str_flatten(l):
	'''str_flatten concatenates a list of strings into a string'''

	if len(l)>0:
		return reduce(str_concat,l)
	else:
		return ''

# Result classes

class Result:
	def __init__(self,values=[],force=False):
		self.values=values
		self.force=force

	def text(self):
		return str_flatten(self.values)

class Failure(Result):
	def __init__(self):
		Result.__init__(self,[])
		self.success=False

class PatternFailure(Failure):
	def __init__(self,s,env,p):
		Failure.__init__(self)
		self.pattern=p
		self.failurestring=s

	def text(self):
		return 'pattern: %s string=(%s)' % (self.pattern, self.failurestring[:128])

class SeqFailure(Failure):
	def __init__(self,length,pos,result):
		Failure.__init__(self)
		self.pos=pos
		self.result=result
		self.length=length
		self.force=result.force

	def text(self):
		return 'sequence(%s): position=%s(\n%s\n)' % (self.length, self.pos,self.result.text())

class OrFailure(Failure):
	def __init__(self,failures):
		Failure.__init__(self)
		self.failures=failures
		self.force=reduce(lambda a,b: a or b, [x.force for x in failures])

	def text(self):
		return 'or: %s ' % str_flatten([x.text() +'\n' for x in self.failures])

class IfFailure(Failure):
	def __init__(self,failure):
		Failure.__init__(self)
		self.failure=failure
		self.force=failure.force

	def text(self):
		return 'IF: %s\n' % self.failure.text()

class StopFailure(Failure):
	def __init__(self,reason):
		Failure.__init__(self)
		self.reason=reason

	def text(self):
		return 'stop: %s' % self.reason
	
class AnyFailure(Failure):
	def __init__(self,failure,untilfailure):
		Failure.__init__(self)
		self.failure=failure
		self.untilfailure=untilfailure
		self.force=failure.force or untilfailure.force

	def text(self):
		return 'any:\n(any)failure:\n%s\n(any)untilfailure:\n%s\n\n' % (self.failure.text(),self.untilfailure.text())

class Success(Result):
	def __init__(self, values=[]):
		Result.__init__(self,values)
		self.success=True

class PossiblyFailure(Failure):
	def __init__(self, result):
		Failure.__init__(self)
		self.force=True
		self.result=result

	def text(self):
		return 'Possibly(forced):\n%s' % self.result.text()

# pattern operators

def FORCE(f):
	def anonFORCE(s, env):
		(s1,env1,result)=f(s,env)
		if not result.success:
			result.force=True

		return (s1,env1,result)

	return anonFORCE

def ANY(f,until=None,otherwise=None):
	'''repeatedly attemps f, until no more string is consumed, or f fails

	ANY always succeeds, unless there is an otherwise clause, which is tried
	after ANY is attempted unless the until clause matches.'''

	def anonANY(s,env):
		debug('ANY')
		values=[]
		untilresult=Success()

		# Check until clause first, if it succeeds, then stop.

		if until:
			(s1,env1,untilresult)=until(s,env)
			values.extend(untilresult.values)
			if untilresult.success:
				# print "####(any)Any until success1"
				return (s1,env1,Success(values))
			elif untilresult.force:
				# print "####(any)Any until force failure1"
				return (s1,env1,untilresult)

		(s1,env1,result)=f(s,env)
		while len(s1) < len(s) and result.success:
			debug('****(any):%s' % values)
			values.extend(result.values)
			s=s1
			env=env1
			if until:
				(s1,env1,untilresult)=until(s,env)
				debug('(any) until result: %s' % untilresult.success)
				if untilresult.success:
					# print "####(any)Any until success2"
					values.extend(untilresult.values)
					return (s1,env1,Success(values))
				elif untilresult.force:
					# print "####(any)Any until force failure2"
					return (s1,env1,untilresult)

			(s1,env1,result)=f(s,env)
		
		if otherwise:
			(s2,env2,result)=otherwise(s1,env1)
			if result.success:
				# print "####(any)anyotherwise success"
				values.extend(result.values)
				return(s2,env2,Success(values))
			else:
				# print "####(any)anyfailure#"
				return(s1,env1,AnyFailure(result, untilresult))
		else:
			#print "####(any)any plain success"
			return (s1,env1,Success(values))	

	return anonANY

def OR(*args):
	'''each argument is tried in order until one is found that succeeds.'''

	def anonOR(s,env):
		debug('OR')
		failures=[]
		for f in args:
			(s1,env1,result)=f(s,env)
			if result.success:
				return (s1,env1,result)
			else:
				failures.append(result)
			if result.force:
				break

		return (s1,env1,OrFailure(failures))

	return anonOR

def SEQ(*args):
	'''each argument is tried in order, all must succeed for SEQ to succeed.'''

	def anonSEQ(s,env):
		debug('SEQ (length=%s)' % len(args))
		original_string=s
		values=[]
		pos=1
		for l in args:
			debug("****(pos=%s)\n##string:\n%s\n##env:\n%s\n##values:\n%s" % (pos,s[:64],env,values))
			(s,env,result)=l(s,env)
			if not result.success:
				break
			values.extend(result.values)
			pos=pos+1

		debug('endSEQ success=%s value=%s\n========' % (result.success, values))

		if result.success:
			return (s, env, Success(values))
		else:
			return (original_string, env, SeqFailure(len(args), pos,result))
	
	return anonSEQ

def IF(condition, ifsuccess):
	'''IF'''

	def anonIF(s, env):
		(s1,env1,result1)=condition(s,env)
		if result1.success:
			(s,env,result2)=ifsuccess(s1,env1)
			values=result1.values+result2.values
			if result2.success:
				# print "####(if): if success"
				return (s,env,Success(values))
			else:
				return (s,env,IfFailure(result2))
		else:
			return (s,env,IfFailure(result1))

	return anonIF		


def POSSIBLY(f):
	'''POSSIBLY always succeeds, unless f is forced'''

	def anonPOSSIBLY(s,env):
		(s1,env1,result)=f(s,env)
		if result.success:
			return (s1,env1,result)
		elif result.force:
			return (s1, env1, PossiblyFailure(result))
		else:
			return (s,env,Success())
	return anonPOSSIBLY

def CALL(f, callstrings=[], passback={}):

	def anonCALL(s,env):

		substring=str_flatten(map(lambda a: env[a], callstrings))
		local_env=env.copy()
		(s1, env1, result)=f(substring, local_env)

		#print "*CALL env:\n%s\n env1:\n%s\n\nlocal_env\n%s\n" % (env, env1, local_env)

		if result.success:
			for key, newkey in passback.iteritems():
				#print key, newkey
				env[newkey]=local_env[key]
		return (s, env, result)

	return anonCALL
		
def pattern(p, flags=re.IGNORECASE, debug=False):
	prog = re.compile(p,flags)
	def anon_pattern(s,env):
		mobj=prog.match(s)
		if debug:
			print 'pattern p=(%s) s=(%s)\n' % (p, s[:128])

		if mobj:
			result=Success()
			s=s[mobj.end():]
			env.update(mobj.groupdict())
		else:
			result=PatternFailure(s,env,p)
		
		return (s,env,result)
	return anon_pattern

# tagged doesn't get things right if tags is empty I think.

def tagged(first='',tags=[],p='',padding=None, last='', strings={}, plaintext=False):
	s='('
	e='('
	if padding:
		s=s+padding+'|'
		e=e+padding+'|'
	lt=len(tags)
	for i in range(lt):
		s='%s<%s[^>]*?>' % (s, tags[i])
		e='%s</%s>' % (e, tags[i])
		if i==lt-1:
			s='%s)*' % s
			e='%s)*' % e
		else:
			s='%s|' % s
			e='%s|' % e

	if plaintext:
		p=prep_plaintext(p, strings, punctuation=standard_punctuation)

	if len(tags)>0:
		p=first+s+p+e+last
	else:
		p=first + p + last

	return pattern(p)
		

# Don't make [] optional because they are significant all too often.
standard_punctuation=['.',';',',',':']

def prep_plaintext(text,strings={},punctuation=standard_punctuation):
	#print "pre_plaintext: text=%s, strings=%s" % (text, strings)

	stringdict=dict([(v,lambda s:x) for (v,x) in strings.iteritems()])
	stringdict.update(standard_patterns)
	for punc in punctuation:
		text=text.replace(punc,'('+punc+')?')

	text=text.replace('.','\.')
	text=text.replace(']','\]')
	text=text.replace('[','\[')
	
	#print '### sub=%s stringdict=%s' % (text, stringdict)

	text=sub(text, stringdict)

	#print "prep_plaintext returned: %s" % text
	return text

def plaintext(text,strings={},punctuation=standard_punctuation, debug=False):

	return pattern(prep_plaintext(text,strings,punctuation), debug=debug)

def plaintextpar(text, strings={}, punctuation=standard_punctuation):
	#print strings
	return tagged(
		first='\s*',
		tags=['p','ul','br'],
		p=text,
		padding='\s',
		last='',
		strings=strings,
		plaintext=True
		)


def NULL(s,env):
	return(s,env,Success())


# Construction of objects.

def OBJECT(name, body, *args):
	return SEQ(DEBUG('object name=%s' % name),START(name,*args),OUT(body),END(name))

def START(name, *args, **keywords):
	def anonSTART(s,env):
		print "debug: starting object name=%s" % name
		keyvaluelist=[(a, env[a]) for a in args] 
		keyvaluelist.extend(keywords.iteritems())
		attributes=['%s="%s" ' % (key, value) for (key, value) in keyvaluelist]

		result=Success([clean('<%s %s>\n' % (name,str_flatten(attributes)))])

		return (s,env,result)

	return anonSTART


def END(name):
	def anonEND(s,env):
		print "debug: ending object name=%s" % name		
		result=Success([clean('</%s>\n' % name)])

		return (s,env,result)

	return anonEND


def OUT(a):
	def anonOUT(s,env):
		if len(a)==0:
			value=''
		else:
			value=clean(env[a])
		
		result=Success([value])

		return (s,env,result)

	return anonOUT

def OUTPUT(t):
	def anonOUTPUT(s,env):
		result=Success(t)

		return (s,env,result)

	return anonOUTPUT


def DEBUG(t, fail=False):
	def anonDEBUG(s,env):
		
		print 'debug: %s' % t

		if fail:
			return (s, env, Failure())
		else:
			return (s,env,Success())

	return anonDEBUG

def TRACE(cond=False, envlength=48, slength=256, vals=[], fail=False):
	def anonTRACE(s,env):
		if cond:
			print '--------\nTrace:\ns=%s\nenv=%s\n' % (s[:slength],str(env)[:envlength])
			for v in vals:
				if env.has_key(v):
					print '%s=%s' % (v,env[v])
				else:
					print 'unknown key %s' % v
			print '--------\n'

		if fail:
			return (s, env, Failure())
		else:
			return (s,env,Success())
	return anonTRACE	

def STOP(t=''):
	def anonSTOP(s,env):
		return (s,env,StopFailure(t))

	return anonSTOP		
