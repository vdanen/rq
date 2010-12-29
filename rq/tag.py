#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""
import sys, datetime, logging, os, commands
import rq.db
from glob import glob

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
    Tag.showdbstats()    : show database statistics, by optional tag
    """

    def __init__(self, rq_db, rq_type, config):
        self.db     = rq_db
        self.type   = rq_type
        self.config = config


    def list(self):
        """
        Function to show database tags.

        Exits the program when complete.
        """
        logging.debug("in Tag.list()")

        query   = 'SELECT tag, path, tdate FROM tags ORDER BY tag'
        results = self.db.fetch_all(query)
        if results:
            for row in results:
                print 'Tag: %-22sDate Added: %-18s\n  Path: %s\n' % (row['tag'], row['tdate'], row['path'])
        else:
            print 'No tags exist in the database!\n'

        self.db.close()
        sys.exit(0)


    def lookup(self, tag):
        """
        Function to return a diction of information about a tag.

        Tag.lookup(tag):
          tag: the tag name to lookup

        Returns a dictionary (id, path) of the tag if it exists, otherwise returns False.
        """
        logging.debug('in Tag.lookup(%s)' % tag)

        query  = "SELECT t_record, path FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        result = self.db.fetch_all(query)

        if result:
            for row in result:
                return_tag = {'id': row['t_record'], 'path': row['path']}
            return(return_tag)
        else:
            return False


    def add_record(self, tag, path_to_tag):
        """
        Function to add a tag record.

        Tag.add_record(tag, path_to_tag):
          tag        : the tag to add
          path_to_tag: the path for this tag

        Returns the ID of the newly created tag, otherwise returns 0
        """
        logging.debug('in Tag.add_record(%s, %s)' % (tag, path_to_tag))

        cur_date = datetime.datetime.now()
        cur_date = cur_date.strftime('%a %b %d %H:%M:%S %Y')

        if os.path.isfile(path_to_tag):
            path = os.path.abspath(os.path.dirname(path_to_tag))
        else:
            path = os.path.abspath(path_to_tag)
        # we can have multiple similar paths, but not multiple similar tags
        query = "SELECT tag FROM tags WHERE tag = '%s'" % self.db.sanitize_string(tag)
        dbtag = self.db.fetch_one(query)
        if dbtag:
            print 'Tag (%s) already exists in the database!\n' % tag
            sys.exit(1)

        query = "INSERT INTO tags (t_record, tag, path, tdate) VALUES (NULL,'%s', '%s', '%s')" % (
                self.db.sanitize_string(tag.strip()),
                self.db.sanitize_string(path.strip()),
                cur_date)
        self.db.do_query(query)

        query   = "SELECT t_record FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        tag_id  = self.db.fetch_one(query)
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

        tag_id =  self.lookup(tag)

        if not tag_id:
            print 'No matching tag found for entry %s!\n' % tag
            sys.exit(1)
        else:
            print 'Removing tag (%s) from Tags...\n' % tag
            query = "DELETE FROM tags WHERE t_record = '%s'" % tag_id['id']
            self.db.do_query(query)

            query  = "SELECT count(*) FROM packages WHERE t_record = '%s'" % tag_id['id']
            result = self.db.fetch_one(query)
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
                    tables = ('packages', 'requires', 'provides', 'files', 'flags', 'symbols')
                if self.type == 'source':
                    tables = ('packages', 'sources', 'files', 'ctags')

                for table in tables:
                    query = "DELETE FROM %s WHERE t_record = '%s'" % (table, tag_id['id'])
                    self.db.do_query(query)

                sys.stdout.write(' done\n')

                if result > 500:
                    sys.stdout.write('Optimizing database (this may take some time)... ')
                    sys.stdout.flush()
                    for table in tables:
                        query = 'OPTIMIZE TABLE %s' % table
                        self.db.do_query(query)
                    sys.stdout.write(' done\n')
                else:
                    sys.stdout.write('Skipping database optimization, less than 500 package records removed.\n')
            else:
                sys.stdout.write('No matching package tags to remove.\n')


    def update_source_entries(self, rq, tag):
        """
        Function to update entries for a given tag (for rqs)
        """
        logging.debug('in Tag.update_source_entries(%s)' % tag)

        to_remove = []
        to_add    = []
        updates   = 0

        query  = "SELECT DISTINCT path FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        path   = self.db.fetch_one(query)
        query  = "SELECT DISTINCT t_record FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        tag_id = self.db.fetch_one(query)
        query  = "SELECT DISTINCT update_path FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        u_path = self.db.fetch_one(query)

        if not tag_id:
            sys.stdout.write('No Tag entry found for tag: %s\n' % tag)

        if u_path:
            log.info('Using associated updates path: %s' % u_path)
            path    = u_path
            updates = 1

        if updates == 0 and path:
            if not os.path.isdir(path):
                logging.critical('Tag path %s does not exist!' % path)
                sys.exit(1)
            # this handles entries where we don't have a dedicated updates directory
            print 'Checking for removed files in %s tag entries from %s...' % (tag, path)
            # get the existing entries
            query  = "SELECT DISTINCT p_record, p_tag, p_fullname FROM packages WHERE t_record = '%s'" % tag_id
            result = self.db.fetch_all(query)
            for row in result:
                fullname = '%s/%s' % (path, row['p_fullname'])
                if not os.path.isfile(fullname):
                    logging.info('  SRPM missing: %s' % row['p_fullname'])
                    to_remove.append(row['p_record'])

            src_list = glob(path + "/*.rpm")
            src_list.sort()

            print 'Checking for added files in %s tag entries from %s...' % (tag, path)
            for src_rpm in src_list:
                sfname = os.path.basename(src_rpm)
                query  = "SELECT p_package FROM packages WHERE t_record = '%s' AND p_fullname = '%s" % (
                         tag_id,
                         self.db.sanitize_string(sfname))
                package = self.db.fetch_one(query)
                if not package:
                    logging.info('Scheduling %s to be added to database')
                    to_add.append(src_rpm)

        if updates == 1 and u_path:
            # this is an entry with an updates path
            if not os.path.isdir(u_path):
                logging.critical('Tag updates path %s does not exist!' % u_path)
                sys.exit(1)

            # we do not remove files from update paths, just add, unless they were
            # previously noted as an updated file

            src_list = glob(path + "/*.rpm")
            src_list.sort()

            print 'Checking for added files in %s tag entries from %s...' % (tag, path)
            for src_rpm in src_list:
                sfname = os.path.basename(src_rpm)
                query  = "SELECT p_package FROM packages WHERE t_record = '%s' AND p_fullname = '%s" % (
                         tag_id,
                         self.db.sanitize_string(sfname))
                package = self.db.fetch_one(query)
                if not package:
                    # this file does not exist in the database, but it's in the updates
                    # directory. this means it is new, or previously existed and has a new
                    # n-v-r; if it's new we need to just add it, if it has a previous n-v-r
                    # we want to remove the old one and add this one
                    pkgname = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}'" + src_rpm.replace(' ', '\ '))
                    query   = "SELECT p_record FROM packages WHERE t_record = '%s' AND p_package = '%s' AND p_updated = 1" % (
                              tag_id,
                              self.db.sanitize_string(src_rpm))
                    pack    = self.db.fetch_one(query)
                    if pack:
                        logging.info('Found an already-updated record for %s (ID: %d)' % (src_rpm, pack))
                        to_add.append(src_rpm)
                        to_remove.append(pack)
                    else:
                        logging.info('Scheduling %s to be added to database')
                        to_add.append(src_rpm)

        if to_remove:
            r_count = 0
            print 'Removing tagged entries for tag: %s...' % tag
            #if self.type == 'binary':
            #    tables = ('packages', 'requires', 'provides', 'files')
            if self.type == 'source':
                tables = ('packages', 'sources', 'files', 'ctags', 'buildreqs')
            for rnum in to_remove:
                r_count = r_count + 1
                for table in tables:
                    query  = "DELETE FROM %s WHERE p_record = %d" % (table, rnum)
                    print query
                    #result = self.db.do_query(query)
            print 'Removed %d files and associated entries' % r_count

        if to_add:
            a_count = 0
            print 'Adding tagged entries for tag: %s...' % tag
            for rpm in to_add:
                a_count = a_count + 1
                logging.info('Adding: %s' % rpm)
                if self.type == 'binary':
                    print 'Adding binary rpms is not supported yet!'
                    sys.exit(1)
                if self.type == 'source':
                    rq.record_add(tag_id, rpm, 1) # the 1 is to indicate this is an update
                    print 'rq.record.add'
            print 'Added %d files and associated entries' % a_count


    def showdbstats(self, tag = 'all'):
        """
        Function to show database info
        """
        logging.debug("in Tag.showdbstats(%s)" % tag)

        if tag == 'all':
            extra_opts = ''
        else:
            tag_id = self.lookup(tag)
            if tag_id:
                extra_opts = "WHERE t_record = '%d'" % tag_id['id']
            else:
                print 'No such tag: "%s" does not exist in the database!\n' % tag
                sys.exit(1)

        query   = "SELECT count(*) FROM tags %s" % extra_opts
        c_tags  = self.db.fetch_one(query)
        query   = "SELECT count(*) FROM packages %s" % extra_opts
        c_pkgs  = self.db.fetch_one(query)
        if self.type == 'binary':
            query   = "SELECT count(*) FROM requires %s" % extra_opts
            c_reqs  = self.db.fetch_one(query)
            query   = "SELECT count(*) FROM provides %s" % extra_opts
            c_provs = self.db.fetch_one(query)
            query   = "SELECT count(*) FROM flags %s" % extra_opts
            c_flags = self.db.fetch_one(query)
            query   = "SELECT count(*) FROM symbols %s" % extra_opts
            c_symbs = self.db.fetch_one(query)
        else:
            query   = "SELECT count(*) FROM sources %s" % extra_opts
            c_src   = self.db.fetch_one(query)
            query   = "SELECT count(*) FROM ctags %s" % extra_opts
            c_ctags = self.db.fetch_one(query)
            query   = "SELECT count(*) FROM buildreqs %s" % extra_opts
            c_breqs = self.db.fetch_one(query)
        query   = "SELECT count(*) FROM files %s" % extra_opts
        c_files = self.db.fetch_one(query)

        # get the size of the database as well
        size   = 0.00
        btype  = ''
        query  = "SHOW TABLE STATUS"
        tbsize = self.db.fetch_all(query)

        for x in tbsize:
            size += x['Data_length']
        count = 0

        while size > 1024:
            size   = size / 1024
            count += 1
            if count == 1:
                btype = 'KB'
            if count == 2:
                btype = 'MB'
            if count == 3:
                btype = 'GB'
                break

        print 'Database statistics:\n'
        if tag != 'all':
            print 'Printing statistics for tag: %s\n' % tag
        print '   Database  => User: %s, Host: %s, Database: %s' % (
            self.config['username'],
            self.config['hostspec'],
            self.config['database'])
        print '   Data size => %2.2f %s\n' % (size, btype)
        print '   Tag records  : %-16d Package records : %-15d' % (c_tags, c_pkgs)
        if self.type == 'binary':
            print '   File records : %-15d  Requires records: %-15d' % (c_files, c_reqs)
            print '   Flag records : %-15d  Provides records: %-15d' % (c_flags, c_provs)
            print '                                   Symbol records  : %-15d\n' % c_symbs
        else:
            print '   File records : %-15d  Source records  : %-15d' % (c_files, c_src)
            print '   Ctags records: %-15d  Requires records: %-15d '% (c_ctags, c_breqs)
        sys.exit(0)
