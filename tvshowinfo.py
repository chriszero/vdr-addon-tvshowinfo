#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable-msg=C0301
"""
This little program is connecting to thetvdb.com to get the requested show
and give the data back to stdout so it can be used with the vdr epgsearch plugin.
"""

from pytvdbapi import api
import argparse
import codecs
import difflib
import logging
import os
import re
import sys

__delimiter__ = "~"
__tvdb_apikey__ = "083D567677C1B555"


def find_in_path(file_name, path=None):
    """
    Search for file in the defined pathes
    """
    path = path or '/etc/tvshowinfo:/etc/vdr/plugins/tvshowinfo'
    for directory in path.split(os.pathsep):
        file_path = os.path.abspath(os.path.join(directory, file_name))
        if os.path.exists(file_path):
            return file_path
    return file_name


def e_error(description, exit_code=1):
    """
    Print error message and exit with given code
    """
    logging.debug(description)
    sys.exit(exit_code)


def s_clean(value):
    """
    Clean a string (episode) from unneeded information
    """
    search = re.split('[\(\)]', value, 2)
    value = search[0].strip()
    # add again number extensions
    for ext in search:
        try:
            int(ext)

            # add the ext only if it is not the complete name
            if value != ext.strip():
                value = value + " (" + ext.strip() + ")"

        except:  # pylint: disable-msg=W0702
            continue

    return value


def s_prepare(value):
    """
    Prepare a string by removing all special characters from it
    """
    value = re.sub('[^A-Za-z0-9 ]', '', value)
    return value.encode('utf-8').lower()


def check_exceptions_tvshow(tvshow):
    """
    check for naming exceptions
    some code of this is from the sickbeard project
    """
    searchkey = ""
    db_file = find_in_path('exceptions.txt')
    db_exceptions = codecs.open(db_file, 'r', 'utf-8')
    for line in db_exceptions.readlines():
        tvdb_id, sep, aliases = line.partition(':')  # pylint: disable-msg=W0612

        if not aliases:
            continue

        tvdb_id = int(tvdb_id)

        # regex out the list of shows, taking \' into account
        alias_list = [re.sub(r'\\(.)', r'\1', x) for x in re.findall(r"'(.*?)(?<!\\)',?", aliases)]
        for alias in alias_list:
            if alias == tvshow:
                searchkey = tvdb_id
                return searchkey


def query_tvdb(args):
    """
    connects to thetvdb and query for all Informations
    """
    # pylint: disable-msg=R0912
    tvshow = args.show
    episodename = args.episode

    # Both variables have a minimum length
    if len(tvshow) <= 1:
        e_error("Show name is to short", 1)
    if len(episodename) <= 1 and not args.overallepisodenumber:
        e_error("Episode name is to short", 1)

    # use new pytvdbapi
    db_connection = api.TVDB(__tvdb_apikey__)

    # check for local exception
    tvshow_id = check_exceptions_tvshow(tvshow)
    if tvshow_id:
        logging.debug("Searching for show " + str(tvshow_id))
        show = db_connection.get(tvshow_id, args.language)  # pylint: disable-msg=E1101
    else:
        logging.debug("Searching for show " + str(tvshow))
        dbsearch = db_connection.search(tvshow, args.language)

        # Is the show avaiable
        try:
            show = dbsearch[0]
        except api.error.PytvdbapiError:
            e_error("Series " + tvshow + " not found.", 5)

    if args.seasonnumber and args.episodenumber:
        try:
            results = show[args.seasonnumber][args.episodenumber]
        except api.error.PytvdbapiError:
            e_error("Series " + tvshow + ", " + str(args.seasonnumber) + __delimiter__ + str(args.episodenumber) + " not found.", 5)

    elif args.overallepisodenumber:
        # loop through the episodes to find matching
        for season in show:
            for episode in season:
                if episode.absolute_number == args.overallepisodenumber:
                    results = episode

        try:
            results
        except api.error.PytvdbapiError:
            e_error("Series " + tvshow + ", " + str(args.overallepisodenumber) + " not found.", 5)
    else:
        episodenameclean = s_clean(episodename)

        logging.debug("Searching for episodename " + episodenameclean)

        # loop through the episodes to find matching
        for season in show:
            for episode in season:
                if episode.EpisodeName.lower() == episodenameclean.decode('utf-8').lower():
                    results = episode

        # loop again with fuzzy search, if no result was found
        try:
            results
        except NameError:
            # clean string for fuzzy matching
            episodennamestripped = s_prepare(episodenameclean)

            for season in show:
                for episode in season:
                    fuzzysearch = difflib.SequenceMatcher(None, s_prepare(episode.EpisodeName), episodennamestripped).ratio()
                    if fuzzysearch >= 0.90:
                        logging.debug("Matched Episode with fuzzy ratio of " + str(fuzzysearch))
                        results = episode

        # check if we got results
        try:
            results
        except NameError:
            e_error("Series " + tvshow + "/" + episodenameclean + " not found.", 5)

    return results


def main():
    """
    Main Programm
    """

    # Parse Arguments
    parser = argparse.ArgumentParser(
        description='Options for finding the tvshow information.',
        epilog='All data is provided from http://www.thetvdb.com')
    parser.add_argument('-s', '--show', help='Name of the tv show', required=True)
    parser.add_argument('-e', '--episode', help='Episode Title', required=True)
    parser.add_argument('-sn', '--seasonnumber', help='Season Number', required=False, type=int)
    parser.add_argument('-en', '--episodenumber', help='Episode Number', required=False, type=int)
    parser.add_argument('-oen', '--overallepisodenumber', help='Overall Episode Number (Most time not set at thetvdb)', required=False, type=int)
    parser.add_argument('-lang', '--language', help='Only search for results in this language', required=False, default='en')
    parser.add_argument('-fus', '--forceunderscores', help='Force to use underscores instead of whitespaces', action='store_true')
    parser.add_argument('-v', dest='verbose', action='store_true')
    args = parser.parse_args()

    # Debug Logging of tvdb_api
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig()

    results = query_tvdb(args)

    # Check for correct number of results
    try:
        results
    except NameError:
        e_error("No Matching found.", 5)

    seasno = "%02d" % results.SeasonNumber
    epno = "%02d" % results.EpisodeNumber
    output = "Serien" + __delimiter__ + args.show +  __delimiter__ + seasno +'x'+epno + " - " + results.EpisodeName
    if args.forceunderscores:
        output = output.replace(" ", "_")
    
    output = output.replace(u"ä", "ae")
    output = output.replace(u"Ä", "Ae")
    output = output.replace(u"ü", "ue")
    output = output.replace(u"Ü", "Ue")
    output = output.replace(u"ö", "oe")
    output = output.replace(u"Ö", "Oe")
    output = output.replace(u"ß", "ss")    
    print(output)


if __name__ == "__main__":
    main()
