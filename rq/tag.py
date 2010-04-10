#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""
import sys, datetime, logging, os
import rq.db

class Tag:
    """
    Class to handle tag management.  Init the class with the database connection and the
    type of connection, whether it is binary or source.  This saves us having to pass
    this information as arguments to functions

    Tag.list()           : show database tags
    Tag.lookup()         : returns a dictionary of tag information
    Tag.add_record()     : ads a new tag to the db
    Tag.deleted_entries(): deletes a tag and associated db entries
    Tag.update_entries() : updates entries based on tag <-- this function doesn't work yet
    """

    def __init__(self, db, rq_type):
        self.db   = db
        self.type = rq_type


    def list(self):
        """
        Function to show database tags.

        Exits the program when complete.
        """
        logging.debug("in Tag.list()")

        query   = 'SELECT tag, path, tdate FROM tags ORDER BY tag'
        results = rq.db.fetch_all(self.db, query)
        if results:
            for row in results:
                print 'Tag: %-22sDate Added: %-18s\n  Path: %s\n' % (row['tag'], row['tdate'], row['path'])
        else:
            print 'No tags exist in the database!\n'

        rq.db.close(self.db)
        sys.exit(0)


    def lookup(self, tag):
        """
        Function to return a diction of information about a tag.

        Tag.lookup_id(tag):
          tag: the tag name to lookup

        Returns a dictionary (id, path) of the tag if it exists, otherwise returns False.
        """
        logging.debug('in Tag.lookup(%s)' % tag)

        query  = "SELECT t_record, path FROM tags WHERE tag = '%s' LIMIT 1" % rq.db.sanitize_string(tag)
        result = rq.db.fetch_all(self.db, query)

        if result:
            for row in result:
                return_tag = {'id': row['t_record'], 'path': row['path']}
            return(return_tag)
        else:
            return False


    def add_record(self, tag, file):
        """
        Function to add a tag record.

        Tag.add_record(tag, file):
          tag : the tag to add
          file: the path for this tag

        Returns the ID of the newly created tag, otherwise returns 0
        """
        logging.debug('in Tag.add_record(%s, %s)' % (tag, file))

        cur_date = datetime.datetime.now()
        cur_date = cur_date.strftime('%a %b %d %H:%M:%S %Y')

        if os.path.isfile(file):
            path = os.path.abspath(os.path.dirname(file))
        else:
            path = os.path.abspath(file)
        # we can have multiple similar paths, but not multiple similar tags
        query = "SELECT tag FROM tags WHERE tag = '%s'" % rq.db.sanitize_string(tag)
        dbtag = rq.db.fetch_one(self.db, query)
        if dbtag:
            print 'Tag (%s) already exists in the database!\n' % tag
            sys.exit(1)

        query = "INSERT INTO tags (t_record, tag, path, tdate) VALUES (NULL,'%s', '%s', '%s')" % (rq.db.sanitize_string(tag.strip()), rq.db.sanitize_string(path.strip()), cur_date)
        rq.db.do_query(self.db, query)

        query   = "SELECT t_record FROM tags WHERE tag = '%s' LIMIT 1" % rq.db.sanitize_string(tag)
        tag_id  = rq.db.fetch_one(self.db, query)
        if tag_id:
            return(tag_id)
        else:
            return(0)


    def delete_entries(self, tag):
        """
        Function to delete database tags and associated entries

        Tag.delete_entries(tag):
          tag : the tag to check

        Returns nothing.
        """
        logging.debug('in Tag.delete_entries(%s)' % tag)

        tag_id =  self.lookup_id(tag)

        if not tag_id:
            print 'No matching tag found for entry %s!\n' % tag
            sys.exit(1)
        else:
            print 'Removing tag (%s) from Tags...\n' % tag
            query = "DELETE FROM tags WHERE t_record = '%s'" % tag_id
            rq.db.do_query(self.db, query)

            query  = "SELECT count(*) FROM packages WHERE t_record = '%s'" % tag_id
            result = rq.db.fetch_one(self.db, query)
            if result:
                if result == 1:
                    word_package = 'Package'
                    word_entry   = 'entry'
                else:
                    word_package = 'Packages'
                    word_entry   = 'entries'

                sys.stdout.write('Removing %s tagged %s %s for %s... ' % (result, word_package, word_entry, tag))
                sys.stdout.flush()

                if self.type == 'binary':
                    tables = ('packages', 'requires', 'provides', 'files')
                if self.type == 'source':
                    tables = ('packages', 'sources', 'files', 'ctags')

                for table in tables:
                    query = "DELETE FROM %s WHERE t_record = '%s'" % (table, tag_id)
                    res   = rq.db.do_query(self.db, query)

                sys.stdout.write(' done\n')

                if result > 500:
                    sys.stdout.write('Optimizing database (this may take some time)... ')
                    sys.stdout.flush()
                    for table in tables:
                        query = 'OPTIMIZE TABLE %s' % table
                        res   = rq.db.do_query(self.db, query)
                    sys.stdout.write(' done\n')
                else:
                    sys.stdout.write('Skipping database optimization, less than 500 package records removed.\n')
            else:
                sys.stdout.write('No matching package tags to remove.\n')


    def update_entries(self, tag):
        """
        Function to update entries for a given tag

        This is an incomplete function
        """
        logging.debug('in Tag.update_entries(%s)' % tag)
        #
        # this function is designed for src.rpm handling, but we can update it for binary rpm handling too
        # XXX: TODO
        #

        to_remove = []
        to_add    = []

        query  = "SELECT DISTINCT path FROM tags WHERE tag = '%s' LIMIT 1" % rq.db.sanitize_string(tag)
        path   = rq.db.fetch_one(self.db, query)
        query  = "SELECT DISTINCT t_record FROM tags WHERE tag = '%s' LIMIT 1" % rq.db.sanitize_string(tag)
        tag_id = rq.db.fetch_one(self.db, query)

        if path:
            logging.info('Update tag (%s) entries from %s...' % (tag, path))
            # get the existing entries
            query  = "SELECT DISTINCT p_record, p_tag, p_package, p_version, p_release FROM packages WHERE t_record = '%s'" % tag_id
            result = rq.db.fetch_all(self.db, query)
            for row in result:
                pname = '%s-%s-%s.src.rpm' % (row['p_package'], row['p_version'], row['p_release'])
                logging.info('Checking for %s in %s...' % (pname, path))
                if os.path.isfile(pname):
                    logging.info('OK')
                else:
                    logging.info('Missing')
                    to_remove.append(result['p_record'])

            src_list = glob(path + "/*.rpm")
            src_list.sort()

            for src_rpm in src_list:
                logging.info('Checking for %s in database...' % src_rpm)
                rtags   = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{VERSION}|%{RELEASE}' " + src_rpm.replace(' ', '\ '))
                tlist   = rtags.split('|')
                package = tlist[0].strip()
                version = tlist[1].strip()
                release = tlist[2].strip()

                query   = "SELECT p_package FROM packages WHERE t_record = '%s' AND p_package = '%s' AND p_version = '%s' AND p_release = '%s'" % (tag_id, rq.db.sanitize_string(package), rq.db.sanitize_string(version), rq.db.sanitize_string(release))
                package = rq.db.fetch_one(self.db, query)
                if package:
                    logging.info('OK')
                else:
                    logging.info('Adding')
                    to_add.append(src_rpm)
        else:
            sys.stdout.write('No Tag entry found for tag: %s\n' % tag)

        if to_remove:
            logging.info('Removing tagged entries for tag: %s...' % tag)
            if self.type == 'binary':
                tables = ('packages', 'requires', 'provides', 'files')
            if self.type == 'source':
                tables = ('packages', 'sources')
            for rnum in to_remove:
                for table in tables:
                    query  = "DELETE FROM %s WHERE p_record = %d" % (table, rnum)
                    result = rq.db.do_query(self.db, query)

        if to_add:
            logging.info('Adding tagged entries for tag: %s...' % tag)
            for rpm in to_add:
                ### this will have to come from another module XXX TODO XXX
                record_add(tag_id, rpm, self.type)
