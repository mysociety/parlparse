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
my $browser = LWP::UserAgent->new;
my $date= '2005-12-01';
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
    my $args;

    $args->{command}='mp-full-cons-match';
	while (($mpid,$name,$constituency, @parts)= @parts) {
        my $pwid;
        if ($name =~ m/^(.*),(.*)$/) {
            $args->{name}="$2 $1";
        } else {
            $args->{name}=$name;
        }
        $args->{constituency}= $constituency;
        $args->{date}=$date; 

        my $response= $browser->post('http://ukparse.kforge.net/parlparse/rest.cgi', $args);

		my @lines= split /\n/, $response->{_content};
		#print $response->{_content};
        if ($lines[1] eq 'OK') {
            $lines[2]=~ m#member/(\d+)$#;
            $pwid=$1;
        } else {
            warn "Name match failed for  $args->{name} $constituency for $date";
            $pwid=0;
        } 
        $lines.= "$constituency\t$mpid\t$pwid\t$name\n";
    }
	return $lines;
}

