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
import os
import sys
import re
import commands
import logging
import tempfile
import shutil
import datetime
from glob import glob
from app.models import RPM_Tag, RPM_Package, RPM_User, RPM_Group, RPM_Requires, \
    RPM_Provides, RPM_File, RPM_Flags, RPM_Symbols


class Binary:
    """
    Class to handle working with source files
    """

    def __init__(self, config, options, rtag, rcommon):
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

        # caches
        self.symbol_cache   = {}
        self.provides_cache = {}
        self.requires_cache = {}
        self.group_cache    = {}
        self.user_cache     = {}


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

        file_list = []
        file_list.extend(glob(path + "/*.rpm"))

        if len(file_list) == 0:
            print 'No files found in %s, checking subdirectories...' % path
            # newer versions of Fedora have packages in subdirectories
            subdirs = [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]
            for s in subdirs:
                npath = '%s/%s' % (path, s)
                file_list.extend(glob(npath + "/*.rpm"))

        if len(file_list) == 0:
            print 'No files found to import in directory: %s' % path
            sys.exit(1)

        file_list.sort()

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

        tag = RPM_Tag.get_tag(tag_id)

        if RPM_Package.in_db(tag_id, package, version, release, arch):
            print 'File %s-%s-%s.%s is already in the database under tag %s' % (package, version, release, arch, tag)
            return(0)

        ## TODO: we shouldn't have to have p_tag here as t_record has the same info, but it
        ## sure makes it easier to sort alphabetically and I'm too lazy for the JOINs right now

        self.rcommon.show_progress(fname)
        try:
            p = RPM_Package.create(
                tag_id   = tag_id,
                package  = package,
                version  = version,
                release  = release,
                date     = pdate,
                arch     = arch,
                srpm     = srpm,
                fullname = fname,
                update   = update
            )
            return p.id
        except Exception, e:
            logging.error('Adding file %s failed!\n%s', file, e)
            return(0)


    def query(self, type):
        """
        Function to run the query for binary RPMs

        Valid types are: files, provides, requires, symbols, packages
        """
        logging.debug('in Binary.query(%s)' % type)

#TODO
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
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm, files, f_id, f_user, f_group, f_is_suid, f_is_sgid, f_perms FROM files LEFT JOIN packages ON (packages.p_record = files.p_record) LEFT JOIN user_names ON (files.u_record = user_names.u_record) LEFT JOIN group_names ON (files.g_record = group_names.g_record) WHERE %s files " % ignorecase
        elif type == 'symbols':
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm, symbols, symbols.f_id, files FROM symbols LEFT JOIN (packages, files) ON (packages.p_record = symbols.p_record AND symbols.f_id = files.f_id) WHERE %s symbols " % ignorecase
        elif type == 'packages':
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm FROM packages WHERE %s p_package " % ignorecase
        elif type == 'provides':
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm, pv_name FROM provides LEFT JOIN packages ON (packages.p_record = provides.p_record) JOIN provides_names ON (provides_names.pv_record = provides.pv_record) WHERE %s pv_name " % ignorecase
        elif type == 'requires':
            query = "SELECT DISTINCT p_tag, p_update, p_package, p_version, p_release, p_date, p_srpm, rq_name FROM requires LEFT JOIN packages ON (packages.p_record = requires.p_record) JOIN requires_names ON (requires_names.rq_record = requires.rq_record) WHERE %s rq_name " % ignorecase

        if self.options.regexp:
            query = query + "RLIKE '" + self.db.sanitize_string(like_q) + "'"
        else:
            query = query + "LIKE '%" + self.db.sanitize_string(like_q) + "%'"

        if self.options.tag:
            query = "%s AND %s.t_record = '%d'"  % (query, type, tag_id)

        if type == 'packages':
            query  = query + " ORDER BY p_tag, p_package"
        elif type == 'symbols':
            query = query + " ORDER BY symbols"
        elif type == 'provides':
            query = query + " ORDER BY pv_name"
        elif type == 'requires':
            query = query + " ORDER BY rq_name"
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

                if type == 'provides':
                    fromdb_type = row['pv_name']

                if type == 'requires':
                    fromdb_type = row['rq_name']

                if type == 'files':
                    # only provides, requires, files
                    fromdb_type = row['files']

                if type == 'files':
                    fromdb_user    = row['f_user']
                    fromdb_group   = row['f_group']
                    fromdb_is_suid = row['f_is_suid']
                    fromdb_is_sgid = row['f_is_sgid']
                    fromdb_perms   = row['f_perms']
                    fromdb_fileid  = row['f_id']

                if type == 'symbols':
                    fromdb_files   = row['files']
                    fromdb_symbol  = row['symbols']

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
                            print '%s (%s): %s in %s' % (rpm, fromdb_srpm, fromdb_symbol, fromdb_files)
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
                                flags = RPM_Flags.get_named(fromdb_fileid)
                            rpm_date = datetime.datetime.fromtimestamp(float(fromdb_date))
                            if flag_result:
                                print '  %-10s%s' % ("Date :", rpm_date.strftime('%a %b %d %H:%M:%S %Y'))
                                print '  %-10s%-10s%-12s%-10s%-12s%-10s%s' % ("Flags:", "RELRO  :", flags.relro, "SSP:", flags.ssp, "PIE:", flags.pie)
                                print '  %-10s%-10s%-12s%-10s%s' % ("", "FORTIFY:", flags.fortify, "NX :", flags.nx)

        else:
            if self.options.tag:
                print 'No matches in database for tag (%s) and %s (%s)' % (self.options.tag, match_type, like_q)
            else:
                print 'No matches in database for %s (%s)' % (match_type, like_q)


    def cache_get_user(self, name):
        """
        Function to look up the u_record and add it to the cache for users
        """
        uid = RPM_User.get_id(name)
        if uid:
            # add to the cache
            self.user_cache[name] = uid
            return uid
        else:
            return False


    def get_user_record(self, name):
        """
        Function to lookup, add, and cache user info
        """

        # first check the cache
        if name in self.user_cache:
            return self.user_cache[name]

        # not cached, check the database
        uid = self.cache_get_user(name)
        if uid:
            return uid

        # not cached, so not in the db, add it
        try:
            u = RPM_User.create(user = name)
        except Exception, e:
            logging.error('Failed to add user %s to the database!\n%s', name, e)
        if u:
            # add to the cache
            self.user_cache[name] = u.id
            return u.id


    def cache_get_group(self, name):
        """
        Function to look up the g_record and add it to the cache for groups
        """
        gid = RPM_Group.get_id(name)
        if gid:
            # add to the cache
            self.group_cache[name] = gid
            return gid
        else:
            return False


    def get_group_record(self, name):
        """
        Function to lookup, add, and cache group info
        """

        # first check the cache
        if name in self.group_cache:
            return self.group_cache[name]

        # not cached, check the database
        gid = self.cache_get_group(name)
        if gid:
            return gid

        # not cached, so not in the db, add it
        try:
            g = RPM_Group.create(group = name)
        except Exception, e:
            logging.error('Failed to add group %s to the database!\n%s', name, e)
        if g:
            # add to the cache
            self.group_cache[name] = g.id
            return g.id


    def cache_get_requires(self, name):
        """
        Function to look up the rq_record and add it to the cache for requires
        """
        rid = RPM_Requires.get_id(name)
        if rid:
            # add to the cache
            self.requires_cache[name] = rid
            return rid
        else:
            return False


    def get_requires_record(self, name):
        """
        Function to lookup, add, and cache requires info
        """

        # first check the cache
        if name in self.requires_cache:
            return self.requires_cache[name]

        # not cached, check the database
        rid = self.cache_get_requires(name)
        if rid:
            return rid

        return None


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
                rid = self.get_requires_record(dep.strip())
                if rid:
                    return rid
                try:
                    r = RPM_Requires.create(
                        package_id  = record,
                        tag_id      = tag_id,
                        name        = dep.strip()
                    )
                    return r.id
                except Exception, e:
                    logging.error('Failed to add requires %s to the database!\n%s', file, e)


    def cache_get_provides(self, name):
        """
        Function to look up the pv_record and add it to the cache for provides
        """
        pid = RPM_Provides.get_id(name)
        if pid:
            # add to the cache
            self.provides_cache[name] = pid
            return pid
        else:
            return False


    def get_provides_record(self, name):
        """
        Function to lookup, add, and cache provides info
        """

        # first check the cache
        if name in self.provides_cache:
            return self.provides_cache[name]

        # not cached, check the database
        pid = self.cache_get_provides(name)
        if pid:
            return pid

        return None


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
                pid = self.get_provides_record(prov.strip())
                if pid:
                    return pid
                try:
                    p = RPM_Provides.create(
                        package_id = record,
                        tag_id     = tag_id,
                        name       = prov.strip()
                    )
                    return p.id
                except Exception, e:
                    logging.error('Failed to add provides %s to the database!\n%s', file, e)


    def add_records(self, tag_id, record, file_list):
        """
        Function to add file records
        """
        logging.debug('in Binary.add_records(%s, %s, %s)' % (tag_id, record, file_list))

        for x in file_list.keys():
            self.rcommon.show_progress()
            if self.options.verbose:
                print 'File: %s' % file_list[x]['file']

            try:
                f = RPM_File.create(
                    tag_id     = tag_id,
                    package_id = record,
                    user_id    = file_list[x]['user'],
                    group_id   = file_list[x]['group'],
                    file       = file_list[x]['file'].strip(),
                    is_suid    = file_list[x]['is_suid'],
                    is_sgid    = file_list[x]['is_sgid'],
                    perms      = file_list[x]['perms']
                )
            except Exception, e:
                logging.error('Adding file %s failed!\n%s', file, e)


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
                        file_id = RPM_File.get_id(nfile, tag_id, record)
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
        # set all bits to their defaults
        flags = {'relro': 0, 'ssp': 0, 'nx': 1, 'pie': 0, 'fortify_source': 0}

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

        if re.search('__stack_chk_fail', readelf_s):
            # found
            flags['ssp'] = 1

        if re.search('GNU_STACK.*RWE', readelf_l):
            # disabled
            flags['nx'] = 0

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

        return flags


    def add_flag_records(self, tag_id, file_id, record, flags):
        """
        Function to add flag records to the database
        """
        logging.debug('in Binary.add_flag_records(%s, %s, %s, %s)' % (tag_id, file_id, record, flags))

        logging.debug('flags: %s' % flags)

        try:
            f = RPM_Flags.create(
                tag_id     = tag_id,
                package_id = record,
                file_id    = file_id,
                relro      = flags['relro'],
                ssp        = flags['ssp'],
                pie        = flags['pie'],
                fortify    = flags['fortify_source'],
                nx         = flags['nx']
            )
        except Exception, e:
            logging.error('Adding flags for file_id %d failed!\n%s', file_id, e)


    def add_symbol_records(self, tag_id, file_id, record, symbols):
        """
        Function to add symbol records to the database
        """
        logging.debug('in Binary.add_symbol_records(%s, %s, %s, %s)' % (tag_id, file_id, record, symbols))

        for symbol in symbols:
            try:
                s = RPM_Symbols.create(
                    package_id = record,
                    tag_id     = tag_id,
                    file_id    = file_id,
                    symbols    = symbol
                )
            except Exception, e:
                logging.error('Adding symbol for file_id %d failed!\n%s', file_id, e)


    def list_updates(self, tag):
        """
        Function to list packages that have been imported due to being in the updates directory
        """
        logging.debug('in Binary.list_updates(%s)' % tag)

        print 'Updated packages in tag %s:\n' % tag

        results = RPM_Package.list_updates(tag)
        if results:
            for xrow in results:
                print '%s' % xrow.fullname
        else:
            print 'No results found.'


    def show_sxid(self, type, tag):
        """
        Function to list all suid or sgid files per tag
        """
        logging.debug('in Binary.show_sxid(%s, %s)' % (type, tag))

        print 'Searching for %s files in tag %s\n' % (type.upper(), tag)

        tag_id = RPM_Tag.get_id(tag)

        if not tag_id:
            print 'Invalid tag: %s' % tag
            sys.exit(1)

        if type == 'suid':
            db_col = 'is_suid'
        elif type == 'sgid':
            db_col = 'is_sgid'
        else:
            print 'Invalid value, looking for suid or sgid, received: %s' % type
            sys.exit(1)

        results = RPM_File.get_sxid(tag_id, db_col)
        if results:
            for xrow in results:
                print '%s: %s [%s:%s mode %s]' % (xrow.rpm_package.package,
                                                  xrow.rpm_file.file,
                                                  xrow.rpm_user.user,
                                                  xrow.rpm_group.group,
                                                  xrow.rpm_file.perms)
        else:
            print 'No results found.'
