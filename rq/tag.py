"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2017 Vincent Danen <vdanen@linsec.ca>

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
"""
import sys
import datetime
import logging
import os
import commands
from glob import glob
from app.models import RPM_Tag, RPM_Package, RPM_Requires, RPM_Provides, RPM_File, RPM_Flags, RPM_Symbols, \
    RPM_AlreadySeen, SRPM_Package, SRPM_Tag, SRPM_BuildRequires, SRPM_Ctag, SRPM_Source, SRPM_File, SRPM_AlreadySeen, \
    rpm_db, srpm_db


class Tag:
    """
    Class to handle tag management.  Init the class with the database connection and the
    type of connection, whether it is binary or source.  This saves us having to pass
    this information as arguments to functions
    """

    def __init__(self, rq_type, config, rcommon, options):
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

        if self.type == 'binary':
            results = RPM_Tag.get_list()
        else:
            results = SRPM_Tag.get_list()

        if results:
            for row in results:
                updated = ''
                c_pkgs  = row.package_count
                c_upd   = row.update_count
                if row.update_date:
                    updated = ' / Updated: %s' % row.update_date
                print 'Tag: %-22sPackages: %-15sUpdates: %s\n  Added: %-18s%s\n  Path       : %s\n  Update Path: %s\n' % (
                    row.tag,
                    c_pkgs,
                    c_upd,
                    row.tdate,
                    updated,
                    row.path,
                    row.update_path
                )

        else:
            print 'No tags exist in the database!\n'

        sys.exit(0)


    def lookup(self, tag):
        """
        Function to return a diction of information about a tag.  Returns a dictionary ({id, path}) of the tag
        if it exists, otherwise returns False.

        :param tag: the tag name to lookup
        :return: dict or False
        """
        logging.debug('in Tag.lookup(%s)' % tag)

        if self.type == 'binary':
            return RPM_Tag.info(tag)
        else:
            return SRPM_Tag.info(tag)


    def add_record(self, tag, path_to_tag, updatepath):
        """
        Add a new tag record to the database.  Returns the ID of the newly created tag, otherwise returns 0

        :param tag: the tag to add
        :param path_to_tag: the path for this tag
        :param updatepath:  the update path for this tag
        :return: int
        """
        logging.debug('in Tag.add_record(%s, %s, %s)' % (tag, path_to_tag, updatepath))

        cur_date = datetime.datetime.now()
        cur_date = cur_date.strftime('%a %b %d %H:%M:%S %Y')

        if os.path.isfile(path_to_tag):
            path = os.path.abspath(os.path.dirname(path_to_tag))
        else:
            path = os.path.abspath(path_to_tag)

        # we can have multiple similar paths, but not multiple similar tags
        if self.type == 'binary':
            dbtag = RPM_Tag.exists(tag)
        else:
            dbtag = SRPM_Tag.exists(tag)

        if dbtag:
            print 'Tag (%s) already exists in the database!\n' % tag
            sys.exit(1)

        try:
            if self.type == 'binary':
                t = RPM_Tag.create(
                    tag         = tag.strip(),
                    path        = path.strip(),
                    update_path = updatepath.strip(),
                    tdate       = cur_date
                )
            else:
                t = SRPM_Tag.create(
                    tag         = tag.strip(),
                    path        = path.strip(),
                    update_path = updatepath.strip(),
                    tdate       = cur_date
                )
            return t.id
        except Exception, e:
            logging.error('Adding tag %s failed!\n%s', tag, e)
            return(0)


    def delete_entries(self, tag):
        """
        Delete database tags and associated entries; optimizes the database if there are a lot of entries
        to remove

        :param tag: the tag to delete
        :return: nothing
        """
        logging.debug('in Tag.delete_entries(%s)' % tag)

        tid = self.lookup(tag)

        if not tid:
            print 'No matching tag found for entry %s!\n' % tag
            sys.exit(1)
        else:
            print 'Removing tag (%s) from Tags...\n' % tag
            if self.type == 'binary':
                t = RPM_Tag.get(RPM_Tag.tag == tag)
            else:
                t = SRPM_Tag.get(SRPM_Tag.tag == tag)
            result = t.package_count

            if result:
                if result == 1:
                    word_package = 'Package'
                    word_entry   = 'entry'
                else:
                    word_package = 'Packages'
                    word_entry   = 'entries'

                sys.stdout.write('Removing %s tagged %s %s for %s... ' % (result, word_package, word_entry, tag))
                sys.stdout.flush()

                if result > 500:
                    self.optimize_db()

                # now delete the tag entry itself
                if self.type == 'binary':
                    RPM_Flags.delete_tags(tid['id'])
                    RPM_Symbols.delete_tags(tid['id'])
                else:
                    print 'deleting sources'
                    SRPM_Ctag.delete_tags(tid['id'])
                    SRPM_File.delete_tags(tid['id'])

                t.delete_instance(recursive=True)

                sys.stdout.write(' done\n')
            else:
                sys.stdout.write('No matching package tags to remove.\n')


    def optimize_db(self):
        """
        Optimize the database
        """
        logging.debug('in Tag.optimize_db()')

        sys.stdout.write('Optimizing database (this may take some time)... ')
        sys.stdout.flush()
        if self.type == 'binary':
            RPM_Flags.optimize()
            RPM_Symbols.optimize()
            RPM_File.optimize()
            RPM_Provides.optimize()
            RPM_Requires.optimize()
            RPM_Package.optimize()
            RPM_Tag.optimize()
            RPM_AlreadySeen.optimize()
        else:
            SRPM_Ctag.optimize()
            SRPM_File.optimize()
            SRPM_Source.optimize()
            SRPM_BuildRequires.optimize()
            SRPM_AlreadySeen.optimize()
            SRPM_Tag.optimize()
            SRPM_Package.optimize()
        sys.stdout.write(' done\n')


    def update_entries(self, rq, tag, listonly=False):
        """
        Update entries for a given tag (for rqs)
        :param rq:
        :param tag:
        :param listonly:
        :return:
        """
        logging.debug('in Tag.update_entries(%s, %s)' % (tag, listonly))

        to_remove = []
        to_add    = []
        have_seen = []
        updates   = 0
        newpkgs   = 0
        the_tag   = None

        if self.type == 'binary':
            pkg_type = 'RPM'
            if RPM_Tag.exists(tag):
                the_tag = RPM_Tag.get(RPM_Tag.tag == tag)
                path    = the_tag.path
                tid     = the_tag.id
                u_path  = the_tag.update_path
        else:
            pkg_type = 'SRPM'
            if SRPM_Tag.exists(tag):
                the_tag = SRPM_Tag.get(SRPM_Tag.tag == tag)
                path    = the_tag.path
                tid     = the_tag.id
                u_path  = the_tag.update_path

        if not the_tag:
            print 'No Tag entry found for tag: %s\n' % tag
            sys.exit(1)

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
            if self.type == 'binary':
                result = RPM_Package.select(RPM_Package.tid == tid)
            else:
                result = SRPM_Package.select(SRPM_Package.tid == tid)
            for row in result:
                fullname = '%s/%s' % (path, row.fullname)
                if not os.path.isfile(fullname):
                    logging.info('  %s missing: %s' % (pkg_type, row.fullname))
                    to_remove.append(row.id)

            src_list = glob(path + "/*.rpm")
            src_list.sort()

            print 'Checking for added files in %s tag entries from %s...' % (tag, path)
            for src_rpm in src_list:
                sfname = os.path.basename(src_rpm)
                if self.type == 'binary':
                    if not RPM_Package.exists(tid, sfname):
                        logging.info('Scheduling %s to be added to database' % src_rpm)
                        to_add.append(src_rpm)
                else:
                    if not SRPM_Package.exists(tid, sfname):
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

                if self.type == 'binary':
                    exists = RPM_Package.exists(tid, sfname)
                else:
                    exists = SRPM_Package.exists(tid, sfname)

                if not exists:
                    # this means we do not have this package currently in the database
                    # so check if we have already seen and removed it
                    if self.type == 'binary':
                        alreadyseen = RPM_AlreadySeen.exists(tid, sfname)
                    else:
                        alreadyseen = SRPM_AlreadySeen.exists(tid, sfname)

                    if not alreadyseen:
                        # this is a new file that does not exist in the database, but it's
                        # in the updates directory and we have not seen it before

                        """
                        # see file, look in packages and alreadyseen, if:
                        #  not in packages, not in alreadyseen: new
                        #  in packages, not in alreadyseen: release package
                        #  in packages, in alreadyseen: should never happen
                        #  not in packages, in alreadyseen: old package
                        # if new, add it, delete old one from packages, add to alreadyseen
                        """

                        # this file is not in our db, so we need to see if this is an updated package
                        rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{ARCH}' " + self.rcommon.clean_shell(src_rpm))
                        tlist   = rpmtags.split('|')
                        logging.debug("tlist is %s " % tlist)
                        r_pkg  = tlist[0].strip()
                        r_arch = tlist[1].strip()
                        if self.type == 'source':
                            result = SRPM_Package.select().where(
                                        (SRPM_Package.tid == tid) &
                                        (SRPM_Package.package == r_pkg))
                        elif self.type == 'binary':
                            # when looking at binaries, we need to include the arch for uniqueness otherwise
                            # we get the first hit, which might be i386 when we're looking at a new i686 pkg
                            result = RPM_Package.select().where(
                                        (RPM_Package.tid == tid) &
                                        (RPM_Package.package == r_pkg) &
                                        (RPM_Package.arch == r_arch))

                        if result:
                            # we have a package record of the same name in the database
                            # this means we need to mark the old package as seen, remove
                            # the old package, and add this new package
                            for package in result:
                                if package.id:
                                    logging.info('Found an already-in-updates record for %s (ID: %d, %s)' % (sfname, package.id, package.fullname))
                                    to_add.append(src_rpm)
                                    if package.id not in to_remove:
                                        to_remove.append(package.id)
                                    logging.debug('Scheduling %s to be added to already-seen list' % package.fullname)
                                    have_seen.append(package.fullname)
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
            sys.stdout.write('\nRemoving tagged entries for tag: %s... ' % tag)
            # if self.type == 'binary':
            #     tables = ('packages', 'requires', 'provides', 'files')
            # if self.type == 'source':
            #     tables = ('packages', 'sources', 'files', 'ctags', 'buildreqs')

            for rnum in to_remove:
                r_count = r_count + 1
                if self.type == 'binary':
                    p = RPM_Package.get(RPM_Package.id == rnum)
                else:
                    p = SRPM_Package.get(SRPM_Package.id == rnum)
                p.delete_instance(recursive=True)

            sys.stdout.write(' done\n')

            if r_count > 100:
                # we could potentially be removing a lot of stuff here, so the package
                # count needs to be set fairly low as we're dropping buildreqs, ctags,
                # etc. so even 10 packages could have a few thousand records all told
                self.optimize_db()

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
                    rq.record_add(tid, a_rpm, 1) # the 1 is to indicate this is an update

        if have_seen and not listonly:
            # make have_seen unique
            hs = []
            for tmp in have_seen:
                if tmp not in hs:
                    hs.append(tmp)
                else:
                    logging.debug('Discarding duplicate entry: %s' % tmp)

            h_count = 0
            for hseen in hs:
                if self.type == 'binary':
                    aseen = RPM_AlreadySeen.exists(tid, sfname)
                else:
                    aseen = SRPM_AlreadySeen.exists(tid, sfname)
                if not aseen:
                    # only add this to the database if we've not seen it
                    # TODO: this should be unnecessary, but seems like we might get dupes otherwise right now
                    h_count = h_count + 1
                    if self.type == 'binary':
                        h = RPM_AlreadySeen.create(
                            fullname = hseen,
                            tid      = tid
                        )
                    else:
                        h = SRPM_AlreadySeen.create(
                            fullname = hseen,
                            tid      = tid
                        )
                    logging.debug('Added %s to alreadyseen table (id: %d)', hseen, h.id)
            logging.debug('Added %d records to alreadyseen table', h_count)

        if not to_add and not to_remove:
            print 'No changes detected.'
        else:
            cur_date = datetime.datetime.now()
            cur_date = cur_date.strftime('%a %b %d %H:%M:%S %Y')
            if self.type == 'binary':
                q = RPM_Tag.update(update_date=cur_date).where(RPM_Tag.id == tid)
            else:
                q = SRPM_Tag.update(update_date=cur_date).where(SRPM_Tag.id == tid)
            q.execute()


    def trim_update_list(self, packagelist, seenlist):
        """
        Function to examine a list of packages scheduled for addition to the
        database and make sure they are unique by only taking the package with
        the highest N-V-R, otherwise we may end up adding multiple copies of the
        same package name, just with different versions
        :param packagelist:
        :param seenlist:
        :return:
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
            if self.type == 'source':
                arch    = 'src'
            else:
                arch    = tlist[4].strip()
            uname   = '%s-%s' % (package, arch)

            # first, add everything we see to the already-seen list; later we'll remove
            # what gets stuffed into our updates list
            seenlist.append(sfname)
            logging.debug('Adding %s to the already-seen list' % sfname)
            try:
                if not templist[uname]:
                    templist[uname] = [version, release, pkg, sfname]
                    logging.debug('Adding %s(%s, %s, %s, %s, %s) to templist' % (package, version, release, pkg, sfname, arch))
                else:
                    bigger = self.nvr_compare(templist[uname], version, release)
                    if bigger == 1:
                        # this one has a higher nvr
                        templist[uname] = [version, release, pkg, sfname]
                        logging.debug('Adding replacement %s(%s, %s, %s, %s, %s) to templist' % (package, version, release, pkg, sfname, arch))
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
        TODO: we can get this from python-rpm and do it better
        Function to compare version and release of two different RPM packages to see which is bigger
        :param oldpkg:
        :param version:
        :param release:
        :return:
        """
        def ncomp(old, new, type):
            logging.debug('comparing %s old:%s and new:%s' % (type, old, new))
            o = old.split('.')
            n = new.split('.')

            # need to make the array lengths the same, but we don't want to use 0's here
            # otherwise 9.1.0 may not be higher than 9.1, which it should be, so use empty
            # values instead to prevent the try statement below failing because o has more
            # elements than n which makes python mad
            len_o = len(o)
            len_n = len(n)
            if len_o > len_n:
                num = len_o - len_n
                x = 0
                while x < num:
                    n.append('')
                    x = x + 1
            elif len_n > len_o:
                num = len_n - len_o
                x = 0
                while x < num:
                    o.append('')
                    x = x + 1

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

        ver_is_bigger = ncomp(oldpkg[0], version, "version")

        if ver_is_bigger == 1:
            return(1)
        elif ver_is_bigger == 2:
            # version is smaller, immediately fail
            return(0)
        else:
            # version is the same so check on release
            rel_is_bigger = ncomp(oldpkg[1], release, "release")
            if rel_is_bigger == 1:
                return(1)

        # if we get here, neither the release nor the version are bigger
        return(0)


    def showdbstats(self, tag=None):
        """
        Show database statistics and info.  This function exits the program when done.

        :param tag: optional tag name to isolate and report on
        :return:
        """
        """
        Function to show database info
        """
        logging.debug("in Tag.showdbstats(%s)" % tag)

        tid = None
        if tag:
            taginfo = self.lookup(tag)
            if taginfo:
                tid = taginfo['id']
            else:
                print 'No such tag: "%s" does not exist in the database!\n' % tag
                sys.exit(1)

        if tid:
            if self.type == 'binary':
                c_tags  = RPM_Tag.select().where(RPM_Tag.id == tid).count()
                c_pkgs  = RPM_Package.select().where(RPM_Package.tid == tid).count()
                c_files = RPM_File.select().where(RPM_File.tid == tid).count()
                c_reqs  = RPM_Requires.select().where(RPM_Requires.tid == tid).count()
                c_provs = RPM_Provides.select().where(RPM_Provides.tid == tid).count()
                c_flags = RPM_Flags.select().where(RPM_Flags.tid == tid).count()
                c_symbs = RPM_Symbols.select().where(RPM_Symbols.tid == tid).count()
            else:
                c_tags  = SRPM_Tag.select().where(SRPM_Tag.id == tid).count()
                c_pkgs  = SRPM_Package.select().where(SRPM_Package.tid == tid).count()
                c_files = SRPM_File.select().where(SRPM_File.tid == tid).count()
                c_src   = SRPM_Source.select().where(SRPM_Tag.id == tid).count()
                c_ctags = SRPM_Ctag.select().where(SRPM_Tag.id == tid).count()
                c_breqs = SRPM_BuildRequires.select().where(SRPM_Tag.id == tid).count()
        else:
            if self.type == 'binary':
                c_tags  = RPM_Tag.select().count()
                c_pkgs  = RPM_Package.select().count()
                c_files = RPM_File.select().count()
                c_reqs  = RPM_Requires.select().count()
                c_provs = RPM_Provides.select().count()
                c_flags = RPM_Flags.select().count()
                c_symbs = RPM_Symbols.select().count()
            else:
                c_tags  = SRPM_Tag.select().count()
                c_pkgs  = SRPM_Package.select().count()
                c_files = SRPM_File.select().count()
                c_src   = SRPM_Source.select().count()
                c_ctags = SRPM_Ctag.select().count()
                c_breqs = SRPM_BuildRequires.select().count()

        # get the size of the database as well
        size   = 0.00
        btype  = ''
        # TODO: use srpm_db if type == source
        if self.type == 'binary':
            db   = rpm_db.database
            user = rpm_db.connect_kwargs['user']
            host = rpm_db.connect_kwargs['host']
        else:
            db   = srpm_db.database
            user = srpm_db.connect_kwargs['user']
            host = srpm_db.connect_kwargs['host']
        query = 'SELECT table_schema "name",  sum( data_length + index_length ) "size" FROM information_schema.TABLES \
                 WHERE table_schema = "%s" GROUP BY table_schema' % db
        tbsize = rpm_db.execute_sql(query)
        for x in tbsize._rows:
            if x[0] == db:
                size = int(x[1])
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
        print '   Database  => User: %s, Host: %s, Database: %s' % (user, host, db)
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
