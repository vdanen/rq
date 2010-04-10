#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""
import os, sys, re, commands, logging, tempfile, shutil
from glob import glob
import rq.db
import rq.basics

class Binary:
    """
    Class to handle working with source files
    """

    def __init__(self, db, config, options, rtag, rcommon):
        self.db      = db
        self.config  = config
        self.options = options
        self.rtag    = rtag
        self.rcommon = rcommon

        self.re_brpm    = re.compile(r'\.rpm$')
        self.re_srpm    = re.compile(r'\.src\.rpm$')
        self.re_patch   = re.compile(r'\.(diff|dif|patch)(\.bz2|\.gz)?$')
        self.re_tar     = re.compile(r'\.((tar)(\.bz2|\.gz)?|t(gz|bz2?))$')
        self.re_targz   = re.compile(r'\.(tgz|tar\.gz)$')
        self.re_tarbz   = re.compile(r'\.(tbz2?|tar\.bz2)$')
        self.re_patchgz = re.compile(r'\.(patch|diff|dif)(\.gz)$')
        self.re_patchbz = re.compile(r'\.(patch|diff|dif)(\.bz2)$')


    def rpm_add_directory(self, tag, path):
        """
        Function to import a directory full of RPMs
        """
        logging.debug('in Binary.rpm_add_directory(%s, %s)' % (tag, path))

        if not os.path.isdir(path):
            print 'Path (%s) is not a valid directory!' % path
            sys.exit(1)

        file_list = glob(path + "/*.rpm")
        file_list.sort()

        if not file_list:
            print 'No files found to import in directory: %s' % path
            sys.exit(1)

        tag_id = self.rtag.add_record(tag, path)
        if tag_id == 0:
            logging.critical('Unable to add tag "%s" to the database!' % tag)
            sys.exit(1)

        for file in file_list:
            if not os.path.isfile(file):
                print 'File %s not found!\n' % file
                next

            if not self.re_brpm.search(file) or self.re_srpm.search(file):
                print 'File %s is not a binary rpm!\n' % file
                next

            self.record_add(tag_id, file)


    def record_add(self, tag_id, file):
        """
        Function to add a record to the database
        """
        logging.debug('in Binary.record_add(%s, %s)' % (tag_id, file))

        if os.path.isfile(file):
            path = os.path.abspath(os.path.dirname(file))
        else:
            path = os.path.abspath(file)
        logging.debug('Path:\t%s' % path)

        rq.basics.file_rpm_check(file, type)

        record = self.package_add_record(tag_id, file)
        if not record:
            return

        file_list = rq.basics.rpm_list(file)
        if not file_list:
            return

        logging.debug('Add file records for package record: %s' % record)
        self.add_records(tag_id, record, file_list)
        self.add_requires(tag_id, record, file)
        self.add_provides(tag_id, record, file)

        if self.options.progress:
            sys.stdout.write('\n')


    def package_add_record(self, tag_id, file):
        """
        Function to add a package record
        """
        logging.debug('in Binary.package_add_record(%s, %s)' % (tag_id, file))

        path    = os.path.basename(file)
        rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{BUILDTIME}|%{ARCH}' " + file.replace(' ', '\ '))
        tlist   = rpmtags.split('|')
        logging.debug("tlist is %s " % tlist)
        package = tlist[0].strip()
        version = tlist[1].strip()
        release = tlist[2].strip()
        pdate   = tlist[3].strip()
        arch    = tlist[4].strip()

        query = "SELECT tag FROM tags WHERE t_record = '%s' LIMIT 1" % tag_id
        tag   = self.db.fetch_one(query)

        query = "SELECT t_record, p_package, p_version, p_release, p_arch FROM packages WHERE t_record = '%s' AND p_package = '%s' AND p_version = '%s' AND p_release = '%s' AND p_arch = '%s'" % (
            tag_id,
            self.db.sanitize_string(package),
            self.db.sanitize_string(version),
            self.db.sanitize_string(release),
            self.db.sanitize_string(arch))
        result = self.db.fetch_all(query)

        if result:
            print 'File %s-%s-%s.%s is already in the database under tag %s' % (package, version, release, arch, tag)
            return(0)

        ## TODO: we shouldn't have to have p_tag here as t_record has the same info, but it
        ## sure makes it easier to sort alphabetically and I'm too lazy for the JOINs right now

        query  = "INSERT INTO packages (t_record, p_tag, p_package, p_version, p_release, p_date, p_arch) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (
            tag_id,
            self.db.sanitize_string(tag),
            self.db.sanitize_string(package),
            self.db.sanitize_string(version),
            self.db.sanitize_string(release),
            self.db.sanitize_string(pdate),
            self.db.sanitize_string(arch))

        result = self.db.do_query(query)
        self.rcommon.show_progress(path)

        query    = "SELECT p_record FROM packages WHERE t_record = '%s' AND p_package = '%s' ORDER BY p_record DESC" % (tag_id, self.db.sanitize_string(package))
        p_record = self.db.fetch_one(query)
        if p_record:
                return(p_record)
        else:
            print 'Adding file %s failed!\n' % file
            return(0)


    def query(self, type):
        """
        Function to run the query for binary RPMs
        """
        logging.debug('in Binary.query(%s)' % type)

        tag_id = self.rtag.lookup(self.options.tag)
        if self.options.tag and not tag_id:
            print 'Tag %s is not a known tag!\n' % self.options.tag
            sys.exit(1)
        elif self.options.tag and tag_id:
            tag_id =  tag_id['id']

        if not self.options.quiet:
            print 'Searching database records for substring match for %s (%s)' % (type, self.options.query)

        if self.options.ignorecase:
            ignorecase = ''
        else:
            ignorecase = 'BINARY'

        if type == 'files':
            query = "SELECT DISTINCT p_tag, p_package, p_version, p_release, p_date, %s, f_user, f_group, f_is_suid, f_is_sgid, f_perms FROM %s LEFT JOIN packages ON (packages.p_record = %s.p_record) WHERE %s %s " % (
                type, type, type, ignorecase, type)
        else:
            # query on type: provides, requires, symbols
            query = "SELECT DISTINCT p_tag, p_package, p_version, p_release, p_date, %s FROM %s LEFT JOIN packages ON (packages.p_record = %s.p_record) WHERE %s %s " % (
                type, type, type, ignorecase, type)

        query = query + "LIKE '%" + self.db.sanitize_string(self.options.query) + "%'"

        if self.options.tag:
            query = "%s AND %s.t_record = '%d'"  % (query, type, tag_id)

        query  = query + " ORDER BY p_tag, p_package, " + type
        result = self.db.fetch_all(query)
        if result:
            if self.options.count:
                if self.options.quiet:
                    print len(result)
                else:
                    if self.options.tag:
                        print '%d match(es) in database for tag (%s) and substring (%s)' % (len(result), self.options.tag, self.options.query)
                    else:
                        print '%d match(es) in database for substring (%s)' % (len(result), self.options.query)
                return

            ltag = ''
            lsrc = ''
            for row in result:
                # for readability
                fromdb_tag  = row['p_tag']
                fromdb_rpm  = row['p_package']
                fromdb_ver  = row['p_version']
                fromdb_rel  = row['p_release']
                fromdb_date = row['p_date']
                fromdb_file = row[type]

                if type == 'files':
                    fromdb_user    = row['f_user']
                    fromdb_group   = row['f_group']
                    fromdb_is_suid = row['f_is_suid']
                    fromdb_is_sgid = row['f_is_sgid']
                    fromdb_perms   = row['f_perms']

                if not ltag == fromdb_tag:
                    print '\nResults in Tag: %s\n' % fromdb_tag
                    ltag = fromdb_tag

                if self.options.debug:
                    print row
                else:
                    rpm = fromdb_rpm

                    if not rpm == lsrc:
                        if type == 'files' and self.options.ownership:
                            is_suid = ''
                            is_sgid = ''
                            if fromdb_is_suid == 1:
                                is_suid = '*'
                            if fromdb_is_sgid == 1:
                                is_sgid = '*'
                            print '%s: %s (%04d,%s%s,%s%s)' % (rpm, fromdb_file, int(fromdb_perms), is_suid, fromdb_user, is_sgid, fromdb_group)
                        else:
                            print '%s: %s' % (rpm, fromdb_file)

                    if self.options.quiet:
                        lsrc = rpm
                    else:
                        if self.options.extrainfo:
                            rpm_date = datetime.datetime.fromtimestamp(float(fromdb_date))
                            print '%-16s%-27s%-9s%s' % ("Package:", fromdb_rpm, "Date:", rpm_date.strftime('%a %b %d %H:%M:%S %Y'))
                            print '%-16s%-27s%-9s%s' % ("Version:", fromdb_ver, "Release:", fromdb_rel)

        else:
            if self.options.tag:
                print 'No matches in database for tag (%s) and substring (%s)' % (self.options.tag, self.options.query)
            else:
                print 'No matches in database for substring (%s)' % self.options.query


    def add_requires(self, tag_id, record, file):
        """
        Function to add requires to the database
        """
        logging.debug('in Binary.add_requires(%s, %s, %s)' % (tag_id, record, file))

        list = commands.getoutput("rpm -qp --nosignature --requires " + file.replace(' ', '\ ') + " | egrep -v '(rpmlib|GLIBC|GCC|rtld)' | uniq")
        list = list.splitlines()
        for dep in list:
            if dep:
                self.rcommon.show_progress()
                if self.options.verbose:
                    print 'Dependency: %s' % dep
                query  = "INSERT INTO requires (t_record, p_record, requires) VALUES ('%s', '%s', '%s')" % (tag_id, record, self.db.sanitize_string(dep.strip()))
                result = self.db.do_query(query)


    def add_provides(self, tag_id, record, file):
        """
        Function to add provides to the database
        """
        logging.debug('in Binary.add_provides(%s, %s, %s)' % (tag_id, record, file))

        list = commands.getoutput("rpm -qp --nosignature --provides " + file.replace(' ', '\ '))
        list = list.splitlines()
        for prov in list:
            if prov:
                self.rcommon.show_progress()
                if self.options.verbose:
                    print 'Provides: %s' % prov
                query  = "INSERT INTO provides (t_record, p_record, provides) VALUES ('%s', '%s', '%s')" % (tag_id, record, self.db.sanitize_string(prov.strip()))
                result = self.db.do_query(query)


    def add_records(self, tag_id, record, file_list):
        """
        Function to add file records
        """
        logging.debug('in Binary.add_records(%s, %s, %s)' % (tag_id, record, file_list))

        for x in file_list.keys():
            self.rcommon.show_progress()
            if self.options.verbose:
                print 'File: %s' % file_list[x]['file']
            query  = "INSERT INTO files (t_record, p_record, files, f_user, f_group, f_is_suid, f_is_sgid, f_perms) VALUES ('%s', '%s', '%s', '%s', '%s', %d, %d, %s)" % (
                tag_id,
                record,
                self.db.sanitize_string(file_list[x]['file'].strip()),
                self.db.sanitize_string(file_list[x]['user']),
                self.db.sanitize_string(file_list[x]['group']),
                file_list[x]['is_suid'],
                file_list[x]['is_sgid'],
                file_list[x]['perms'])
            result = self.db.do_query(query)
