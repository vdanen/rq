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
"""
import os, sys, re, commands, logging, tempfile, shutil, datetime
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

        self.re_brpm     = re.compile(r'\.rpm$')
        self.re_srpm     = re.compile(r'\.src\.rpm$')
        self.re_patch    = re.compile(r'\.(diff|dif|patch)(\.bz2|\.gz)?$')
        self.re_tar      = re.compile(r'\.((tar)(\.bz2|\.gz)?|t(gz|bz2?))$')
        self.re_targz    = re.compile(r'\.(tgz|tar\.gz)$')
        self.re_tarbz    = re.compile(r'\.(tbz2?|tar\.bz2)$')
        self.re_patchgz  = re.compile(r'\.(patch|diff|dif)(\.gz)$')
        self.re_patchbz  = re.compile(r'\.(patch|diff|dif)(\.bz2)$')
        self.re_srpmname = re.compile(r'(\w+)(-[0-9]).*')

        self.excluded_symbols = ['abort', '__assert_fail', 'bindtextdomain', '__bss_start', 'calloc',
                                 'chmod', 'close', 'close_stdout', '__data_start', 'dcgettext', 'dirname',
                                 '_edata', '_end', 'error', '_exit', 'exit', 'fclose', 'fdopen', 'ferror',
                                 'fgets', '_fini', 'fnmatch', 'fopen', 'fork', 'fprintf', '__fprintf_chk',
                                 'fread', 'free', 'fscanf', 'fwrite', 'getenv', 'getgrgid', 'getgrnam',
                                 'getopt', 'getopt_long', 'getpwnam', 'getpwuid', 'gettimeofday',
                                 '__gmon_start__', '_init', 'ioctl', '_IO_stdin_used', 'isatty', 'iswalnum',
                                 'iswprint', 'iswspace', '_Jv_RegisterClasses', 'kill', '__libc_csu_fini',
                                 '__libc_csu_init', '__libc_start_main', 'localtime', 'malloc', 'memchr',
                                 'memcpy', '__memcpy_chk', 'memmove', 'mempcpy', '__mempcpy_chk', 'memset',
                                 'mkstemp', 'mktime', 'opendir', 'optarg', 'pclose', 'pipe', 'popen',
                                 '__printf_chk', '__progname', '__progname_full', 'program_invocation_name',
                                 'program_invocation_short_name', 'program_name', 'read', 'readdir',
                                 'readlink', 'realloc', 'rename', 'setenv', 'setlocale', 'sigaction',
                                 'sigaddset', 'sigemptyset', 'sigismember', 'signal', 'sigprocmask',
                                 '__stack_chk_fail', 'stderr', 'stdout', 'stpcpy', 'strcasecmp', 'strchr',
                                 'strcmp', 'strcpy', 'strerror', 'strftime', 'strlen', 'strncasecmp',
                                 'strnlen', 'strrchr', 'strstr', 'strtol', 'textdomain', 'time', 'umask',
                                 'unlink', 'Version', 'version_etc_copyright', 'waitpid', 'write', '__xstat']


    def rpm_add_directory(self, tag, path, updatepath):
        """
        Function to import a directory full of RPMs
        """
        logging.debug('in Binary.rpm_add_directory(%s, %s, %s)' % (tag, path, updatepath))

        if not os.path.isdir(path):
            print 'Path (%s) is not a valid directory!' % path
            sys.exit(1)

        if not os.path.isdir(updatepath):
            print 'Path (%s) is not a valid directory!' % updatepath
            sys.exit(1)

        file_list = glob(path + "/*.rpm")
        file_list.sort()

        if not file_list:
            print 'No files found to import in directory: %s' % path
            sys.exit(1)

        tag_id = self.rtag.add_record(tag, path, updatepath)
        if tag_id == 0:
            logging.critical('Unable to add tag "%s" to the database!' % tag)
            sys.exit(1)

        for file in file_list:
            if not os.path.isfile(file):
                print 'File %s not found!\n' % file
            elif not self.re_brpm.search(file):
                print 'File %s is not a binary rpm!\n' % file
            else:
                self.record_add(tag_id, file)


    def record_add(self, tag_id, file, update=0):
        """
        Function to add a record to the database
        """
        logging.debug('in Binary.record_add(%s, %s, %d)' % (tag_id, file, update))

        if os.path.isfile(file):
            path = os.path.abspath(os.path.dirname(file))
        else:
            path = os.path.abspath(file)
        logging.debug('Path:\t%s' % path)

        self.rcommon.file_rpm_check(file)

        record = self.package_add_record(tag_id, file, update)
        if not record:
            return

        file_list = self.rcommon.rpm_list(file)
        if not file_list:
            return

        logging.debug('Add file records for package record: %s' % record)
        self.add_records(tag_id, record, file_list)
        self.add_requires(tag_id, record, file)
        self.add_provides(tag_id, record, file)
        self.add_binary_records(tag_id, record, file)

        if self.options.progress:
            sys.stdout.write('\n')


    def package_add_record(self, tag_id, file, update=0):
        """
        Function to add a package record
        """
        logging.debug('in Binary.package_add_record(%s, %s, %d)' % (tag_id, file, update))

        fname   = os.path.basename(file)
        rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{BUILDTIME}|%{ARCH}|%{SOURCERPM}' " + self.rcommon.clean_shell(file))
        tlist   = rpmtags.split('|')
        logging.debug("tlist is %s " % tlist)
        package = tlist[0].strip()
        version = tlist[1].strip()
        release = tlist[2].strip()
        pdate   = tlist[3].strip()
        arch    = tlist[4].strip()
        srpm    = self.re_srpmname.sub(r'\1', tlist[5].strip())

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

        query  = "INSERT INTO packages (t_record, p_tag, p_package, p_version, p_release, p_date, p_arch, p_srpm, p_fullname, p_update) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', %d)" % (
            tag_id,
            self.db.sanitize_string(tag),
            self.db.sanitize_string(package),
            self.db.sanitize_string(version),
            self.db.sanitize_string(release),
            self.db.sanitize_string(pdate),
            self.db.sanitize_string(arch),
            self.db.sanitize_string(srpm),
            self.db.sanitize_string(fname),
            update)

        result = self.db.do_query(query)
        self.rcommon.show_progress(fname)

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

        if self.options.ignorecase and not self.options.regexp:
            ignorecase = ''
        else:
            ignorecase = 'BINARY'

        if type == 'files':
            like_q = self.options.query
        if type == 'provides':
            like_q = self.options.provides
        if type == 'requires':
            like_q = self.options.requires
        if type == 'symbols':
            like_q = self.options.symbols
        if type == 'packages':
            like_q = self.options.query

        if self.options.regexp:
            match_type = 'regexp'
        else:
            match_type = 'substring'

        if not self.options.quiet:
            print 'Searching database records for %s match for %s (%s)' % (match_type, type, like_q)

        if type == 'files':
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm, files, f_id, f_user, f_group, f_is_suid, f_is_sgid, f_perms FROM files LEFT JOIN packages ON (packages.p_record = files.p_record) WHERE %s files " % ignorecase
        elif type == 'symbols':
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm, symbols, symbols.f_id, files FROM symbols LEFT JOIN (packages, files) ON (packages.p_record = symbols.p_record AND symbols.f_id = files.f_id) WHERE %s symbols " % ignorecase
        elif type == 'packages':
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm FROM packages WHERE %s p_package " % ignorecase
        else:
            # query on type: provides, requires
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm, %s FROM %s LEFT JOIN packages ON (packages.p_record = %s.p_record) WHERE %s %s " % (
                type, type, type, ignorecase, type)

        if self.options.regexp:
            query = query + "RLIKE '" + self.db.sanitize_string(like_q) + "'"
        else:
            query = query + "LIKE '%" + self.db.sanitize_string(like_q) + "%'"

        if self.options.tag:
            query = "%s AND %s.t_record = '%d'"  % (query, type, tag_id)

        if type == 'packages':
            query  = query + " ORDER BY p_tag, p_package"
        else:
            query  = query + " ORDER BY p_tag, p_package, " + type

        result = self.db.fetch_all(query)
        if result:
            if self.options.count:
                if self.options.quiet:
                    print len(result)
                else:
                    if self.options.tag:
                        print '%d match(es) in database for tag (%s) and %s (%s)' % (len(result), self.options.tag, match_type, like_q)
                    else:
                        print '%d match(es) in database for %s (%s)' % (len(result), match_type, like_q)
                return

            ltag = ''
            lsrc = ''
            for row in result:
                utype = ''
                # for readability
                fromdb_tag  = row['p_tag']
                fromdb_rpm  = row['p_package']
                fromdb_ver  = row['p_version']
                fromdb_rel  = row['p_release']
                fromdb_date = row['p_date']
                fromdb_srpm = row['p_srpm']
                if not type == 'packages':
                    fromdb_type = row[type]

                if type == 'files':
                    fromdb_user    = row['f_user']
                    fromdb_group   = row['f_group']
                    fromdb_is_suid = row['f_is_suid']
                    fromdb_is_sgid = row['f_is_sgid']
                    fromdb_perms   = row['f_perms']
                    fromdb_fileid  = row['f_id']
                if type == 'symbols':
                    fromdb_files   = row['files']

                if row['p_update'] == 1:
                    utype = '[update] '

                if not ltag == fromdb_tag:
                    if not type == 'packages':
                        print '\n\nResults in Tag: %s\n%s\n' % (fromdb_tag, '='*40)
                    ltag = fromdb_tag

                if self.options.debug:
                    print row
                else:
                    rpm = '%s-%s-%s' % (fromdb_rpm, fromdb_ver, fromdb_rel)

                    if not rpm == lsrc:
                        if type == 'files' and self.options.ownership:
                            is_suid = ''
                            is_sgid = ''
                            if fromdb_is_suid == 1:
                                is_suid = '*'
                            if fromdb_is_sgid == 1:
                                is_sgid = '*'
                            print '%s (%s): %s (%04d,%s%s,%s%s)' % (rpm, fromdb_srpm, fromdb_type, int(fromdb_perms), is_suid, fromdb_user, is_sgid, fromdb_group)
                        elif type == 'symbols':
                            print '%s (%s): %s in %s' % (rpm, fromdb_srpm, fromdb_type, fromdb_files)
                        elif type == 'packages':
                            print '%s/%s %s' % (ltag, rpm, utype)
                        else:
                            print '%s%s (%s): %s' % (utype, rpm, fromdb_srpm, fromdb_type)

                    if self.options.quiet:
                        lsrc = rpm
                    else:
                        flag_result = None
                        if self.options.extrainfo:
                            if type == 'files':
                                query       = 'SELECT * FROM flags WHERE f_id = %d LIMIT 1' % fromdb_fileid
                                flag_result = self.db.fetch_all(query)
                                if flag_result:
                                    for x in flag_result:
                                        #fetch_all returns a tuple containing a dict, so...
                                        flags = self.convert_flags(x)
                            rpm_date = datetime.datetime.fromtimestamp(float(fromdb_date))
                            if flag_result:
                                print '  %-10s%s' % ("Date :", rpm_date.strftime('%a %b %d %H:%M:%S %Y'))
                                print '  %-10s%-10s%-12s%-10s%-12s%-10s%s' % ("Flags:", "RELRO  :", flags['relro'], "SSP:", flags['ssp'], "PIE:", flags['pie'])
                                print '  %-10s%-10s%-12s%-10s%s' % ("", "FORTIFY:", flags['fortify'], "NX :", flags['nx'])

        else:
            if self.options.tag:
                print 'No matches in database for tag (%s) and %s (%s)' % (self.options.tag, match_type, like_q)
            else:
                print 'No matches in database for %s (%s)' % (match_type, like_q)


    def add_requires(self, tag_id, record, file):
        """
        Function to add requires to the database
        """
        logging.debug('in Binary.add_requires(%s, %s, %s)' % (tag_id, record, file))

        list = commands.getoutput("rpm -qp --nosignature --requires " + self.rcommon.clean_shell(file) + " | egrep -v '(rpmlib|GLIBC|GCC|rtld)' | uniq")
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

        list = commands.getoutput("rpm -qp --nosignature --provides " + self.rcommon.clean_shell(file))
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


    def add_binary_records(self, tag_id, record, rpm):
        """
        Function to add binary symbols and flags to the database
        """
        logging.debug('in Binary.add_binary_records(%s, %s, %s)' % (tag_id, record, rpm))

        cpio_dir = tempfile.mkdtemp()
        try:
            current_dir = os.getcwd()
            os.chdir(cpio_dir)
            # explode rpm
            command      = 'rpm2cpio "%s" | cpio -d -i 2>/dev/null' % rpm
            (rc, output) = commands.getstatusoutput(command)

            command      = 'find . -perm /u+x -type f'
            (rc, output) = commands.getstatusoutput(command)

            dir = output.split()
            logging.debug('dir is %s' % dir)
            for file in dir:
                if os.path.isfile(file):
                    logging.debug('checking file: %s' % file)
                    # executable files
                    if re.search('ELF', commands.getoutput('file ' + self.rcommon.clean_shell(file))):
                        # ELF binaries
                        flags   = self.get_binary_flags(file)
                        symbols = self.get_binary_symbols(file)
                        # need to change ./usr/sbin/foo to /usr/sbin/foo and look up the file record
                        nfile   = file[1:]
                        query   = "SELECT f_id FROM files WHERE t_record = %s AND p_record = %s AND files = '%s'" % (tag_id, record, nfile)
                        file_id = self.db.fetch_one(query)
                        self.add_flag_records(tag_id, file_id, record, flags)
                        self.add_symbol_records(tag_id, file_id, record, symbols)
            os.chdir(current_dir)
        finally:
            logging.debug('Removing temporary directory: %s...' % cpio_dir)
            try:
                shutil.rmtree(cpio_dir)
            except:
                # if we can't remove the directory, recursively chmod and try again
                os.system('chmod -R u+rwx ' + cpio_dir)
                shutil.rmtree(cpio_dir)


    def get_binary_symbols(self, file):
        """
        Function to get symbols from a binary file
        """
        symbols = []

        self.rcommon.show_progress()

        nm_output = commands.getoutput('nm -D -g ' + self.rcommon.clean_shell(file))
        nm_output = nm_output.split()
        for symbol in nm_output:
            if re.search('^[A-Za-z_]{2}.*', symbol):
                if symbol not in self.excluded_symbols:
                    # dump the __cxa* symbols
                    if not re.search('^__cxa', symbol):
                        symbols.append(symbol)

        return symbols


    def get_binary_flags(self, file):
        """
        Function to get binary flags from a file
        """
        flags = {'relro': 0, 'ssp': 0, 'nx': 0, 'pie': 0, 'fortify_source': 0}

        self.rcommon.show_progress()

        readelf_l = commands.getoutput('readelf -l ' + self.rcommon.clean_shell(file))
        readelf_d = commands.getoutput('readelf -d ' + self.rcommon.clean_shell(file))
        readelf_s = commands.getoutput('readelf -s ' + self.rcommon.clean_shell(file))
        readelf_h = commands.getoutput('readelf -h ' + self.rcommon.clean_shell(file))

        if re.search('GNU_RELRO', readelf_l):
            if re.search('BIND_NOW', readelf_d):
                # full RELRO
                flags['relro'] = 1
            else:
                # partial RELRO
                flags['relro'] = 2
        else:
            # no RELRO
            flags['relro'] = 0

        if re.search('__stack_chk_fail', readelf_s):
            # found
            flags['ssp'] = 1
        else:
            # none
            flags['ssp'] = 0

        if re.search('GNU_STACK.*RWE', readelf_l):
            # disabled
            flags['nx'] = 0
        else:
            # enabled
            flags['nx'] = 1

        if re.search('Type:( )+EXEC', readelf_h):
            # none
            flags['pie'] = 0
        elif re.search('Type:( )+DYN', readelf_h):
            if re.search('\(DEBUG\)', readelf_d):
                # enabled
                flags['pie'] = 1
            else:
                # DSO
                flags['pie'] = 2

        if re.search('_chk@GLIBC', readelf_s):
            # found
            flags['fortify_source'] = 1
        else:
            # not found
            flags['fortify_source'] = 0

        return flags


    def add_flag_records(self, tag_id, file_id, record, flags):
        """
        Function to add flag records to the database
        """
        logging.debug('in Binary.add_flag_records(%s, %s, %s, %s)' % (tag_id, file_id, record, flags))

        logging.debug('flags: %s' % flags)
        query  = "INSERT INTO flags (t_record, p_record, f_id, f_relro, f_ssp, f_pie, f_fortify, f_nx) VALUES ('%s', '%s', '%s', %d, %d, %d, %d, %d)" % (
            tag_id,
            record,
            file_id,
            flags['relro'],
            flags['ssp'],
            flags['pie'],
            flags['fortify_source'],
            flags['nx'])
        result = self.db.do_query(query)


    def add_symbol_records(self, tag_id, file_id, record, symbols):
        """
        Function to add symbol records to the database
        """
        logging.debug('in Binary.add_symbol_records(%s, %s, %s, %s)' % (tag_id, file_id, record, symbols))

        for symbol in symbols:
            query  = "INSERT INTO symbols (t_record, p_record, f_id, symbols) VALUES ('%s', '%s', '%s', '%s')" % (
                tag_id,
                record,
                file_id,
                self.db.sanitize_string(symbol))
            result = self.db.do_query(query)


    def convert_flags(self, flags):
        """
        Convert numeric representation of flags (from the database) to human
        readable form, dropping the prefix (i.e. f_relro becomes relro)
        """
        newflags = {}

        if flags['f_relro'] == 1:
            newflags['relro'] = "full"
        elif flags['f_relro'] == 2:
            newflags['relro'] = "partial"
        else:
            newflags['relro'] = "none"

        if flags['f_ssp'] == 1:
            newflags['ssp'] = "found"
        else:
            newflags['ssp'] = "not found"

        if flags['f_nx'] == 1:
            newflags['nx'] = "enabled"
        else:
            newflags['nx'] = "disabled"

        if flags['f_pie'] == 2:
            newflags['pie'] = "DSO"
        elif flags['f_pie'] == 1:
            newflags['pie'] = "enabled"
        else:
            newflags['pie'] = "none"

        if flags['f_fortify'] == 1:
            newflags['fortify'] = "found"
        else:
            newflags['fortify'] = "not found"

        return(newflags)


    def list_updates(self, tag):
        """
        Function to list packages that have been imported due to being in the updates directory
        """
        logging.debug('in Binary.list_updates(%s)' % tag)

        print 'Updated packages in tag %s:\n' % tag

        query   = "SELECT t_record FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        tag_id  = self.db.fetch_one(query)

        query   = "SELECT p_fullname FROM packages WHERE t_record = %s AND p_update = 1 ORDER BY p_fullname ASC" % tag_id
        results = self.db.fetch_all(query)
        if results:
            for xrow in results:
                print '%s' % xrow['p_fullname']
        else:
            print 'No results found.'


    def show_sxid(self, type, tag):
        """
        Function to list all suid or sgid files per tag
        """
        logging.debug('in Binary.show_sxid(%s, %s)' % (type, tag))

        print 'Searching for %s files in tag %s\n' % (type.upper(), tag)

        query   = "SELECT t_record FROM tags WHERE tag = '%s' LIMIT 1" % self.db.sanitize_string(tag)
        tag_id  = self.db.fetch_one(query)

        if not tag_id:
            print 'Invalid tag: %s' % tag
            sys.exit(1)

        if type == 'suid':
            db_col = 'f_is_suid'
        elif type == 'sgid':
            db_col = 'f_is_sgid'

        query   = "SELECT p_package, files, f_user, f_group, f_perms FROM files JOIN packages ON (files.p_record = packages.p_record) WHERE %s = 1 AND files.t_record = %s ORDER BY p_package ASC" % (db_col, tag_id)
        results = self.db.fetch_all(query)
        if results:
            for xrow in results:
                print '%s: %s [%s:%s mode %s]' % (xrow['p_package'], xrow['files'], xrow['f_user'], xrow['f_group'], xrow['f_perms'])
        else:
            print 'No results found.'
