#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""
import MySQLdb, MySQLdb.cursors
import logging
import sys
import re

def connect(type, config):
    """
    function connect(type, config)

    Function to connect to the database.  It requires two arguments: type is
    'source' or 'binary' to know which database we are working with and config
    is the database configuration information.  It returns two objects: the db
    object for connecting to the database and a modified config list that has
    the appropriate database name (for whether it is called with type 'source'
    or type 'binary').
    """

    if config['hostspec'] == '':
        logging.critical('Missing hostspec in the configuration!')
        sys.exit(1)
    if config['username'] == '':
        logging.critical('Missing username in the configuration!')
        sys.exit(1)
    if config['password'] == '':
        logging.critical('Missing password in the configuration!')
        sys.exit(1)

    if type == 'binary':
        if (config['rpm_database'] == ''):
            logging.critical('Missing rpm_database in the configuration!')
            sys.exit(1)
        else:
            config['database'] = config['rpm_database']

    if type == 'source':
        if (config['srpm_database'] == ''):
            logging.critical('Missing srpm_database in the configuration!')
            sys.exit(1)
        else:
            config['database'] = config['srpm_database']

    logging.debug('Using host=>%s, user=>%s, db=>%s' % (config['hostspec'], config['username'], config['database']))

    try:
        db = MySQLdb.connect(host=config['hostspec'],
                             user=config['username'],
                             passwd=config['password'],
                             db=config['database'],
                             cursorclass=MySQLdb.cursors.DictCursor)
    except MySQLdb.Error, e:
        logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
        sys.exit(1)

    return (db, config)


def close(db):
    """
    function close()

    Function to close connections to the database
    """
    db.commit()
    db.close()


def fetch_all(db, query):
    """
    function db_fetchall(query)

    Function to perform database queries.  It takes one argument, the query to
    execute (a SELECT statement), and returns the results of the query if the
    query was successful, returns False if not.  This function is meant to be
    used with multi-result queries.
    """
    logging.debug('  in fetch_all()')
    logging.debug('  => query is: %s' % query)

    try:
        cursor = db.cursor()
        cursor.execute("set autocommit=0")
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()

        if results:
            return results
        else:
            return False
    except MySQLdb.Error, e:
        logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
        sys.exit(1)


def fetch_one(db, query):
    """
    function fetch_one(query)

    Function to perform database queries.  It takes one argument, the query to
    execute (a SELECT statement), and returns the results of the query if the
    query was successful, returns False if not.  This function is meant to be
    used with single-result queries.
    """
    logging.debug('  in fetch_one()')
    logging.debug('  => query is: %s' % query)

    try:
        cursor  = db.cursor()
        cursor.execute(query)
        results = cursor.fetchone()
        cursor.close()
        if results:
            key = results.keys()
            return(results[key[0]])
        else:
            return False
    except MySQLdb.Error, e:
        logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
        sys.exit(1)


def do_query(db, query):
    """
    Function to perform an actual update (UPDATE/INSERT) query (non-SELECT) from the database
    """
    logging.debug('  in do_query()')
    logging.debug('  => query is: %s' % query)

    try:
        cursor = db.cursor()
        cursor.execute(query)
        cursor.close()
    except MySQLdb.Error, e:
        logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
        sys.exit(1)


def sanitize_string(string):
    """
    String to cleanup a string to remove characters that will cause problems
    with the database
    """
    #logging.debug('  in sanitize_string(%s)' % string)
    if string:
        # escape single and double quotes
        new_string = re.sub('''(['";\\\])''', r'\\\1', string)
    else:
        new_string = None
    return(new_string)
