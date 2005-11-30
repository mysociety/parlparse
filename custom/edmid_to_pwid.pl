#!/usr/bin/perl

# parser which takes edmi.parliament.uk Early Day Motions and
# converts them to an XML file.
#
# Still to do: 
# 	include TWFY person identifiers

use warnings;
use strict;
use LWP::UserAgent;
use XML::Simple;
use Inline 'Python';
my $browser = LWP::UserAgent->new;
$browser->agent("www.TheyWorkForYou.com EDM fetcher - run by theyworkforyou\@msmith.net");
my %EDM;
my $index_url= 'http://edmi.parliament.uk/EDMi/';
my $mplist_url= $index_url. 'MemberList.aspx?__EVENTTARGET=_alpha1:_';
my $Parl_Session= '875'; # hardcode to 05-06 for now
my $Parl_Session_readable= '05-06'; # hardcode to 05-06 for now
my $dir=shift || die "usage: $0 <output dir>\n";

{
	&setup_cookies($index_url); # it'll get redirected to the front page anyway
	open (OUT, ">$dir/people.txt") || die "can't open $dir/people.txt : $!";
	print OUT "Constituency\tPIMS_MP_ID\tPublicWhipID\tName\n";
	print OUT &indexes_fetch($index_url, {});
	close (OUT);
}

sub setup_cookies {
	my $url= shift;
	$browser->cookie_jar({});
	my $response = $browser->get($url);

	# we don't need to do anything else
}



sub indexes_fetch {
	my $url= shift;
	my $args= shift;
	$args->{'_MenuCtrl:ddlSession'} = $Parl_Session;
	$args->{'ddlSortedBy'} = 1;
	$args->{'ddlStatus'} = 0;
	if (defined $ENV{DEBUG}) {print STDERR "Fetching $url\n";}
	my $return='';
	my $response = $browser->post($url, $args); # args that don't change each time
	if($response->code == 200) {
		my $content= $response->{_content};
		#if (defined $ENV{DEBUG}) {print STDERR "$content\n";}
		foreach my $letter ('a' .. 'z') {
			$return.= &mp_list_parse($letter);
		}
	} else {
		die "Hmm, couldn't access it: ", $response->status_line, "\n";
	}
	return ($return);
}

sub mp_list_parse {
	my $letter= shift;	
	my $page= $browser->get($mplist_url . $letter);
	my $lines='';
	#print $page->content;
	my (@parts, $mpid, $name, $constituency);
	@parts = $page->content =~ m#<td><a href='EDMByMember\.aspx\?MID=(\d+).*?>([^>]+)</a></td>\s*<td>([^<]+)</td>#scg;

	while (($mpid,$name,$constituency, @parts)= @parts) {
        my $pwid;
        $pwid=mfcl($name, $constituency);
        $lines.= "$constituency\t$mpid\t$pwid\t$name\n";
	}
	return $lines;
}

__END__
__Python__
import datetime
import sys
import urllib
import urlparse
import re
import sets

sys.path.append("../pyscraper/")
from resolvemembernames import memberList
date_today= datetime.date.today().isoformat()
def mfcl (name, cons): 
    a,b,c = memberList.matchfullnamecons(name, cons, date_today)
    return a
