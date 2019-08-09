#! /usr/bin/env python

import os
import logging

import click
import click_log

import json
import datetime
import dateutil.parser
import re

import requests
import requests_cache

import string

from bs4 import BeautifulSoup, element
from lxml import etree
from lxml.html import soupparser

# Set up logging
logger = logging.getLogger(__name__)
click_log.basic_config(logger)

# Set up the requests cache
cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
requests_cache.install_cache(cache_path, expire_after=60*60*12)

# Load and parsethe configuration file
with open('config.json') as config_json_file:
    logger.debug('Reading config file')
    config = json.load(config_json_file)

# Set our constants
ASSEMBLY_DOMAIN = config['assembly_domain']
DEFAULT_START_DATE = config['default_start_date']
PUBLIC_WHIP_QUESTION_ID_PREFIX = config['public_whip_question_id_prefix']
CURRENT_MAYOR_NAME = config['current_mayor_name']
NAME_REGEX_TO_STRIP = config['name_regex_to_strip']
NAME_CORRECTIONS = config['name_corrections']

# This needs to match the type from xml2db.pl in TWFY
XML_FILE_PREFIX = config['xml_file_prefix']

CLI_DATETIME_FORMAT = click.DateTime(formats=('%Y-%m-%d',))

STATE_JSON_FILENAME = 'state.json'

EMPTY_STATE_OBJECT = {
    'dates': {},
    'questions': {}
}


def getScraperState(output_folder):
    ''' Load the scraper's state from file. '''

    state_file = os.path.join(output_folder, STATE_JSON_FILENAME)

    # Check this file exists before we load it
    if os.path.exists(state_file):

        with open(state_file) as state_json_file:
            logger.debug('Reading state file')
            state = json.load(state_json_file)

    # If not, just use the empty object. It'll be written at wrap-up.
    else:
        logger.warning('Could not find existing state file at {}, creating new one'.format(state_file))
        state = EMPTY_STATE_OBJECT

    return state


def writeScraperState(state, output_folder):
    ''' Write the scraper's state back out to file. '''

    output_file = os.path.join(output_folder, STATE_JSON_FILENAME)

    try:
        json_string = json.dumps(state, indent=2, default=str)
        with open(output_file, 'w') as state_json_file:
            logger.debug('Writing state file')
            state_json_file.write(json_string)
    except TypeError, e:
        logger.error('Could not serialise to valid JSON: {}'.format(str(e)))


def getDatesInRange(start, end):
    ''' Return an array of dates between (and inclusive of) those given. '''

    delta = end - start
    dates = []
    for i in range(delta.days + 1):
        date = start + datetime.timedelta(days=i)
        # Convert it to a date rather than a datetime
        dates.append(date)

    return dates


def scrapeAssemblyMeetingOnDate(date):
    ''' Scrape the Mayor's Questions meeting page for the provided date '''

    meeting_date_string = date.strftime('%Y/%m/%d')

    meeting_date_url = ASSEMBLY_DOMAIN + '/questions/meeting/mqt/' + meeting_date_string

    logger.debug('Scraping meeting page at {}'.format(meeting_date_url))

    meeting_page = requests.get(meeting_date_url)

    scraped_data = {
        'http_status': str(meeting_page.status_code)
    }

    if meeting_page.status_code == 404:
        logger.info('Meeting on {} returned HTTP 404'.format(date))
        scraped_data['to_scrape'] = False
    elif meeting_page.status_code == 200:
        logger.info('Meeting on {} returned HTTP 200'.format(date))

        scraped_data['sessions'] = parseAssemblyMeetingToSessions(meeting_page.content)
        scraped_data['questions'] = []

        if len(scraped_data['sessions']) > 0:
            scraped_data['to_scrape'] = False
            for session in scraped_data['sessions']:
                scraped_data['questions'] += scrapeSessionAtUrl(session)
        elif meeting_date_string != '2019/02/25': # Exempt date we know lacks sessions
            logger.warning('Meeting on {} doesn\'t seem to have any sessions!'.format(date))
            scraped_data['to_scrape'] = True
    else:
        logger.warning('Meeting on {} returned HTTP {}'.format(date, meeting_page.status_code))
        scraped_data['to_scrape'] = True

    return scraped_data


def parseAssemblyMeetingToSessions(content):
    ''' Parse an assembly meeting page and return a list of its sessions. '''

    soup = BeautifulSoup(content)

    sessions_in_content = soup.find_all('div', class_='entity-meetingsession')

    sessions_in_meeting = []

    for session in sessions_in_content:
        session_title = session.a.text
        session_url = session.a.get('href')

        logger.debug('Found session "{}" at URL {}'.format(session_title, session_url))

        sessions_in_meeting.append(session_url)

    return sessions_in_meeting


def scrapeSessionAtUrl(session_url):
    ''' Scrape a given session URL and extract the questions within. '''

    session_full_url = ASSEMBLY_DOMAIN + session_url

    logger.debug('Scraping session page at {}'.format(session_full_url))

    session_page = requests.get(session_full_url)

    questions_in_session = parseSessionToQuestions(session_page.content)

    return questions_in_session


def parseSessionToQuestions(content):

    soup = BeautifulSoup(content)

    questions_in_content = soup.find_all('tr', class_='question')

    questions_in_session = []

    for question_row in questions_in_content:

        question_row_cells = question_row.findAll('td')

        question_number = question_row_cells[1].text

        logger.debug('Found question {}'.format(question_number))

        questions_in_session.append(question_number)

    return questions_in_session


def scrapeQuestionWithId(question_id):
    ''' Scrape the page for a given question ID and return structured data. '''

    logger.debug('Scraping question {}'.format(question_id))

    question_full_url = ASSEMBLY_DOMAIN + '/questions/' + question_id

    logger.debug('Scraping question page at {}'.format(question_full_url))

    question_page = requests.get(question_full_url)

    if question_page.status_code == 200:
        logger.debug('Question {} returned HTTP 200'.format(question_id))

        question_parsed_data = parseQuestionPage(question_page.content)

    else:
        logger.warning('Question {} returned HTTP {}'.format(question_id, question_page.status_code))
        context.obj['state']['questions'][question_id]['to_scrape'] = True

        question_parsed_data = None

    return question_parsed_data


def parseQuestionPage(content):
    ''' Actually take the HTML from a scraped question page and turn it into a structured object. '''

    soup = BeautifulSoup(content)

    # We use the canonical URL just in case anything exotic has happened with redirects.
    canonical_url = soup.find('link', {'rel': 'canonical'})['href']

    main_content = soup.find('div', role='main')

    # Pull the title

    question_title = main_content.h1.text.strip()

    logger.debug(u'Question title is {}'.format(question_title))

    # Extract who asked it

    asked_by_name = main_content.find('div', class_='field--name-field-asked-by').find('div', class_='field__item').text.strip()
    asked_by_person = getSpeakerObjectFromName(asked_by_name)

    logger.debug(u'Question asked by {}'.format(asked_by_person['name']))

    # Try to extract the actual question

    question_text = main_content.find('div', class_='field--name-body').find('div', class_='field__item')

    question_p_elements = main_content\
        .find('section', class_='question')\
        .findAll('p')

    question_paragraphs = []

    for paragraph in question_p_elements:

        # Some paragraphs are helpfully empty. Deal with those
        if paragraph.text.strip() != '':
            # NB at this point we're still sending BeautifulSoup objects
            question_paragraphs.append(paragraph)

    # We ignore the speaker which comes back with this, but this function otherwise does all the tidying needed
    question_with_speaker = splitTextToSpeeches(question_text)[0]
    question_text_paragraphs = question_with_speaker['paragraphs']

    # Now we know the title and the question, assemble the basic question object to send back

    question_object = {
        'title': question_title,
        'canonical_url': canonical_url,
        'question_text_paragraphs': question_text_paragraphs,
        'asked_by': asked_by_person
    }

    # Try parse the actual answers out
    answers_object = parseAnswersFromQuestionPage(main_content)

    # Got answers?

    if len(answers_object['answers']) > 0:
        question_object['answered'] = True
        question_object['answers'] = answers_object['answers']
        question_object['answered_date'] = answers_object['answered_date']
    else:
        question_object['answered'] = False

    # Send the parsed data back upstream

    return question_object


def parseAnswersFromQuestionPage(page_content):
    ''' Given page content, see if we can get answers. '''

    # Look to see if there are any answers given

    answers_div = page_content.find('div', class_='answers')

    answers_object = {
        'answers': []
    }

    answer_articles = answers_div.findAll('article', class_='node--answer')
    for answer_article in answer_articles:
        # If there's a paragraph with a class of 'holding', we're waiting for an answer.
        if answer_article.find('p', class_='holding'):
            logger.debug('Question is awaiting an answer')
            continue

        # Sometimes the question just has no answer. Because this is "currently", still assume it's unanswered.
        elif answer_article.find('div', class_='no-answer'):
            logger.debug('Question has no available answers.')
            continue

        # Get the date this was answered - this is the important one, not when it was asked,

        answer_date = answer_article.find('div', class_='field--name-post-date').find('div', class_='field__item').text

        answers_object['answered_date'] = dateutil.parser.parse(answer_date).date()
        logger.debug('Question answered on {}'.format(answers_object['answered_date']))

        # Find who answered it

        answered_by_name = answer_article.find('div', class_='field--name-field-answered-by').find('div', class_='field__item').text.strip()
        answered_by_person = getSpeakerObjectFromName(answered_by_name)

        logger.debug(u'Question answered by {}'.format(answered_by_person['name']))

        answer_p_elements = answer_article\
            .find('div', class_='field--name-body')\
            .findAll('p')

        answer_paragraphs = []

        for paragraph in answer_p_elements:

            # Some paragraphs are helpfully empty. Deal with those
            if paragraph.text.strip() != '':
                # NB at this point we're still sending BeautifulSoup objects
                answer_paragraphs.append(paragraph)

        logger.debug('Found {} paragraphs of non-empty answers on page'.format(len(answer_paragraphs)))

        # Send the paragraphs of answers off to be sliced if this is multiple parts of a conversation
        answers_by_speech = splitTextToSpeeches(answer_paragraphs)

        logger.debug('Found {} individual speeches within this answer'.format(len(answers_by_speech)))

        for i, answer in enumerate(answers_by_speech):

            # This makes sure the answer has a speaker - if it doesn't, something is wrong
            if answer['speaker']:
                answers_object['answers'].append({
                    'speaker': answer['speaker'],
                    'paragraphs': answer['paragraphs']
                })
            else:
                # If this is the first speech with no speaker, it's the answerer.
                if (i == 0):
                    logger.debug('First speech with no detected speaker, using "Answered By"')
                    answers_object['answers'].append({
                        'speaker': answered_by_person,
                        'paragraphs': answer['paragraphs']
                    })
                else:
                    logger.warning('Speech with no detected speaker in question {}!'.format(canonical_url))

    return answers_object


def stripPatternsFromName(name):

    patterns_to_strip = True

    while patterns_to_strip:

        original_name = name

        for pattern in NAME_REGEX_TO_STRIP:
            name = re.sub(pattern, '', name)

        if name == original_name:
            patterns_to_strip = False

    return name.strip()


def getPersonIDFromName(name):
    ''' Turn a name into a speaker ID. '''

    if name == 'The Mayor':
        name = CURRENT_MAYOR_NAME

    # If this person's name has a correction, use that instead
    if name in NAME_CORRECTIONS:
        name = NAME_CORRECTIONS[name]

    return ASSEMBLY_MEMBERS_BY_NAME.get(name)


def getSpeakerObjectFromName(name):
    ''' Given a name, try to find a speaker ID and return a whole object. '''

    name = name.replace(u'\u00a0', ' ')
    name = stripPatternsFromName(name)
    id = getPersonIDFromName(name)
    if not id:
        if 'Liz Peace' not in name:
            logger.warning(u'Could not match name {} to any assembly member'.format(name))
        id = 'unknown'

    return {
        'id': id,
        'name': name
    }


def cleanParagraphText(text):

    # Remove non-breaking spaces followed by a space.
    text = text.replace(u'\u00a0 ', ' ')

    # Strip trailing whitespace
    text = text.strip()

    return text


def getSpeakerAndTextFromParagraph(paragraph):
    ''' For the given paragraph text, try to detect if it is led by a speaker's name. '''

    # Strong tags are used to mark speaker names in the source
    name_candidate = paragraph.find('strong')
    if name_candidate:

        # Sanity check if this matches the expected format of speaker names - a name followed by a colon
        if re.match('^.:', name_candidate.text):

            # extract() removes the element from the beautifulsoup tree and returns it
            speaker_name = name_candidate.extract()

            speaker = getSpeakerObjectFromName(speaker_name.text.replace(':', '').strip())

        else:
            speaker =  False

    else:
        speaker = False

    return {
        'speaker': speaker,
        'text': cleanParagraphText(paragraph.text)
    }


def splitTextToSpeeches(text_paragraphs):
    ''' Sometimes text has several speeches by different people within it. Try isolate those. '''

    answers_by_speech = []

    paragraphs_in_speech = []
    current_speaker = False

    for paragraph in text_paragraphs:

        if isinstance(paragraph, element.NavigableString):
            logger.debug('Ignored NavigableString')

        else:

            # Ignore entirely empty paragraphs
            if paragraph.text != '':

                paragraph_with_speaker = getSpeakerAndTextFromParagraph(paragraph)

                # If this paragraph is a new speaker, wrap up the answer and start a new one
                if paragraph_with_speaker['speaker']:
                    if len(paragraphs_in_speech) > 0:
                        answers_by_speech.append({
                            'paragraphs': paragraphs_in_speech,
                            'speaker': current_speaker
                        })

                    logger.debug('New speaker! Last speech was {} paragraphs'.format(len(paragraphs_in_speech)))

                    paragraphs_in_speech = [paragraph_with_speaker['text']]
                    current_speaker = paragraph_with_speaker['speaker']

                # If this isn't a new speaker, just append to the current one
                else:
                    paragraphs_in_speech.append(paragraph_with_speaker['text'])

    # Finally, wrap up the whole thing if there's anything remaining
    if len(paragraphs_in_speech) > 0:

        logger.debug('Final speech was {} paragraphs'.format(len(paragraphs_in_speech)))

        answers_by_speech.append({
            'paragraphs': paragraphs_in_speech,
            'speaker': current_speaker
        })

    logger.debug('Split {} paragraphs into {} speeches'.format(len(text_paragraphs), len(answers_by_speech)))

    return answers_by_speech


def buildXMLForQuestions(questions):
    ''' Given a date, collect answered questions and output the appropriate XML file. '''

    pwxml = etree.Element('publicwhip')

    for question_id, question in questions.items():

        question_number = '{}.{}'.format(question['answered_date'].strftime('%Y-%m-%d'), question['canonical_url'].split('/')[-1])
        pw_root_id = '{}{}'.format(PUBLIC_WHIP_QUESTION_ID_PREFIX, question_number)

        pw_heading_id = pw_root_id + '.h'
        heading_element = etree.SubElement(pwxml, 'minor-heading', nospeaker='true', id=pw_heading_id)
        heading_element.text = question['title']

        pw_question_id = pw_root_id + '.q0'
        question_element = etree.SubElement(pwxml, 'question',
                                            id=pw_question_id,
                                            url=question['canonical_url'],
                                            speakername=question['asked_by']['name'],
                                            person_id=question['asked_by']['id']
                                            )

        for paragraph in question['question_text_paragraphs']:
            paragraph_element = etree.SubElement(question_element, 'p')
            paragraph_element.text = paragraph

        for answer_index, answer in enumerate(question['answers']):

            pw_answer_id = pw_root_id + '.r' + str(answer_index)

            answer_element = etree.SubElement(pwxml, 'reply',
                                              id=pw_answer_id,
                                              speakername=answer['speaker']['name'],
                                              person_id=answer['speaker']['id']
                                              )

            for paragraph in answer['paragraphs']:
                paragraph_element = etree.SubElement(answer_element, 'p')
                paragraph_element.text = paragraph

    return pwxml


def writeXMLToFile(lxml, file):
    ''' Write an lxml element out to file. '''

    # Make a new document tree
    xmldoc = etree.ElementTree(lxml)

    # Save to XML file
    with open(file, 'w') as outFile:
        xmldoc.write(outFile, pretty_print=True, encoding='utf-8')
        logger.debug('Written XML to {}'.format(file))


def buildDateStatusObjectFromScrape(meeting_scrape_data):
    ''' Format a date's status for storing in the state file. '''

    status_object = {
        'http_status': meeting_scrape_data['http_status'],
        'to_scrape': meeting_scrape_data['to_scrape'] if 'to_scrape' in meeting_scrape_data else True,
        'updated': datetime.datetime.today()
    }

    if 'sessions' in meeting_scrape_data:
        status_object['sessions_count'] = len(meeting_scrape_data['sessions'])

    if 'questions' in meeting_scrape_data:
        status_object['questions_count'] = len(meeting_scrape_data['questions'])

    return status_object


def loadMembershipsFromFile(members_file):
    ''' Parse the provided file and extract data on Assembly members. '''

    # We don't need to open this file, since Click deals with that
    members_raw_data = json.load(members_file)

    logger.debug('Loaded {} people from {}'.format(len(members_raw_data['persons']), members_file.name))

    people_by_id = {}

    # This unpacks all the people in the JSON so we can pull a person's name back from their ID
    for person in members_raw_data['persons']:
        people_by_id[person['id']] = person

    # This loops through each membership, checks to see if it's for the Assembly, if so adds it to the map

    person_ids_by_name = {}

    for membership in members_raw_data['memberships']:
        if membership.get('organization_id') == 'london-assembly':
            name = getNameFromPerson(people_by_id[membership['person_id']])

            if name not in person_ids_by_name:
                person_ids_by_name[name] = membership['person_id']
                logger.debug(u'Added ID map for for {}'.format(name))
            else:
                if person_ids_by_name[name] != membership['person_id']:
                    raise Exception('Multiple people with name {}'.format(name))

    logger.debug('Added {} names with Assembly memberships'.format(len(person_ids_by_name)))

    return person_ids_by_name


def getNameFromPerson(person):

    for name in person.get('other_names', []):
        if name['note'] == 'Main':
            return name['given_name'] + ' ' + name['family_name']

    raise Exception('Unable to find main name for person {}'.format(person['id']))


@click.group()
@click_log.simple_verbosity_option(logger, default='warning')
@click.option('-o', '--out', required=True, type=click.Path(exists=True, file_okay=False, writable=True), help='The directory to place output and state files.')
@click.pass_context
def cli(context, out):
    context.ensure_object(dict)

    context.obj['OUTPUT_FOLDER'] = out

    # Get the current state file, parse it and assign to the context
    context.obj['state'] = getScraperState(context.obj['OUTPUT_FOLDER'])


@cli.command()
@click.option('-s', '--start', type=CLI_DATETIME_FORMAT, help='The first date of the range to be scrape.')
@click.option('-e', '--end', type=CLI_DATETIME_FORMAT, help='The last date of the range to be scraped.')
@click.option('--force-scrape-dates', is_flag=True, help='Force all dates in the range to be re-scraped regardless of status')
@click.option('--force-refresh-questions', is_flag=True, help='Force all detected questions to have their state refreshed')
@click.pass_context
def meetings(context, start, end, force_scrape_dates, force_refresh_questions):
    ''' Get a list of questions from the London Assembly website asked between the dates given. '''

    logger.info('Scraping London Assembly')

    if start:
        start_date = start.date()
        logger.debug('End date has been explicitly set to {} by CLI'.format(start_date))
    else:
        start_date = datetime.datetime.strptime(DEFAULT_START_DATE, '%Y-%m-%d').date()
        logger.debug('Start date has been automatically set to {} by config'.format(start_date))

    if end:
        end_date = end.date()
        logger.debug('End date has been explicitly set to {} by CLI'.format(end_date))
    else:
        # Yesterday
        end_date = (datetime.datetime.today() - datetime.timedelta(days=1)).date()
        logger.debug('End date has been automatically set to {} (yesterday)'.format(end_date))

    if end_date < start_date:
        logger.error('End date is before the start date. Aborting.')
        return

    dates_in_range = getDatesInRange(start_date, end_date)

    logger.info('Targetting {} dates between {} and {}.'.format(len(dates_in_range), start_date, end_date))

    questions_in_range = []

    with click.progressbar(dates_in_range) as bar:
        for date in bar:

            # Check to see if we should actually scrape this date
            if force_scrape_dates \
             or str(date) not in context.obj['state']['dates'] \
             or (str(date) in context.obj['state']['dates'] and context.obj['state']['dates'][str(date)]['to_scrape']):

                    logger.info('Scraping date {}'.format(date))

                    meeting_scrape_data = scrapeAssemblyMeetingOnDate(date)

                    if 'questions' in meeting_scrape_data:
                        logger.info('{} has {} questions'.format(date, len(meeting_scrape_data['questions'])))

                        questions_in_range += meeting_scrape_data['questions']

                    context.obj['state']['dates'][str(date)] = buildDateStatusObjectFromScrape(meeting_scrape_data)

            else:

                logger.debug('Skipping date {} (already scraped successfully)'.format(date))

    logger.info('{} questions found in this scrape'.format(len(questions_in_range)))

    for question in questions_in_range:
        # Only do this if the question doesn't already exist, or we're forcing a refresh
        if force_refresh_questions or question not in context.obj['state']['questions']:
            context.obj['state']['questions'][question] = {
                'to_scrape': True,
                'scrape_requested_on': datetime.datetime.today()
            }


@cli.command()
@click.option('-l', '--limit', type=int, help='The maximum number of questions to scrape')
@click.option('-m', '--members', required=True, type=click.File(), help='The members.json file to match names against.')
@click.option('--dry-run', is_flag=True, help='Should questions be marked as not needing scraping in future?')
@click.pass_context
def questions(context, limit, members, dry_run):
    ''' Update all questions which are still pending a scrape. '''

    # Try load in the Members data first - if that fails there's no point continuing.
    # ASSEMBLY_MEMBERS_BY_NAME is global to avoid having to pass it down every function until names are turned to IDs
    global ASSEMBLY_MEMBERS_BY_NAME
    ASSEMBLY_MEMBERS_BY_NAME = loadMembershipsFromFile(members)

    logger.debug('{} questions are known to exist'.format(len(context.obj['state']['questions'])))

    questions_to_scrape = []

    for question_id, question_state in context.obj['state']['questions'].items():
        if question_state['to_scrape']:
            questions_to_scrape.append(question_id)

    # If a limit is provided, set it. Otherwise, scrape the lot.

    if limit:
        questions_to_scrape = questions_to_scrape[:limit]

    logger.info('Scraping {} questions'.format(len(questions_to_scrape)))

    scraped_questions = {}

    with click.progressbar(questions_to_scrape) as bar:
        for question_id in bar:

            scraped_questions[question_id] = scrapeQuestionWithId(question_id)
            context.obj['state']['questions'][question_id]['scraped_at'] = datetime.datetime.today()

    answered_questions = {}

    for question_id, question_object in scraped_questions.items():

        if question_object['answered'] == True:
            answered_date = question_object['answered_date']
            answered_questions.setdefault(answered_date, {})[question_id] = question_object

            if not dry_run:
                # Setting this question's scrape state to False means it won't be processed again
                context.obj['state']['questions'][question_id]['to_scrape'] = False

    logger.info('{} questions have had answers found in this scrape'.format(len(answered_questions)))

    # If there are new answers, write out our file.

    if len(answered_questions) > 0:
        for date, qns in answered_questions.items():

            i = 0;

            file_needs_writing = True

            while file_needs_writing:

                date_string = date.strftime('%Y-%m-%d')
                letter_suffix = string.ascii_lowercase[i]
                output_filename = XML_FILE_PREFIX + date_string + letter_suffix + '.xml'
                output_file = os.path.join(context.obj['OUTPUT_FOLDER'], output_filename)

                if os.path.exists(output_file):
                    i = i + 1
                else:
                    # The file doesn't exist, write it!
                    writeXMLToFile(buildXMLForQuestions(qns), output_file)
                    file_needs_writing = False


@cli.command(name='set_date_scrape')
@click.option('--date', required=True, type=CLI_DATETIME_FORMAT, help='The date to alter the scrape status of.')
@click.option('--scrape/--no-scrape', required=True, help='Should the date be marked as needing scraping, or not?')
@click.pass_context
def set_date_scrape(context, date, scrape):
    ''' Explicitly set if a date should be scraped or not at the next run.

    Used to either manually request a re-scraping of a date, or to suppress future scraping of a date. '''

    date = date.date()

    click.echo('Setting scrape status of {} to {}'.format(date, scrape))

    if date in context.obj['state']['dates']:
        context.obj['state']['dates'][str(date)]['to_scrape'] = scrape
    else:
        context.obj['state']['dates'][str(date)] = {
            'to_scrape': scrape
        }


@cli.command(name='set_question_scrape')
@click.option('--id', required=True, help='The question to alter the scrape status.')
@click.option('--scrape/--no-scrape', required=True, help='Should the question be marked as needing scraping, or not?')
@click.pass_context
def set_question_scrape(context, id, scrape):
    ''' Explicitly set if a question should be scraped or not at the next run.

    Used to either manually request a re-scraping of a question, or to suppress future scraping of a question. '''

    click.echo('Setting scrape status of {} to {}'.format(id, scrape))

    if id in context.obj['state']['questions']:
        context.obj['state']['questions'][id]['to_scrape'] = scrape
    else:
        context.obj['state']['questions'][id] = {
            'to_scrape': scrape
        }


@cli.command(name='reset_state')
@click.pass_context
def reset_state(context):
    ''' Reset the scraper's state file, wiping all knowledge of dates and questions. '''

    click.secho('Resetting the state file will wipe all information about the states of dates and questions.', bg='red', fg='white')

    if click.confirm('Are you really sure you want to do this?', abort=True):
        logger.info('Resetting scraper state file')

        context.obj['state'] = EMPTY_STATE_OBJECT

        click.echo('All done. Have a nice day.')


@cli.resultcallback()
@click.pass_context
def process_result(context, result, **kwargs):
    ''' Called after anything in the CLI command group, to write the state back to the file. '''
    writeScraperState(context.obj['state'], context.obj['OUTPUT_FOLDER'])


if __name__ == '__main__':
    cli(obj={})
