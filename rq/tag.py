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

    def __init__(self, rq_db, rq_type, config, rcommon, options):
        self.db      = rq_db
        self.type    = rq_type
        self.config  = config
        self.rcommon = rcommon
        self.options = options

    def list(self):
        """
        Function to show database tags.

        Exits the program when complete.
        """
        logging.debug("in Tag.list()")

        query   = 'SELECT t_record, tag, path, update_path, tdate FROM tags ORDER BY tag'
        results = self.db.fetch_all(query)
        if results:
            for row in results:
                query2  = "SELECT count(*) FROM packages WHERE t_record = %s" % row['t_record']
                c_pkgs  = self.db.fetch_one(query2)
                query2  = "SELECT count(*) FROM packages WHERE t_record = %s AND p_update = 1" % row['t_record']
                c_upd   = self.db.fetch_one(query2)
                print 'Tag: %-22sDate Added: %-18s\n  Path       : %s\n  Update Path: %s\n  Packages: %-15sUpdates: %s\n' % (row['tag'], row['tdate'], row['path'], row['update_path'], c_pkgs, c_upd)

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


    def add_record(self, tag, path_to_tag, updatepath):
        """
        Function to add a tag record.

        Tag.add_record(tag, path_to_tag):
          tag        : the tag to add
          path_to_tag: the path for this tag
          updatepath : the updates path for this tag

        Returns the ID of the newly created tag, otherwise returns 0
        """
        logging.debug('in Tag.add_record(%s, %s, %s)' % (tag, path_to_tag, updatepath))

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

        query = "INSERT INTO tags (t_record, tag, path, update_path, tdate) VALUES (NULL,'%s', '%s', '%s', '%s')" % (
                self.db.sanitize_string(tag.strip()),
                self.db.sanitize_string(path.strip()),
                self.db.sanitize_string(updatepath.strip()),
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
                    tables = ('packages', 'requires', 'provides', 'files', 'flags', 'symbols', 'alreadyseen')
                if self.type == 'source':
                    tables = ('packages', 'sources', 'files', 'ctags', 'alreadyseen')

                for table in tables:
                    query = "DELETE FROM %s WHERE t_record = '%s'" % (table, tag_id['id'])
                    self.db.do_query(query)

                sys.stdout.write(' done\n')

                if result > 500:
                    self.optimize_db(tables)
            else:
                sys.stdout.write('No matching package tags to remove.\n')


    def optimize_db(self, tables):
        """
        Function to optimize the database
        """
        logging.debug('in Tag.optimize_db()')

        sys.stdout.write('Optimizing database (this may take some time)... ')
        sys.stdout.flush()
        for table in tables:
            query = 'OPTIMIZE TABLE %s' % table
            self.db.do_query(query)
        sys.stdout.write(' done\n')


    def update_entries(self, rq, tag, listonly=False):
        """
        Function to update entries for a given tag (for rqs)
        """
        logging.debug('in Tag.update_entries(%s, %s)' % (tag, listonly))

        to_remove = []
        to_add    = []
        have_seen = []
        updates   = 0
        newpkgs   = 0

        if self.type == 'source':
            pkg_type = 'SRPM'
        elif self.type == 'binary':
            pkg_type = 'RPM'

        query  = "SELECT DISTINCT path FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        path   = self.db.fetch_one(query)
        query  = "SELECT DISTINCT t_record FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        tag_id = self.db.fetch_one(query)
        query  = "SELECT DISTINCT update_path FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        u_path = self.db.fetch_one(query)

        if not tag_id:
            sys.stdout.write('No Tag entry found for tag: %s\n' % tag)

        if u_path:
            logging.info('Using associated updates path: %s' % u_path)
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
                    logging.info('  %s missing: %s' % (pkg_type, row['p_fullname']))
                    to_remove.append(row['p_record'])

            src_list = glob(path + "/*.rpm")
            src_list.sort()

            print 'Checking for added files in %s tag entries from %s...' % (tag, path)
            for src_rpm in src_list:
                sfname = os.path.basename(src_rpm)
                query  = "SELECT p_package FROM packages WHERE t_record = '%s' AND p_fullname = '%s'" % (
                         tag_id,
                         self.db.sanitize_string(sfname))
                package = self.db.fetch_one(query)
                if not package:
                    logging.info('Scheduling %s to be added to database' % src_rpm)
                    to_add.append(src_rpm)

        if updates == 1 and u_path:
            # this is an entry with an updates path
            if not os.path.isdir(u_path):
                logging.critical('Tag updates path %s does not exist!' % u_path)
                sys.exit(1)

            src_list = glob(path + "/*.rpm")
            src_list.sort()

            print 'Checking for added files in %s tag entries from %s...' % (tag, path)
            for src_rpm in src_list:
                sfname = os.path.basename(src_rpm)
                query  = "SELECT p_record FROM packages WHERE t_record = '%s' AND p_fullname = '%s'" % (
                         tag_id,
                         self.db.sanitize_string(sfname))
                package = self.db.fetch_one(query)
                if not package:
                    # this means we do not have this package currently in the database
                    # so check if we have already seen and removed it
                    query = "SELECT a_record FROM alreadyseen WHERE p_fullname = '%s'" % self.db.sanitize_string(sfname)
                    seen  = self.db.fetch_one(query)
                    if not seen:
                        # this is a new file that does not exist in the database, but it's
                        # in the updates directory and we have not seen it before

# see file, look in packages and alreadyseen, if:
#  not in packages, not in alreadyseen: new
#  in packgaes, not in alreadyseen: release package
#  in packages, in alreadyseen: should never happen
#  not in packages, in alreadyseen: old package
# if new, add it, delete old one from packages, add to alreadyseen

                        # this file is not in our db, so we need to see if this is an updated package
                        rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{ARCH}' " + self.rcommon.clean_shell(src_rpm))
                        tlist   = rpmtags.split('|')
                        logging.debug("tlist is %s " % tlist)
                        r_pkg  = tlist[0].strip()
                        r_arch = tlist[1].strip()
                        if self.type == 'source':
                            query   = "SELECT p_record, p_fullname FROM packages WHERE t_record = '%s' AND p_package = '%s' LIMIT 1" % (
                                      tag_id,
                                      self.db.sanitize_string(r_pkg))
                        elif self.type == 'binary':
                            # when looking at binaries, we need to include the arch for uniqueness otherwise
                            # we get the first hit, which might be i386 when we're looking at a new i686 pkg
                            query   = "SELECT p_record, p_fullname FROM packages WHERE t_record = '%s' AND p_package = '%s' AND p_arch = '%s' LIMIT 1" % (
                                      tag_id,
                                      self.db.sanitize_string(r_pkg),
                                      self.db.sanitize_string(r_arch))
                        result  = self.db.fetch_all(query)

                        if result:
                            # we have a package record of the same name in the database
                            # this means we need to mark the old package as seen, remove
                            # the old package, and add this new package
                            for row in result:
                                if row['p_record']:
                                    logging.info('Found an already-in-updates record for %s (ID: %d, %s)' % (sfname, row['p_record'], row['p_fullname']))
                                    to_add.append(src_rpm)
                                    if row['p_record'] not in to_remove:
                                        to_remove.append(row['p_record'])
                                    logging.debug('Scheduling %s to be added to already-seen list' % row['p_fullname'])
                                    have_seen.append(row['p_fullname'])
                        else:
                            # we do NOT have a matching package record of the same name
                            # that makes this a new package to add, and there is nothing
                            # to remove
                            logging.debug('New package found: %s' % src_rpm)
                            self.rcommon.show_progress()
                            newpkgs = newpkgs + 1
                            to_add.append(src_rpm)
                    else:
                        logging.debug('We have already seen %s' % sfname)

        # here we need to weed out any extras; in the case of first updating
        # an updates directory with multiple similar packages (e.g multiple
        # seamonkey packages) we only want the latest version
        (to_add, have_seen) = self.trim_update_list(to_add, have_seen)

        if to_remove:
            if listonly:
                removetext = ", would remove %d packages" % len(to_remove)
            else:
                removetext = ", removing %d packages" % len(to_remove)
        else:
            removetext = ''

        if to_add:
            existing = len(to_add) - newpkgs
            if listonly:
                print 'Would update %d packages, would add %d new packages%s (%d total potential updates)' % (existing, newpkgs, removetext, len(to_add))
            else:
                print 'Updating %d packages, adding %d new packages%s (%d total updates)' % (existing, newpkgs, removetext, len(to_add))

        r_count = 0
        if to_remove and not listonly:
            queries =[]
            sys.stdout.write('\nRemoving tagged entries for tag: %s... ' % tag)
            if self.type == 'binary':
                tables = ('packages', 'requires', 'provides', 'files')
            if self.type == 'source':
                tables = ('packages', 'sources', 'files', 'ctags', 'buildreqs')

            for rnum in to_remove:
                r_count = r_count + 1
                for table in tables:
                    query  = "DELETE FROM %s WHERE p_record = %d" % (table, rnum)
                    queries.append(query)
                    #result = self.db.do_query(query)
                    #self.rcommon.show_progress()
                # TODO: see if this makes things faster; it might for a full db
                #query  = "DELETE FROM %s USING %s INNER JOIN temptable ON %s.p_record = temptable.p_record WHERE p_record = %d" % (table, table, table, rnum)
                #result = self.db.do_query(query)
                #self.rcommon.show_progress()
                #queries.append(query)
            result = self.db.do_transactions(queries)
            sys.stdout.write(' done\n')

            if r_count > 100:
                # we could potentially be removing a lot of stuff here, so the package
                # count needs to be set fairly low as we're dropping buildreqs, ctags,
                # etc. so even 10 packages could have a few thousand records all told
                self.optimize_db(tables)

        if have_seen and not listonly:
            h_count = 0
            for hseen in have_seen:
                query  = "SELECT a_record FROM alreadyseen WHERE p_fullname = '%s' AND t_record = %d LIMIT 1" % (self.db.sanitize_string(sfname), tag_id)
                exists = self.db.fetch_one(query)
                if not exists:
                    # only add this to the database if we've not seen it
                    # TODO: this should be unnecessary, but seems like we might get dupes otherwise right now
                    h_count = h_count + 1
                    query   = "INSERT INTO alreadyseen (p_fullname, t_record) VALUES ('%s', '%s')" % (hseen, tag_id)
                    result  = self.db.do_query(query)
                    logging.debug('Added %d records to alreadyseen table' % h_count)

        if to_add:
            if listonly:
                print 'Would add the following tagged entries for tag: %s\n' % tag
            else:
                print 'Adding tagged entries for tag: %s:' % tag
            for a_rpm in to_add:
                if listonly:
                    print '%s' % a_rpm
                else:
                    logging.info('Adding: %s' % a_rpm)
                    rq.record_add(tag_id, a_rpm, 1) # the 1 is to indicate this is an update

        if not to_add and not to_remove:
            print 'No changes detected.'
        else:
            cur_date = datetime.datetime.now()
            cur_date = cur_date.strftime('%a %b %d %H:%M:%S %Y')
            query    = "UPDATE tags SET update_date = '%s' WHERE t_record = '%s'" % (cur_date, tag_id)
            result   = self.db.do_query(query)


    def trim_update_list(self, packagelist, seenlist):
        """
        Function to examine a list of packages scheduled for addition to the
        database and make sure they are unique by only taking the package with
        the highest N-V-R, otherwise we may end up adding multiple copies of the
        same package name, just with different versions
        """
        logging.debug("in Tag.trim_update_list(%s, %s)" % (packagelist, seenlist))

        templist = {}
        newlist  = []
        new_seen = []

        for pkg in packagelist:
            sfname  = os.path.basename(pkg)
            rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{BUILDTIME}|%{ARCH}' " + self.rcommon.clean_shell(pkg))
            tlist   = rpmtags.split('|')
            logging.debug("tlist is %s " % tlist)
            package = tlist[0].strip()
            version = tlist[1].strip()
            release = tlist[2].strip()
            pdate   = tlist[3].strip()
            arch    = tlist[4].strip()
            uname   = '%s-%s' % (package, arch)

            # first, add everything we see to the already-seen list; later we'll remove
            # what gets stuffed into our updates list
            seenlist.append(sfname)
            logging.debug('Adding %s to the already-seen list' % sfname)
            try:
                if not templist[uname]:
                    templist[uname] = [version, release, pkg, sfname]
                    logging.debug('Adding %s(%s, %s, %s, %s) to templist' % (package, version, release, pkg, sfname))
                else:
                    bigger = self.nvr_compare(templist[uname], version, release)
                    if bigger == 1:
                        # this one has a higher nvr
                        templist[uname] = [version, release, pkg, sfname]
                        logging.debug('Adding replacement %s(%s, %s, %s, %s) to templist' % (package, version, release, pkg, sfname))
            except:
                templist[uname] = [version, release, pkg, sfname]
                logging.debug('Adding %s(%s, %s, %s, %s) to templist' % (package, version, release, pkg, sfname))

        # reconstruct the old list to return, less what we don't want
        ns = []
        for pkg in templist:
            newlist.append(templist[pkg][2])
            ns.append(templist[pkg][3])

        # reconstruct the new_seen list so it does not contain what is in newlist
        for pkg in seenlist:
            if not pkg in ns:
                # we want to remove all packages from the seenlist that are also
                # in the newlist
                new_seen.append(pkg)
            else:
                logging.debug("Removing %s from the already-seen list; it's in the new package list" % pkg)

        newlist.sort()
        new_seen.sort()
        return(newlist, new_seen)


    def nvr_compare(self, oldpkg, version, release):
        """
        Function to compare version and release of two
        different RPM packages to see which is bigger
        """
        def ncomp(old, new):
            #print 'comparing old:%s and new:%s' % (old, new)
            o = old.split('.')
            n = new.split('.')
            c = 0
            b = 0
            while c < len(o):
                try:
                    # first try comparing numerically, as by strings 3 > 15
                    # which we don't want -- this is pretty simplistic though
                    # as if we get 3a vs 15b we're hooped
                    if int(n[c]) < int(o[c]):
                        # immediately fail if smaller
                        return(2)
                    elif int(n[c]) > int(o[c]):
                        b = 1
                        c = c + 1
                        break
                except:
                    # if that fails, compare as strings and hope for the best
                    if n[c] < o[c]:
                        # immediately fail if smaller
                        return(2)
                    if n[c] > o[c]:
                        b = 1
                        c = c + 1
                        break
                c = c + 1

            return(b)

        ver_is_bigger = ncomp(oldpkg[0], version)

        if ver_is_bigger == 1:
            return(1)
        elif ver_is_bigger == 2:
            # version is smaller, immediately fail
            return(0)
        else:
            # version is the same so check on release
            rel_is_bigger = ncomp(oldpkg[1], release)
            if rel_is_bigger == 1:
                return(1)

        # if we get here, neither the release nor the version are bigger
        return(0)


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
