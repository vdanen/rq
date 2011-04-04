#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2011 Vincent Danen <vdanen@linsec.ca>

This file is part of rq.

rq is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

rq is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with rq.  If not, see <http://www.gnu.org/licenses/>.

$Id$
"""
import MySQLdb, MySQLdb.cursors
import logging
import sys
import re

class DB:
    """
    Class to do database queries
    """

    def __init__(self, type, config):
        """
        function __init__(type, config)

        Initialize connection to the database.  It requires two arguments: type is
        'source' or 'binary' to know which database we are working with and config
        is the database configuration information.  It returns two objects: the db
        object for connecting to the database and a modified config list that has
        the appropriate database name (for whether it is called with type 'source'
        or type 'binary').
        """
        logging.debug('  in DB.__init__(%s, %s)' % (type, config))

        self.db     = ''    # db connection
        self.dbname = ''    # srpm or rpm database name depending on how called

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
                self.dbname = config['rpm_database']

        if type == 'source':
            if (config['srpm_database'] == ''):
                logging.critical('Missing srpm_database in the configuration!')
                sys.exit(1)
            else:
                self.dbname = config['srpm_database']

        logging.debug('Using host=>%s, user=>%s, db=>%s' % (config['hostspec'], config['username'], self.dbname))

        try:
            self.db = MySQLdb.connect(host=config['hostspec'],
                                      user=config['username'],
                                      passwd=config['password'],
                                      db=self.dbname,
                                      cursorclass=MySQLdb.cursors.DictCursor)
        except MySQLdb.Error, e:
            logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
            sys.exit(1)


    def get_dbname(self):
        """
        function DB.get_dbname()

        Function to return the database name we're using depending on if this
        is being called by rqp or rqs
        """
        return (self.dbname)


    def close(self):
        """
        function DB.close()

        Function to close connections to the database
        """
        self.db.commit()
        self.db.close()


    def fetch_all(self, query):
        """
        function DB.fetchall(query)

        Function to perform database queries.  It takes one argument, the query to
        execute (a SELECT statement), and returns the results of the query if the
        query was successful, returns False if not.  This function is meant to be
        used with multi-result queries.
        """
        logging.debug('  in DB.fetch_all()')
        logging.debug('  => query is: %s' % query)

        try:
            cursor = self.db.cursor()
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


    def fetch_one(self, query):
        """
        function DB.fetch_one(query)

        Function to perform database queries.  It takes one argument, the query to
        execute (a SELECT statement), and returns the results of the query if the
        query was successful, returns False if not.  This function is meant to be
        used with single-result queries.
        """
        logging.debug('  in DB.fetch_one()')
        logging.debug('  => query is: %s' % query)

        try:
            cursor  = self.db.cursor()
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


    def do_query(self, query):
        """
        function DB.do_query(query)

        Function to perform an actual update (UPDATE/INSERT) query (non-SELECT) from the database
        """
        logging.debug('  in DB.do_query()')
        logging.debug('  => query is: %s' % query)

        try:
            cursor = self.db.cursor()
            cursor.execute(query)
            cursor.close()
        except MySQLdb.Error, e:
            logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
            sys.exit(1)


    def do_transactions(self, queries):
        """
        function DB.do_transcation(queries)

        Function to a set of non-sequential transactions (usually DELETES) from the database
        """
        logging.debug('  in DB.do_transaction()')

        if not queries:
            logging.critical('Received empty set of queries: nothing to do!')
            sys.exit(1)

        try:
            cursor = self.db.cursor()
            cursor.execute("set autocommit=0")
            cursor.execute("START TRANSACTION")
        except MySQLdb.Error, e:
            logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
            sys.exit(1)

        for query in queries:
            logging.debug('  => query is: %s' % query)
            try:
                cursor.execute(query)
            except MySQLdb.Error, e:
                logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
                sys.exit(1)

        try:
            self.db.commit()
            cursor.close()
        except MySQLdb.Error, e:
            logging.critical('MySQL error %d: %s' % (e.args[0], e.args[1]))
            logging.critical('Rolling back the transaction!')
            cursor.rollback()
            sys.exit(1)


    def sanitize_string(self, string):
        """
        function DB.sanitize_string(string)

        String to cleanup a string to remove characters that will cause problems
        with the database
        """
        #logging.debug('  in DB.sanitize_string(%s)' % string)

        if string:
            # escape single and double quotes
            new_string = re.sub('''(['";\\\])''', r'\\\1', string)
        else:
            new_string = None

        return(new_string)
