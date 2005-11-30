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
$browser->agent("www.TheyWorkForYou.com EDM fetcher - run by theyworkforyou\@msmith.net");
my %EDM;
my $base_url= 'http://edmi.parliament.uk/EDMi/';
my $index_url= $base_url . 'EDMList.aspx';
my $Parl_Session= '875'; # hardcode to 05-06 for now
my $Parl_Session_readable= '05-06'; # hardcode to 05-06 for now
my $dir=shift || die "usage: $0 <output dir>\n";
my %MPmap;
{
	&parse_mpid_table();
	&setup_cookies($index_url); # it'll get redirected to the front page anyway
	&indexes_fetch($index_url, {});

	open (OUT, ">$dir/$Parl_Session_readable.xml") || die "can't open $dir/$Parl_Session_readable.xml:$!";
	my $edm;
	$edm->{"edm"}->{"session"}->{"edm_session_name"}="$Parl_Session_readable";
	$edm->{"edm"}->{"session"}->{"edm_session_id"}="$Parl_Session";
	$edm->{"edm"}->{"session"}->{"motion"}=\%EDM;
	print OUT XMLout ($edm, KeepRoot=>1 , NoAttr=>1, AttrIndent=> 1);
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
	my $response = $browser->post($url, $args); # args that don't change each time
	if($response->code == 200) {
		my $content= $response->{_content};
		#if (defined $ENV{DEBUG}) {print STDERR "$content\n";}
		&index_parse($content);
	} else {
		die "Hmm, couldn't access it: ", $response->status_line, "\n";
	}
	#foreach my $k (sort keys %args){ print "\n\n\n$k - $args{$k}\n"; }
}

sub index_parse {
	my $html= shift;
	$html=~ s#
?\n\s*##g;
	#print $html;
	my ($number, $parl_edmid, $edm_title, $edm_by, $signatures);
	my @matches = $html=~ m#<td class="edm-number">\s*<span id="[^"]+">\s*([\dA]+)\s*</span>\s*</td>\s*<td><a href='EDMDetails\.aspx\?EDMID=(\d+)\D.*?'>(.*?)</a></td>\s*<td><a href='EDMByMember\.aspx\?MID=\d+.*?'>([^<]+)</a>\s*</td>\s*<td class="signature-number">(\d+)</td>#micg ;
	if (defined $ENV{DEBUG}) {print STDERR "$#matches matches\n";}
	while (($number, $parl_edmid, $edm_title, $edm_by, $signatures, @matches)= @matches){
	if (defined $ENV{DEBUG}){	print  STDERR "$number $edm_title\n";}

		if (defined $EDM{$number} and defined $EDM{$number}{'title'}) {
			# you can have amendments on a page before the actual EDM being amended
			print STDERR "index is looping; bailing out\n";
			return;
		}
		$EDM{$number}{'edm_in_session'}= $number;
		$EDM{$number}{'title'}= $edm_title;
		$EDM{$number}{'primary_sponsor'}= $edm_by;
		$EDM{$number}{'signatures'}= $signatures;
		$EDM{$number}{'parliament_edmid'}= $parl_edmid;
		$EDM{$number}{'has_amendments'}||= 0;
		$EDM{$number}{'is_amendment'}= 0;

		if ($number =~ /^(\d+)A/) {
			$EDM{$1}{'has_amendments'}++;
			$EDM{$number}{'is_amendment'}=1;
		}
		&parse_motion($EDM{$number});
	}

	if ($html=~ m#<input type="submit" name="(_Pagination1:btnNextPage)"(.*?)>#) {
		my $next_page= $1;
		if ($2 !~ /disabled/) {
			if ($html=~ m#name="(__VIEWSTATE)" value="([^"]+)"#i) {
				#			&indexes_fetch($index_url, {"_MenuCtrl:hdSessionID"=>'', $next_page=> "", "$1" => "$2", "__EVENTTARGET"=> '', "__EVENTARGUMENT" => ''}); # args that could change each time
			}
		}
	}
}



sub parse_motion {
	my $info_ref= shift;
	my $response= $browser->get($base_url . 'EDMDetails.aspx?EDMID='.$info_ref->{parliament_edmid});
 	my $content= $response->{_content};
	$content=~ s#
?\n\s*##g;
	$content=~ m#<div class="DateDetail">([\d\.\s]+)</div>#;
	$info_ref->{date}=$1;
	$content=~ m#<!--\s*Motion Text Display -->\s*<p><span class=".*?">(.*?)</span>#mcgi;
	$info_ref->{motion}=$1;

	my ($memberid, $order, $name, @matches);
	my $pw_id;
	(@matches)= $content=~ m#<a\s*href='EDMByMember\.aspx\?MID=(\d+)'>\s*<span id="Sigs__ctl(\d+)_lblMember"><i>(.*?)</i></span>#mcig;
	while (($memberid, $order, $name, @matches)= @matches) {
		$info_ref->{sponsored_by}->{$order}->{name}= $name;
		#$info_ref->{sponsored_by}->{$order}->{position}= $order;
		$info_ref->{sponsored_by}->{$order}->{edm_memberid}= $memberid;
		$info_ref->{sponsored_by}->{$order}->{pw_memberid}= $MPmap{$memberid} || 'missing';
	}
	(@matches)= $content=~ m#<a\s*href='EDMByMember\.aspx\?MID=(\d+)'>\s*<span id="Sigs__ctl(\d+)_lblMember">(.*?)</span>#mcig;
	while (($memberid, $order, $name, @matches)= @matches) {
		next if $name =~ /<[bi]>/;
		$info_ref->{supported_by}->{$order}->{name}= $name;
		#$info_ref->{supported_by}->{$order}->{position}= $name;
		$info_ref->{supported_by}->{$order}->{edm_memberid}= $memberid;
		#$info_ref->{supported}->[$order -1]="$name";
		$info_ref->{supported_by}->{$order}->{pw_memberid}= $MPmap{$memberid} || 'missing';
	}
	#print "$info_ref->{motion}\n";

}



sub parse_mpid_table  {
    my $line;
	open (LIST, "$dir/people.txt") || die "can't open $dir/people.txt: $!";
	while ($line = <LIST>) {
		chomp($line);
		#         "Constituency\tPIMS_MP_ID\tPublicWhipID\tName\n";
		my ($constituency, $pims_id, $PW_id, $name) = split /\t/, $line;
		$MPmap{$pims_id}=$PW_id;
	}
	close (LIST);

}
