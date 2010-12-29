#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""
import os, sys, re, commands, logging, tempfile, shutil, datetime
from glob import glob
import rq.db
import rq.basics

class Source:
    """
    Class to handle working with source files
    """

    def __init__(self, db, config, options, rtag, rcommon):
        self.db      = db
        self.config  = config
        self.options = options
        self.rtag    = rtag
        self.rcommon = rcommon

        self.re_srpm    = re.compile(r'\.src\.rpm$')
        self.re_patch   = re.compile(r'\.(diff|dif|patch)(\.bz2|\.gz)?$')
        self.re_tar     = re.compile(r'\.((tar)(\.bz2|\.gz)?|t(gz|bz2?))$')
        self.re_targz   = re.compile(r'\.(tgz|tar\.gz)$')
        self.re_tarbz   = re.compile(r'\.(tbz2?|tar\.bz2)$')
        self.re_patchgz = re.compile(r'\.(patch|diff|dif)(\.gz)$')
        self.re_patchbz = re.compile(r'\.(patch|diff|dif)(\.bz2)$')


    def patch_list(self, file):
        """
        Function to get a list of files that a patch touches
        """
        logging.debug('in patch_list(%s)' % file)

        grep = 'grep'

        if self.re_patchgz.search(file):
            grep = 'zgrep'

        if self.re_patchbz.search(file):
            grep = 'bzgrep'

        list = commands.getoutput(grep + " '^+++' " + self.rcommon.clean_shell(file) + " 2>/dev/null | awk '{print $2}'")

        return(list)


    def tar_list(self, file):
        """
        Function to get a list of files in a tarball
        """
        logging.debug('in tar_list(%s)' % file)

        comp = 'tf'
        if self.re_targz.search(file):
            comp = 'tzf'
        if self.re_tarbz.search(file):
            comp = 'tjf'

        excludes = ''
        for f in self.rcommon.get_file_excludes():
            f = self.fix_excludes(f)

            excludes = '%s --exclude=%s' % (excludes, f)

        command = 'tar -%s "%s" %s 2>/dev/null' % (comp, file.replace(' ', '\ '), excludes)

        (rc, list) = commands.getstatusoutput(command)
        logging.debug('called tar (rc=%s): %s\n%s' % (rc, command, list))

        return(list)


    def fix_excludes(self, file):
        """
        if this is a directory exclude, remove the leading '/' for the tar extract
        """
        if file[0] == '/':
            file = file[1:]

        return(file)


    def get_all_files(self, file):
        """
        Function to get the source and patch files from a SRPM
        """
        logging.debug('in Source.get_all_files(%s)' % file)
        self.get_tar_files(file)
        self.get_patch_files(file)


    def get_tar_files(self, file):
        """
        Function to get the tar files from a SRPM

        cpio --quiet is a GNU-ism and isn't portable
        """
        logging.debug('in Source.get_tar_files(%s)' % file)

        # include the .spec file here; we need it later
        exts = ['*.tar.?z*', '*.tgz', '*.tbz', '*.zip', '*.spec']
        for search in exts:
            command      = 'rpm2cpio "%s" | cpio -i "%s" 2>/dev/null' % (file, search)
            (rc, output) = commands.getstatusoutput(command)
            logging.debug('called cpio (rc=%s): %s' % (rc, command))

    #    if not rc == 0:
    #        logging.critical('Failed to execute rpm2cpio!  Command was: %s\nOutput was:\n(rc: %s) %s\n' % (command, rc, output))
    #        sys.exit(1)


    def get_patch_files(self, file):
        """
        Function to get the patch files from a SRPM
        """
        logging.debug('in Source.get_patch_files(%s)' % file)

        exts = ['*patch*', '*diff*']
        for search in exts:
            command      = 'rpm2cpio "%s" | cpio -i "%s" 2>/dev/null' % (file, search)
            (rc, output) = commands.getstatusoutput(command)
            logging.debug('called cpio (rc=%s): %s' % (rc, output))

    #    if not rc == 0:
    #        logging.critical('Failed to execute rpm2cpio!  Command was: %s\nOutput was:\n(rc: %s) %s\n' % (command, rc, output))
    #        sys.exit(1)


    def query(self, type):
        """
        Function to run the query for source RPMs
        """
        logging.debug('in Source.query(%s)' % type)

        if self.options.tag and not self.rtag.lookup(self.options.tag):
            print 'Tag %s is not a known tag!\n' % self.options.tag
            sys.exit(1)

        if self.options.ignorecase and not self.options.regexp:
            ignorecase = ''
        else:
            ignorecase = 'BINARY'

        if type == 'ctags':
            like_q = self.options.ctags
        if type == 'buildreqs':
            like_q = self.options.buildreqs
        if type == 'files':
            like_q = self.options.query

        if self.options.regexp:
            match_type = 'regexp'
        else:
            match_type = 'substring'

        if type == 'ctags':
            query   = "SELECT DISTINCT p_tag, p_package, p_version, p_release, p_date, s_type, s_file, c_file, c_type, c_extra, c_line FROM ctags JOIN sources ON (sources.s_record = ctags.s_record) JOIN packages ON (packages.p_record = ctags.p_record) WHERE %s c_name " % ignorecase
            orderby = "c_file"
            match_t = 'Ctags data'
        elif type == 'buildreqs':
            query   = "SELECT DISTINCT p_tag, p_package, p_version, p_release, p_date, b_req FROM buildreqs JOIN packages ON (packages.p_record = buildreqs.p_record) WHERE %s b_req " % ignorecase
            match_t = '.spec BuildRequires'
        else:
            query   = "SELECT DISTINCT p_tag, p_package, p_version, p_release, p_date, s_type, s_file, f_file FROM files JOIN sources ON (sources.s_record = files.s_record) JOIN packages ON (packages.p_record = files.p_record) WHERE %s f_file " % ignorecase
            orderby = "f_file"
            match_t = 'files'

        if self.options.regexp:
            query = query + "RLIKE '" + self.db.sanitize_string(like_q) + "'"
        else:
            query = query + "LIKE '%" + self.db.sanitize_string(like_q) + "%'"

        if self.options.sourceonly:
            query = query + " AND s_type = 'S'"

        if self.options.tag:
            query = query + " AND p_tag = '" + self.db.sanitize_string(self.options.tag) + "'"

        if type == 'buildreqs':
            query   = '%s ORDER BY p_tag, p_package' % query
        else:
            query   = "%s ORDER BY p_tag, p_package, s_type, s_file, %s" % (query, orderby)

        if not self.options.quiet:
            print 'Searching database records for %s match on %s ("%s")' % (match_type, match_t, like_q)

        result = self.db.fetch_all(query)
        if result:
            if self.options.count:
                if self.options.quiet:
                    print len(result)
                else:
                    if self.options.tag:
                        print '%d match(es) in database for tag (%s) and %s ("%s")' % (len(result), self.options.tag, match_type, like_q)
                    else:
                        print '%d match(es) in database for %s ("%s")' % (len(result), match_type, like_q)
                return

            ltag = ''
            lsrc = ''
            for row in result:
                # for readability
                fromdb_tag   = row['p_tag']
                fromdb_rpm   = row['p_package']
                fromdb_ver   = row['p_version']
                fromdb_rel   = row['p_release']
                fromdb_date  = row['p_date']
                if type == 'buildreqs':
                    fromdb_type  = 'S'
                    fromdb_breq  = row['b_req']
                else:
                    fromdb_type  = row['s_type']
                    fromdb_file  = row['s_file']
                    fromdb_sfile = row[orderby]
                if type == 'ctags':
                    fromdb_ctype  = row['c_type']
                    fromdb_cline  = row['c_line']
                    fromdb_cextra = row['c_extra']

                if not ltag == fromdb_tag:
                    print '\n\nResults in Tag: %s\n%s\n' % (fromdb_tag, '='*40)
                    ltag = fromdb_tag

                if self.options.debug:
                    print row
                else:
                    srpm  = '%s-%s-%s' % (fromdb_rpm, fromdb_ver, fromdb_rel)
                    stype = 'source'

                    if self.options.quiet:
                        lsrc = srpm
                        sys.stdout.write('%s\n' % srpm)
                        sys.stdout.flush()
                    else:
                        if fromdb_type == 'P':
                            stype = 'patch'
                        if self.options.extrainfo:
                            rpm_date = datetime.datetime.fromtimestamp(float(fromdb_date))
                            print '\n%-16s%-27s%-9s%s' % ("Package:", fromdb_rpm, "Date:", rpm_date.strftime('%a %b %d %H:%M:%S %Y'))
                            print '%-16s%-27s%-9s%s' % ("Version:", fromdb_ver, "Release:", fromdb_rel)
                            print '%-16s%-30s' % (stype.title() + " File:", fromdb_file)
                            print '%-16s%-30s' % ("Source Path:", fromdb_sfile)
                        else:
                            if type == 'ctags':
                                sys.stdout.write('%s: (%s) %s\n\tFound matching %s in %s:%s: %s\n' % (srpm, stype, fromdb_file, fromdb_ctype, fromdb_sfile, fromdb_cline, fromdb_cextra))
                            elif type == 'buildreqs':
                                sys.stdout.write('%s: %s\n' % (srpm, fromdb_breq))
                            else:
                                sys.stdout.write('%s: (%s) %s: %s\n' % (srpm, stype, fromdb_file, fromdb_sfile))

        else:
            if self.options.tag:
                print 'No matches in database for tag (%s) and %s ("%s")' % (self.options.tag, match_type, like_q)
            else:
                print 'No matches in database for %s ("%s")' % (match_type, like_q)


    def examine(self, file):
        """
        Examine a src.rpm and output the details
        """
        logging.debug('in Source.examine(%s)' % file)

        self.rcommon.file_rpm_check(file)

        file = path = os.path.abspath(file)

        print 'Examining %s...\n' % file

        # stage 1, list the rpm content
        src_list = self.rcommon.rpm_list(file, raw=True)
        print 'SRPM Contents:\n%s\n' % src_list

        file_list = self.rcommon.rpm_list(file)

        cpio_dir = tempfile.mkdtemp()
        try:
            current_dir = os.getcwd()
            os.chdir(cpio_dir)

            # stage 2, list patched files
            if self.options.patch:
                self.get_patch_files(file)
                for x in file_list.keys():
                    if self.re_patch.search(file_list[x]['file']):
                        plist = self.patch_list(file_list[x]['file'])
                        print 'Patch file %s modifies:\n%s\n' % (file_list[x]['file'], plist)

            # stage 3, list the tarball contents
            if not self.options.skiptar:
                self.get_tar_files(file)
                for y in file_list.keys():
                    if self.re_tar.search(file_list[y]['file']):
                        tlist = self.tar_list(file_list[y]['file'])
                        print 'Tarfile %s contents:\n%s\n' % (file_list[y]['file'], tlist)

            os.chdir(current_dir)
        finally:
            logging.debug('Removing temporary directory: %s...' % cpio_dir)
            shutil.rmtree(cpio_dir)


    def showinfo(self):
        """
        Display all known information on a srpm
        """
        logging.debug('in Source.showinfo()')

        if self.options.tag and not self.rtag.lookup(self.options.tag):
            print 'Tag %s is not a known tag!\n' % self.options.tag
            sys.exit(1)

        print 'Displaying all known information on srpm "%s"\n' % self.options.showinfo

        if self.options.tag:
            qtag = " AND p_tag = '%s'" % self.db.sanitize_string(self.options.tag)
        else:
            qtag = ''

        query = "SELECT * FROM packages JOIN tags ON (packages.t_record = tags.t_record) WHERE p_package = '%s' %s ORDER BY p_tag" % (self.db.sanitize_string(self.options.showinfo), qtag)

        result = self.db.fetch_all(query)
        if not result:
            print 'No matches found for package %s' % srpm
            sys.exit(0)

        for row in result:
            print 'Results for package %s-%s-%s' % (row['p_package'], row['p_version'], row['p_release'])
            print '  Tag: %-20s Source path: %s' % (row['p_tag'], row['path'])

            query   = "SELECT s_file FROM sources WHERE p_record = '%s' ORDER BY s_type, s_file ASC" % row['p_record']
            results = self.db.fetch_all(query)
            if results:
                print ''
                print '  Source RPM contains the following source files:'
                for xrow in results:
                    print '  %s' % xrow['s_file']

            query   = "SELECT b_req FROM buildreqs WHERE p_record = '%s' ORDER BY b_req ASC" % row['p_record']
            results = self.db.fetch_all(query)
            if results:
                print ''
                print '  Source RPM has the following BuildRequires:'
                for xrow in results:
                    print '  %s' % xrow['b_req']
            print ''


    def add_records(self, tag_id, record, file_list):
        """
        Function to add source records
        """
        logging.debug('in Source.add_records(%s, %s, %s)' % (tag_id, record, file_list))

        for x in file_list.keys():
            # remove any possible paths from source files; may be due to rpm5
            sfile = file_list[x]['file'].split('/')[-1]
            logging.debug('processing source: %s ' % sfile)
            self.rcommon.show_progress()
            stype = ''

            if self.re_patch.search(sfile):
                stype = 'P'
            if self.re_tar.search(sfile):
                stype = 'S'

            # we only care about source and patch files, nothing else
            if stype == '':
                continue

            if self.options.verbose:
                print 'Source: %s, Type: %s' % (sfile, stype)
            query  = "INSERT INTO sources (t_record, p_record, s_type, s_file) VALUES ('%s', '%s', '%s', '%s')" % (tag_id, record, stype, self.db.sanitize_string(sfile.strip()))
            result = self.db.do_query(query)


    def add_file_records(self, tag_id, record, file_list):
        """
        Function to add all source file records
        """
        logging.debug('in Source.add_file_records(%s, %s, %s)' % (tag_id, record, file_list))

        for x in file_list.keys():
            good_src = False
            # file_list may contain paths, so strip them; may be due to rpm5
            sfile    = file_list[x]['file'].split('/')[-1]
            logging.debug('processing file: %s' % sfile) ### DEBUG

            if self.re_patch.search(sfile):
                flist    = self.patch_list(sfile)
                good_src = True

            if self.re_tar.search(sfile):
                flist    = self.tar_list(sfile)
                good_src = True

            # only proceed for tarballs and patches
            if good_src:
                logging.debug('found good file to process: %s' % sfile)
                files = flist.split()

                # get the s_record for this source from the db
                query   = "SELECT s_record FROM sources WHERE p_record = '%s' AND s_file = '%s'" % (record, self.db.sanitize_string(sfile))
                db_srec = self.db.fetch_one(query)
                if not db_srec:
                    logging.critical('adding files from %s failed...' % sfile)
                    sys.exit(1)

                for dfile in files:
                    break_loop = False
                    if dfile.endswith('/'):     # skip directories
                        pass
                    else:
                        for exclude in self.rcommon.get_file_excludes():
                            # make sure we don't include any files in our exclude list
                            if re.search(exclude, dfile):
                                logging.debug('found unwanted entry: %s' % dfile)
                                break_loop = True
                        if break_loop == True:
                            pass
                        else:
                            self.rcommon.show_progress()
                            if self.options.verbose:
                                print 'File: %s' % dfile
                            query  = "INSERT INTO files (t_record, p_record, s_record, f_file) VALUES ('%s', '%s', '%s', '%s')" % (tag_id, record, db_srec, self.db.sanitize_string(dfile))
                            result = self.db.do_query(query)
            else:
                logging.debug('unwilling to process: %s' % sfile)


    def add_ctag_records(self, tag_id, record, cpio_dir):
        """
        Function to run ctags against an unpacked source directory
        and insert records into the database
        """
        logging.debug('in Source.add_ctag_records(%s, %s, %s)' % (tag_id, record, cpio_dir))

        # this is likely a double chdir, but let's make sure we're in the right place
        # so we don't have to strip out the path from the ctags output
        os.chdir(cpio_dir)

        # first, identify and expand any tarballs found:
        for file in os.listdir(cpio_dir):
            if self.re_tar.search(file):
                # get the s_record for this source from the db
                query   = "SELECT s_record FROM sources WHERE p_record = '%s' AND s_file = '%s'" % (record, self.db.sanitize_string(file))
                db_srec = self.db.fetch_one(query)
                if not db_srec:
                    logging.critical('!!!!! adding files from %s failed...' % file)
                    # don't bail, it's logged, continue
                    #sys.exit(1)
                    continue

                comp = 'xf'
                if self.re_targz.search(file):
                    comp = 'xzf'
                if self.re_tarbz.search(file):
                    comp = 'xjf'

                excludes = ''
                for f in self.rcommon.get_file_excludes():
                    f = self.fix_excludes(f)

                    excludes = '%s --exclude=%s' % (excludes, f)

                tmpdir  = tempfile.mkdtemp()
                command = 'tar -%s "%s" -C %s %s 2>/dev/null' % (comp, file.replace(' ', '\ '), tmpdir, excludes)

                (rc, list) = commands.getstatusoutput(command)
                logging.debug('called tar (rc=%s): %s\n%s' % (rc, command, list))

                os.chdir(tmpdir)

                # some packages contain files that are r--r--r-- which prevents
                # us from cleanly removing the directory, so do a recursive
                # chmod first
                command = "chmod -R u+rwx ."
                (rc, output) = commands.getstatusoutput(command)
                logging.debug('called chmod (rc=%s): %s' % (rc, command))

                command = "ctags -x -R -f - ."
                (rc, output) = commands.getstatusoutput(command)
                logging.debug('called ctags (rc=%s): %s' % (rc, command))

                for tag in output.split('\n'):
                    try:
                        (name, type, line, path, extra) = tag.split(None, 4)
                    except:
                        continue

                    # only store some ctags info, not all of it
                    wanted = ['function', 'macro', 'subroutine', 'class', 'method']
                    if type in wanted:
                        self.rcommon.show_progress()
                        query = "INSERT INTO ctags (t_record, p_record, s_record, c_name, c_type, c_line, c_file, c_extra) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (
                            tag_id,
                            record,
                            db_srec,
                            self.db.sanitize_string(name),
                            self.db.sanitize_string(type),
                            self.db.sanitize_string(line),
                            self.db.sanitize_string(path),
                            self.db.sanitize_string(extra))
                        result = self.db.do_query(query)
                        #print '%s\n' % query
                os.chdir(cpio_dir)

                # have to put this in a try statement; who puts files and directories in a tarball all mode 0200?!?
                try:
                    logging.debug('attempting to remove temporary directory: %s' % tmpdir)
                    shutil.rmtree(tmpdir)
                except:
                    logging.critical('Unable to remove directory: %s, most likely because the tarball has idiotic permissions' % tmpdir)


    def add_buildreq_records(self, tag_id, record, cpio_dir):
        """
        Get the build requirements for this package from the spec file
        """
        logging.debug('in Source.add_buildreq_records(%s, %s, %s)' % (tag_id, record, cpio_dir))

        specfile = ''
        r        = []

        # this is likely a double chdir, but let's make sure we're in the right place
        # so we don't have to strip out the path from the ctags output
        os.chdir(cpio_dir)

        for file in os.listdir(cpio_dir):
            if re.search('.spec', file):
                specfile = file

        if specfile == '':
            logging.critical('No specfile found, unable to process buildrequirements')
            sys.exit(1)

        for line in open(specfile):
            reqs  = {}
            count = 0
            if re.search('^buildrequire', line.lower()):
                words = line.split()
                for c in words:
                    if not c.startswith('Build'):
                        reqs[count] = c.strip()
                        count += 1

            # if there is more than one item on this line
            if len(reqs) > 1:
                skip = 0
                for x in reqs.keys():
                    # iterate through each item on the line, if this item includes
                    # the >, <, or = characters, create our requirement string
                    # based on the N+1 and N+2 words
                    new = ''

                    if skip == 0 and x+1 in reqs.keys():
                        if re.search('(>|<|=)', reqs[x+1]):
                            # construct the new string based on N+1 (equality) and N+2 (nvr)
                            new = '%s %s %s' % (reqs[x], reqs[x+1], reqs[x+2])
                            # tell it to skip the next item since we grabbed it
                            skip += 1
                        else:
                            new = reqs[x]

                    elif skip == 0:
                        # there is no following equality string, so take it as it is
                        new = reqs[x]

                    else:
                        if skip == 1:
                            # skipped the equality, so skip one more (nvr)
                            skip += 1
                        else:
                            # skip would be 2, so reset the counter
                            skip = 0

                    if new.endswith(','):
                        # multi-item dependencies, uses ',' as a delimiter so remove it
                        new = new[:-1]

                    # we want to make sure we don't list the same thing twice, we also don't want blank items
                    if not new in r:
                        if new != '':
                            r.append(new)

            elif len(reqs) == 1:
                # exactly one item on this line, put it in as-is
                if reqs[0].endswith(','):
                    new = reqs[0][:-1]
                else:
                    new = reqs[0]
                r.append(new)

        for require in r:
            # now iterate through each item and add them to the database
            self.rcommon.show_progress()
            # record == p_record
            query = "INSERT INTO buildreqs (t_record, p_record, b_req) VALUES ('%s', '%s', '%s')" % (
                            tag_id,
                            record,
                            self.db.sanitize_string(require))
            result = self.db.do_query(query)
            #print '%s\n' % query


    def rpm_add_directory(self, tag, path, updatepath):
        """
        Function to import a directory full of source RPMs
        """
        logging.debug('in Source.rpm_add_directory(%s, %s, %s)' % (tag, path, updatepath))

        if not os.path.isdir(path):
            print 'Path (%s) is not a valid directory!' % path
            sys.exit(1)

        if not os.path.isdir(updatepath):
            print 'Path (%s) is not a valid directory!' % updatepath
            sys.exit(1)

        file_list = glob(path + "/*.src.rpm")
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
                next

            if not self.re_srpm.search(file):
                print 'File %s is not a source rpm!\n' % file
                next

            self.record_add(tag_id, file)


    def record_add(self, tag_id, file, update=0):
        """
        Function to add a record to the database
        """
        logging.debug('in Source.record_add(%s, %s, %d)' % (tag_id, file, update))

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

        logging.debug('Add source records for package record: %s' % record)
        self.add_records(tag_id, record, file_list)
        cpio_dir = tempfile.mkdtemp()

        try:
            current_dir = os.getcwd()
            os.chdir(cpio_dir)
            self.get_all_files(file)
            self.add_file_records(tag_id, record, file_list)
            self.add_ctag_records(tag_id, record, cpio_dir)
            self.add_buildreq_records(tag_id, record, cpio_dir)
            os.chdir(current_dir)
        finally:
            logging.debug('Removing temporary directory: %s...' % cpio_dir)
            shutil.rmtree(cpio_dir)

        if self.options.progress:
            sys.stdout.write('\n')


    def package_add_record(self, tag_id, file, update=0):
        """
        Function to add a package record
        """
        logging.debug('in Source.package_add_record(%s, %s, %d)' % (tag_id, file, update))

        fname   = os.path.basename(file)
        rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{BUILDTIME}' " + self.rcommon.clean_shell(file))
        tlist   = rpmtags.split('|')
        logging.debug("tlist is %s " % tlist)
        package = tlist[0].strip()
        version = tlist[1].strip()
        release = tlist[2].strip()
        pdate   = tlist[3].strip()

        query = "SELECT tag FROM tags WHERE t_record = '%s' LIMIT 1" % tag_id
        tag   = self.db.fetch_one(query)

        query = "SELECT t_record, p_package, p_version, p_release FROM packages WHERE t_record = '%s' AND p_package = '%s' AND p_version = '%s' AND p_release = '%s'" % (
            tag_id,
            self.db.sanitize_string(package),
            self.db.sanitize_string(version),
            self.db.sanitize_string(release))
        result = self.db.fetch_all(query)

        if result:
            print 'File %s-%s-%s is already in the database under tag %s' % (package, version, release, tag)
            return(0)

        ## TODO: we shouldn't have to have p_tag here as t_record has the same info, but it
        ## sure makes it easier to sort alphabetically and I'm too lazy for the JOINs right now

        query  = "INSERT INTO packages (t_record, p_tag, p_package, p_version, p_release, p_date, p_fullname, p_update) VALUES ('%s', '%s', '%s', '%s', '%s', '%s', %d)" % (
            tag_id,
            self.db.sanitize_string(tag),
            self.db.sanitize_string(package),
            self.db.sanitize_string(version),
            self.db.sanitize_string(release),
            self.db.sanitize_string(pdate),
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
