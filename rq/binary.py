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

        tid = self.rtag.add_record(tag, path, updatepath)
        if tid == 0:
            logging.critical('Unable to add tag "%s" to the database!' % tag)
            sys.exit(1)

        for rpm in file_list:
            if not os.path.isfile(rpm):
                print 'File %s not found!\n' % rpm
            elif not self.re_brpm.search(rpm):
                print 'File %s is not a binary rpm!\n' % rpm
            else:
                self.record_add(tid, rpm)


    def record_add(self, tid, rpm, update=0):
        """
        Function to add a record to the database
        """
        logging.debug('in Binary.record_add(%s, %s, %d)' % (tid, rpm, update))

        if os.path.isfile(rpm):
            path = os.path.abspath(os.path.dirname(rpm))
        else:
            path = os.path.abspath(rpm)
        logging.debug('Path:\t%s' % path)

        self.rcommon.file_rpm_check(rpm)

        pid = self.package_add_record(tid, rpm, update)
        if not pid:
            return

        rpm_list = self.rcommon.rpm_list(rpm)
        if not rpm_list:
            return

        logging.debug('Add file records for pid: %s' % pid)
        self.add_records(tid, pid, rpm_list)
        self.add_requires(tid, pid, rpm)
        self.add_provides(tid, pid, rpm)
        self.add_binary_records(tid, pid, rpm)

        if self.options.progress:
            sys.stdout.write('\n')


    def package_add_record(self, tid, rpm, update=0):
        """
        Function to add a package record
        """
        logging.debug('in Binary.package_add_record(%s, %s, %d)' % (tid, rpm, update))

        fname   = os.path.basename(rpm)
        rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{BUILDTIME}|%{ARCH}|%{SOURCERPM}' " + self.rcommon.clean_shell(rpm))
        tlist   = rpmtags.split('|')
        logging.debug("tlist is %s " % tlist)
        package = tlist[0].strip()
        version = tlist[1].strip()
        release = tlist[2].strip()
        pdate   = tlist[3].strip()
        arch    = tlist[4].strip()
        srpm    = self.re_srpmname.sub(r'\1', tlist[5].strip())

        tag = RPM_Tag.get_tag(tid)

        if RPM_Package.in_db(tid, package, version, release, arch):
            print 'File %s-%s-%s.%s is already in the database under tag %s' % (package, version, release, arch, tag)
            return 0

        # TODO: we shouldn't have to have p_tag here as t_record has the same info, but it
        # TODO: sure makes it easier to sort alphabetically and I'm too lazy for the JOINs right now

        self.rcommon.show_progress(fname)
        try:
            p = RPM_Package.create(
                tid      = tid,
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
            logging.error('Adding file %s failed!\n%s', rpm, e)
            return 0


    def query(self, qtype):
        """
        Function to run the query for binary RPMs

        Valid types are: files, provides, requires, symbols, packages
        """
        logging.debug('in Binary.query(%s)' % qtype)

        # TODO: seems to always be case-insensitive; need to change args!!
        t = self.rtag.lookup(self.options.tag)
        if self.options.tag and not t:
            print 'Tag %s is not a known tag!\n' % self.options.tag
            sys.exit(1)
        elif self.options.tag and t:
            tid = t['id']
        else:
            tid = ''

        like_q = ''
        if qtype == 'files':
            like_q = self.options.query
        elif qtype == 'provides':
            like_q = self.options.provides
        elif qtype == 'requires':
            like_q = self.options.requires
        elif qtype == 'symbols':
            like_q = self.options.symbols
        elif qtype == 'packages':
            like_q = self.options.query

        if self.options.regexp:
            match_type = 'regexp'
        else:
            match_type = 'substring'

        if not self.options.quiet:
            print 'Searching database records for %s match for %s (%s)' % (match_type, qtype, like_q)

        result = None
        if qtype == 'files':
            if self.options.regexp:
                if self.options.tag:
                    result = RPM_File.select().where((RPM_File.file.regexp(like_q)) & (RPM_File.tid == tid)).order_by(RPM_File.file.asc())
                else:
                    result = RPM_File.select().where(RPM_File.file.regexp(like_q)).order_by(RPM_File.file.asc())
            else:
                if self.options.tag:
                    result = RPM_File.select().where((RPM_File.file.contains(like_q)) & (RPM_File.tid == tid)).order_by(RPM_File.file.asc())
                else:
                    result = RPM_File.select().where(RPM_File.file.contains(like_q)).order_by(RPM_File.file.asc())

        elif qtype == 'symbols':
            if self.options.regexp:
                if self.options.tag:
                    result = RPM_Symbols.select().where((RPM_Symbols.symbols.regexp(like_q)) & (RPM_Symbols.tid == tid)).order_by(RPM_Symbols.symbols.asc())
                else:
                    result = RPM_Symbols.select().where(RPM_Symbols.symbols.regexp(like_q)).order_by(RPM_Symbols.symbols.asc())
            else:
                if self.options.tag:
                    result = RPM_Symbols.select().where((RPM_Symbols.symbols.contains(like_q)) & (RPM_Symbols.tid == tid)).order_by(RPM_Symbols.symbols.asc())
                else:
                    result = RPM_Symbols.select().where(RPM_Symbols.symbols.contains(like_q)).order_by(RPM_Symbols.symbols.asc())

        elif qtype == 'packages':
            if self.options.regexp:
                if self.options.tag:
                    result = RPM_Package.select().where((RPM_Package.package.regexp(like_q)) & (RPM_Package.tid == tid)).order_by(RPM_Package.package.asc())
                else:
                    result = RPM_Package.select().where(RPM_Package.package.regexp(like_q)).order_by(RPM_Package.package.asc())
            else:
                if self.options.tag:
                    result = RPM_Package.select().where((RPM_Package.package.contains(like_q)) & (RPM_Package.tid == tid)).order_by(RPM_Package.package.asc())
                else:
                    result = RPM_Package.select().where(RPM_Package.package.contains(like_q)).order_by(RPM_Package.package.asc())

        elif qtype == 'provides':
            if self.options.regexp:
                if self.options.tag:
                    result = RPM_Provides.select().where((RPM_Provides.name.regexp(like_q)) & (RPM_Provides.tid == tid)).order_by(RPM_Provides.name.asc())
                else:
                    result = RPM_Provides.select().where(RPM_Provides.name.regexp(like_q)).order_by(RPM_Provides.name.asc())
            else:
                if self.options.tag:
                    result = RPM_Provides.select().where((RPM_Provides.name.contains(like_q)) & (RPM_Provides.tid == tid)).order_by(RPM_Provides.name.asc())
                else:
                    result = RPM_Provides.select().where(RPM_Provides.name.contains(like_q)).order_by(RPM_Provides.name.asc())

        elif qtype == 'requires':
            if self.options.regexp:
                if self.options.tag:
                    result = RPM_Requires.select().where((RPM_Requires.name.regexp(like_q)) & (RPM_Requires.tid == tid)).order_by(RPM_Requires.name.asc())
                else:
                    result = RPM_Requires.select().where(RPM_Requires.name.regexp(like_q)).order_by(RPM_Requires.name.asc())
            else:
                if self.options.tag:
                    result = RPM_Requires.select().where((RPM_Requires.name.contains(like_q)) & (RPM_Requires.tid == tid)).order_by(RPM_Requires.name.asc())
                else:
                    result = RPM_Requires.select().where(RPM_Requires.name.contains(like_q)).order_by(RPM_Requires.name.asc())

        # DEBUG: print result
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
                # DEBUG: print vars(row)
                utype = ''
                # for readability
                package = RPM_Package.get(RPM_Package.id == row.pid)
                r_tag   = RPM_Tag.get_tag(row.tid)
                r_rpm   = package.package
                r_ver   = package.version
                r_rel   = package.release
                r_date  = package.date
                r_srpm  = package.srpm

                # defaults, so nothing is undeclared
                r_is_suid = ''
                r_is_sgid = ''
                r_type    = ''
                r_user    = ''
                r_group   = ''
                r_perms   = ''
                r_symbol  = ''
                r_fileid  = ''
                r_files   = ''

                if qtype == 'provides':
                    r_type = row.name

                if qtype == 'requires':
                    r_type = row.name

                if qtype == 'files':
                    # only provides, requires, files
                    r_type = row.file

                if qtype == 'files':
                    r_user    = RPM_User.get_name(row.uid)
                    r_group   = RPM_Group.get_name(row.gid)
                    r_is_suid = row.is_suid
                    r_is_sgid = row.is_sgid
                    r_perms   = row.perms
                    r_fileid  = row.id

                if qtype == 'symbols':
                    r_files  = RPM_File.get_name(row.fid)
                    r_symbol = row.symbols

                if row.update == 1:
                    utype = '[update] '

                if not ltag == r_tag:
                    if not qtype == 'packages':
                        print '\n\nResults in Tag: %s\n%s\n' % (r_tag, '='*40)
                    ltag = r_tag

                if self.options.debug:
                    print vars(row)
                else:
                    rpm = '%s-%s-%s' % (r_rpm, r_ver, r_rel)

                    if not rpm == lsrc:
                        if qtype == 'files' and self.options.ownership:
                            is_suid = ''
                            is_sgid = ''
                            if r_is_suid == 1:
                                is_suid = '*'
                            if r_is_sgid == 1:
                                is_sgid = '*'
                            print '%s (%s): %s (%04d,%s%s,%s%s)' % (rpm, r_srpm, r_type, int(r_perms), is_suid, r_user, is_sgid, r_group)
                        elif qtype == 'symbols':
                            print '%s (%s): %s in %s' % (rpm, r_srpm, r_symbol, r_files)
                        elif qtype == 'packages':
                            print '%s/%s %s' % (ltag, rpm, utype)
                        else:
                            print '%s%s (%s): %s' % (utype, rpm, r_srpm, r_type)

                    if self.options.quiet:
                        lsrc = rpm
                    else:
                        flags = None
                        if self.options.extrainfo:
                            if qtype == 'files':
                                flags = RPM_Flags.get_named(r_fileid)
                            rpm_date = datetime.datetime.fromtimestamp(float(r_date))
                            if flags:
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
            sys.exit(1)

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
            sys.exit(1)

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


    def add_requires(self, tid, pid, fname):
        """
        Function to add requires to the database
        """
        logging.debug('in Binary.add_requires(%s, %s, %s)' % (tid, pid, fname))

        flist = commands.getoutput("rpm -qp --nosignature --requires " + self.rcommon.clean_shell(fname) + " | egrep -v '(rpmlib|GLIBC|GCC|rtld)' | uniq")
        flist = flist.splitlines()
        for dep in flist:
            if dep:
                self.rcommon.show_progress()
                if self.options.verbose:
                    print 'Dependency: %s' % dep
                rid = self.get_requires_record(dep.strip())
                if rid:
                    return rid
                try:
                    r = RPM_Requires.create(
                        pid  = pid,
                        tid  = tid,
                        name = dep.strip()
                    )
                    return r.id
                except Exception, e:
                    logging.error('Failed to add requires %s to the database!\n%s', fname, e)


    def cache_get_provides(self, name):
        """
        Function to look up the pv_record and add it to the cache for provides
        """
        prid = RPM_Provides.get_id(name)
        if prid:
            # add to the cache
            self.provides_cache[name] = prid
            return prid
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
        prid = self.cache_get_provides(name)
        if prid:
            return prid

        return None


    def add_provides(self, tid, pid, fname):
        """
        Function to add provides to the database
        """
        logging.debug('in Binary.add_provides(%s, %s, %s)' % (tid, pid, fname))

        flist = commands.getoutput("rpm -qp --nosignature --provides " + self.rcommon.clean_shell(fname))
        flist = flist.splitlines()
        for prov in flist:
            if prov:
                self.rcommon.show_progress()
                if self.options.verbose:
                    print 'Provides: %s' % prov
                prid = self.get_provides_record(prov.strip())
                if prid:
                    return prid
                try:
                    pr = RPM_Provides.create(
                         pid  = pid,
                         tid  = tid,
                         name = prov.strip()
                    )
                    return pr.id
                except Exception, e:
                    logging.error('Failed to add provides %s to the database!\n%s', fname, e)


    def add_records(self, tid, pid, file_list):
        """
        Function to add file records
        """
        logging.debug('in Binary.add_records(%s, %s, %s)' % (tid, pid, file_list))

        for x in file_list.keys():
            fname = file_list[x]['file'].strip()
            uid   = self.get_user_record(file_list[x]['user'])
            gid   = self.get_group_record(file_list[x]['group'])
            self.rcommon.show_progress()
            if self.options.verbose:
                print 'File: %s' % fname

            try:
                f = RPM_File.create(
                    tid     = tid,
                    pid     = pid,
                    uid     = uid,
                    gid     = gid,
                    file    = fname,
                    is_suid = file_list[x]['is_suid'],
                    is_sgid = file_list[x]['is_sgid'],
                    perms   = file_list[x]['perms']
                )
                logging.debug('Filed File with id %d', f.id)
            except Exception, e:
                logging.error('Adding file %s failed!\n%s', fname, e)


    def add_binary_records(self, tid, pid, rpm):
        """
        Function to add binary symbols and flags to the database
        """
        logging.debug('in Binary.add_binary_records(%s, %s, %s)' % (tid, pid, rpm))

        cpio_dir = tempfile.mkdtemp()
        try:
            current_dir = os.getcwd()
            os.chdir(cpio_dir)
            # explode rpm
            command      = 'rpm2cpio "%s" | cpio -d -i 2>/dev/null' % rpm
            (rc, output) = commands.getstatusoutput(command)

            command      = 'find . -perm /u+x -type f'
            (rc, output) = commands.getstatusoutput(command)

            rdir = output.split()
            logging.debug('dir is %s' % rdir)
            for fname in rdir:
                if os.path.isfile(fname):
                    logging.debug('checking file: %s' % fname)
                    # executable files
                    if re.search('ELF', commands.getoutput('file ' + self.rcommon.clean_shell(fname))):
                        # ELF binaries
                        flags   = self.get_binary_flags(fname)
                        symbols = self.get_binary_symbols(fname)
                        # need to change ./usr/sbin/foo to /usr/sbin/foo and look up the file record
                        nfile   = fname[1:]
                        fid     = RPM_File.find_id(nfile, tid, pid)
                        self.add_flag_records(tid, fid, pid, flags)
                        self.add_symbol_records(tid, fid, pid, symbols)
            os.chdir(current_dir)
        finally:
            logging.debug('Removing temporary directory: %s...' % cpio_dir)
            try:
                shutil.rmtree(cpio_dir)
            except:
                # if we can't remove the directory, recursively chmod and try again
                os.system('chmod -R u+rwx ' + cpio_dir)
                shutil.rmtree(cpio_dir)


    def get_binary_symbols(self, bfile):
        """
        Function to get symbols from a binary file
        """
        symbols = []

        self.rcommon.show_progress()

        nm_output = commands.getoutput('nm -D -g ' + self.rcommon.clean_shell(bfile))
        nm_output = nm_output.split()
        for symbol in nm_output:
            if re.search('^[A-Za-z_]{2}.*', symbol):
                if symbol not in self.excluded_symbols:
                    # dump the __cxa* symbols
                    if not re.search('^__cxa', symbol):
                        symbols.append(symbol)

        return symbols


    def get_binary_flags(self, bfile):
        """
        Function to get binary flags from a file
        """
        # set all bits to their defaults
        flags = {'relro': 0, 'ssp': 0, 'nx': 1, 'pie': 0, 'fortify_source': 0}

        self.rcommon.show_progress()

        readelf_l = commands.getoutput('readelf -l ' + self.rcommon.clean_shell(bfile))
        readelf_d = commands.getoutput('readelf -d ' + self.rcommon.clean_shell(bfile))
        readelf_s = commands.getoutput('readelf -s ' + self.rcommon.clean_shell(bfile))
        readelf_h = commands.getoutput('readelf -h ' + self.rcommon.clean_shell(bfile))

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


    def add_flag_records(self, tid, fid, pid, flags):
        """
        Function to add flag records to the database
        """
        logging.debug('in Binary.add_flag_records(%s, %s, %s, %s)' % (tid, fid, pid, flags))

        logging.debug('flags: %s' % flags)

        try:
            f = RPM_Flags.create(
                tid     = tid,
                pid     = pid,
                fid     = fid,
                relro   = flags['relro'],
                ssp     = flags['ssp'],
                pie     = flags['pie'],
                fortify = flags['fortify_source'],
                nx      = flags['nx']
            )
            logging.debug('Filed Flag with id %d', f.id)
        except Exception, e:
            logging.error('Adding flags for fid %d failed!\n%s', fid, e)


    def add_symbol_records(self, tid, fid, pid, symbols):
        """
        Function to add symbol records to the database
        """
        logging.debug('in Binary.add_symbol_records(%s, %s, %s, %s)' % (tid, fid, pid, symbols))

        for symbol in symbols:
            try:
                s = RPM_Symbols.create(
                    pid     = pid,
                    tid     = tid,
                    fid     = fid,
                    symbols = symbol
                )
                logging.debug('Filed Symbol with id %d', s.id)
            except Exception, e:
                logging.error('Adding symbol for fid %d failed!\n%s', fid, e)


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

        tid = RPM_Tag.get_id(tag)

        if not tid:
            print 'Invalid tag: %s' % tag
            sys.exit(1)

        if type == 'suid':
            db_col = 'is_suid'
        elif type == 'sgid':
            db_col = 'is_sgid'
        else:
            print 'Invalid value, looking for suid or sgid, received: %s' % type
            sys.exit(1)

        sxid_files = RPM_File.get_sxid(tid, db_col)
        if sxid_files:
            for sxid_file in sxid_files:
                print '%s: %s [%s:%s mode %s]' % (sxid_file.package,
                                                  sxid_file.file,
                                                  sxid_file.user,
                                                  sxid_file.group,
                                                  sxid_file.perms)
        else:
            print 'No results found.'
