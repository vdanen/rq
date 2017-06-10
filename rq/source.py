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
from app.models import SRPM_Ctag, SRPM_Tag, SRPM_BuildRequires, SRPM_Source, SRPM_Package, SRPM_File, SRPM_AlreadySeen

class Source:
    """
    Class to handle working with source files
    """

    def __init__(self, config, options, rtag, rcommon):
        self.config     = config
        self.options    = options
        self.rtag       = rtag
        self.rcommon    = rcommon

        self.re_srpm    = re.compile(r'\.src\.rpm$')
        self.re_patch   = re.compile(r'\.(diff|dif|patch)(\.bz2|\.gz)?$')
        self.re_tar     = re.compile(r'\.((tar)(\.bz2|\.gz)?|t(gz|bz2?))$')
        self.re_targz   = re.compile(r'\.(tgz|tar\.gz)$')
        self.re_tarbz   = re.compile(r'\.(tbz2?|tar\.bz2)$')
        self.re_patchgz = re.compile(r'\.(patch|diff|dif)(\.gz)$')
        self.re_patchbz = re.compile(r'\.(patch|diff|dif)(\.bz2)$')

        self.ctag_map   = {'function'  : 0,
                           'subroutine': 1,
                           'class'     : 2,
                           'method'    : 3}

        # caches
        self.breq_cache = {}


    def patch_list(self, patchfile):
        """
        Function to get a list of files that a patch touches
        """
        logging.debug('in patch_list(%s)' % patchfile)

        grep = 'grep'

        if self.re_patchgz.search(patchfile):
            grep = 'zgrep'

        if self.re_patchbz.search(patchfile):
            grep = 'bzgrep'

        list = commands.getoutput(grep + " '^+++' " + self.rcommon.clean_shell(patchfile) + " 2>/dev/null | awk '{print $2}'")

        return list


    def tar_list(self, tarfile):
        """
        Function to get a list of files in a tarball
        """
        logging.debug('in tar_list(%s)' % tarfile)

        comp = 'tf'
        if self.re_targz.search(tarfile):
            comp = 'tzf'
        if self.re_tarbz.search(tarfile):
            comp = 'tjf'

        excludes = ''
        for f in self.rcommon.get_file_excludes():
            f = self.fix_excludes(f)

            excludes = '%s --exclude=%s' % (excludes, f)

        command = 'tar -%s "%s" %s 2>/dev/null' % (comp, tarfile.replace(' ', '\ '), excludes)

        (rc, list) = commands.getstatusoutput(command)
        logging.debug('called tar (rc=%s): %s\n%s' % (rc, command, list))

        return list


    def fix_excludes(self, fname):
        """
        if this is a directory exclude, remove the leading '/' for the tar extract
        """
        if fname[0] == '/':
            fname = fname[1:]

        return fname


    def get_all_files(self, srpm):
        """
        Function to get the source and patch files from a SRPM
        """
        logging.debug('in Source.get_all_files(%s)' % srpm)
        self.get_tar_files(srpm)
        self.get_patch_files(srpm)


    def get_tar_files(self, srpm):
        """
        Function to get the tar files from a SRPM

        cpio --quiet is a GNU-ism and isn't portable
        """
        logging.debug('in Source.get_tar_files(%s)' % srpm)

        # include the .spec file here; we need it later
        exts = ['*.tar.?z*', '*.tgz', '*.tbz', '*.zip', '*.spec']
        for search in exts:
            command      = 'rpm2cpio "%s" | cpio -i "%s" 2>/dev/null' % (srpm, search)
            (rc, output) = commands.getstatusoutput(command)
            logging.debug('called cpio (rc=%s): %s' % (rc, command))

    #    if not rc == 0:
    #        logging.critical('Failed to execute rpm2cpio!  Command was: %s\nOutput was:\n(rc: %s) %s\n' % (command, rc, output))
    #        sys.exit(1)


    def get_patch_files(self, srpm):
        """
        Function to get the patch files from a SRPM
        """
        logging.debug('in Source.get_patch_files(%s)' % srpm)

        exts = ['*patch*', '*diff*']
        for search in exts:
            command      = 'rpm2cpio "%s" | cpio -i "%s" 2>/dev/null' % (srpm, search)
            (rc, output) = commands.getstatusoutput(command)
            logging.debug('called cpio (rc=%s): %s' % (rc, output))

    #    if not rc == 0:
    #        logging.critical('Failed to execute rpm2cpio!  Command was: %s\nOutput was:\n(rc: %s) %s\n' % (command, rc, output))
    #        sys.exit(1)


    def query(self, qtype):
        # TODO: we need to add options to only search updates, only search releases, or omit either/or
        # or we need to decide to filter out release packages and only show updates if both exist (maybe
        # default to showing only updates with a --include-release option or something)
        """
        Function to run the query for source RPMs
        """
        logging.debug('in Source.query(%s)' % qtype)

        t = self.rtag.lookup(self.options.tag)
        if self.options.tag and not t:
            print 'Tag %s is not a known tag!\n' % self.options.tag
            sys.exit(1)
        elif self.options.tag and t:
            tid = t['id']
        else:
            tid = ''

        like_q  = ''
        match_t = ''
        if qtype == 'ctags':
            match_t = 'Ctags data'
            like_q  = self.options.ctags
        if qtype == 'buildreqs':
            match_t = '.spec BuildRequires'
            like_q  = self.options.buildreqs
        if qtype == 'files':
            match_t = 'files'
            like_q  = self.options.query

        if self.options.regexp:
            match_type = 'regexp'
        else:
            match_type = 'substring'

        if not self.options.quiet:
            print 'Searching database records for %s match on %s ("%s")' % (match_type, match_t, like_q)

        result = None
        if qtype == 'ctags':
            if self.options.regexp:
                if self.options.tag:
                    result = SRPM_Ctag.select().where((SRPM_Ctag.name.regexp(like_q)) & (SRPM_Ctag.tid == tid)).order_by(SRPM_Ctag.file.asc())
                else:
                    result = SRPM_Ctag.select().where(SRPM_Ctag.name.regexp(like_q)).order_by(SRPM_Ctag.file.asc())
            else:
                if self.options.tag:
                    result = SRPM_Ctag.select().where((SRPM_Ctag.name.contains(like_q)) & (SRPM_Ctag.tid == tid)).order_by(SRPM_Ctag.file.asc())
                else:
                    result = SRPM_Ctag.select().where(SRPM_Ctag.name.contains(like_q)).order_by(SRPM_Ctag.file.asc())

        elif qtype == 'buildreqs':
            if self.options.regexp:
                if self.options.tag:
                    result = SRPM_BuildRequires.select().where((SRPM_BuildRequires.name.regexp(like_q)) & (SRPM_BuildRequires.tid == tid)).order_by(SRPM_BuildRequires.name.asc())
                else:
                    result = SRPM_BuildRequires.select().where(SRPM_BuildRequires.name.regexp(like_q)).order_by(SRPM_BuildRequires.name.asc())
            else:
                if self.options.tag:
                    result = SRPM_BuildRequires.select().where((SRPM_BuildRequires.name.contains(like_q)) & (SRPM_BuildRequires.tid == tid)).order_by(SRPM_BuildRequires.name.asc())
                else:
                    result = SRPM_BuildRequires.select().where(SRPM_BuildRequires.name.contains(like_q)).order_by(SRPM_BuildRequires.name.asc())

        elif qtype == 'files':
            if self.options.regexp:
                if self.options.tag:
                    result = SRPM_File.select().where((SRPM_File.file.regexp(like_q)) & (SRPM_File.tid == tid)).order_by(SRPM_File.file.asc())
                else:
                    result = SRPM_File.select().where(SRPM_File.file.regexp(like_q)).order_by(SRPM_File.file.asc())
            else:
                if self.options.tag:
                    result = SRPM_File.select().where((SRPM_File.file.contains(like_q)) & (SRPM_File.tid == tid)).order_by(SRPM_File.file.asc())
                else:
                    result = SRPM_File.select().where(SRPM_File.file.contains(like_q)).order_by(SRPM_File.file.asc())


        #TODO: need to make joins work somehow and reduce the above; need to be able to look for sources only
        #if self.options.sourceonly:
        #    query = query + " AND s_type = 'S'"

        #if type == 'buildreqs':
        #    query   = '%s ORDER BY p_tag, p_package' % query
        #else:
        #    query   = "%s ORDER BY p_tag, p_package, s_type, s_file, %s" % (query, orderby)


        # TODO: if the match is a source file (e.g. a patch) we should constrain on it's uniqueness; for instance
        # a search on mgetty-1.1.33-167830.patch results in:
        #
        # mgetty-1.1.36-7.fc14: (patch) mgetty-1.1.33-167830.patch: mgetty-1.1.36/login.c
        # mgetty-1.1.36-7.fc14: (patch) mgetty-1.1.33-167830.patch: mgetty-1.1.36/mgetty.c
        #
        # the match here is on s_file, not f_file, and since we don't care about f_file we should do two things:
        #
        # 1) remove f_file from the output
        # 2) not duplicate the information show (just show: mgetty-1.1.36-7.fc14: (patch) mgetty-1.1.33-167830.patch)
        #
        # we could do this with different command-line options to search either files or patches, but then we have
        # a lot of silly options, so we can make the program smart enough to figure this out eventually
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
            last = ''
            for row in result:
                utype = ''
                # for readability
                package = SRPM_Package.get(SRPM_Package.id == row.pid)
                r_tag   = SRPM_Tag.get_tag(row.tid)
                r_rpm   = package.package
                r_ver   = package.version
                r_rel   = package.release
                r_date  = package.date

                # defaults, so nothing is undeclared
                r_ctype  = ''
                r_cline  = ''
                r_cextra = ''
                r_breq   = ''

                if qtype == 'buildreqs':
                    r_type = 'S'
                    r_breq = row.name
                else:
                    source  = SRPM_Source.get(SRPM_Source.id == row.sid)
                    r_type  = source.stype
                    r_file  = row.file
                    r_sfile = source.file

                if qtype == 'ctags':
                    r_ctype  = [k for k, v in self.ctag_map.iteritems() if v == row.ctype][0]
                    r_cline  = row.line
                    r_cextra = row.extra

                if row.update == 1:
                    utype = '[update] '

                if not ltag == r_tag:
                    print '\n\nResults in Tag: %s\n%s\n' % (r_tag, '='*40)
                    ltag = r_tag

                if self.options.debug:
                    print vars(row)
                else:
                    srpm  = '%s-%s-%s' % (r_rpm, r_ver, r_rel)
                    stype = 'source'

                    if self.options.quiet:
                        print srpm
                    else:
                        if r_type == 'P':
                            stype = 'patch'
                        if self.options.extrainfo:
                            rpm_date = datetime.datetime.fromtimestamp(float(r_date))
                            print '\n%-16s%-27s%-9s%s' % ("Package:", r_rpm, "Date:", rpm_date.strftime('%a %b %d %H:%M:%S %Y'))
                            print '%-16s%-27s%-9s%s' % ("Version:", r_ver, "Release:", r_rel)
                            print '%-16s%-30s' % (stype.title() + " File:", r_file)
                            print '%-16s%-30s' % ("Source Path:", r_sfile)
                        else:
                            if qtype == 'ctags':
                                if r_file != last:
                                    print '%s: (%s) %s' % (srpm, stype, r_file)
                                print '\tFound matching %s in %s:%s: %s' % (r_ctype, r_sfile, r_cline, r_cextra)
                            elif qtype == 'buildreqs':
                                print '%s: %s' % (srpm, r_breq)
                            else:
                                print '%s%s: (%s) %s: %s' % (utype, srpm, stype, r_file, r_sfile)

                if qtype == 'ctags':
                    last = r_file

        else:
            if self.options.tag:
                print 'No matches in database for tag (%s) and %s ("%s")' % (self.options.tag, match_type, like_q)
            else:
                print 'No matches in database for %s ("%s")' % (match_type, like_q)


    def examine(self, srpm):
        """
        Examine a src.rpm and output the details
        """
        logging.debug('in Source.examine(%s)' % srpm)

        self.rcommon.file_rpm_check(srpm)

        srpm = os.path.abspath(srpm)

        print 'Examining %s...\n' % srpm

        # stage 1, list the rpm content
        src_list = self.rcommon.rpm_list(srpm, raw=True)
        print 'SRPM Contents:\n%s\n' % src_list

        file_list = self.rcommon.rpm_list(srpm)

        cpio_dir = tempfile.mkdtemp()
        try:
            current_dir = os.getcwd()
            os.chdir(cpio_dir)

            # stage 2, list patched files
            if self.options.patch:
                self.get_patch_files(srpm)
                for x in file_list.keys():
                    if self.re_patch.search(file_list[x]['file']):
                        plist = self.patch_list(file_list[x]['file'])
                        print 'Patch file %s modifies:\n%s\n' % (file_list[x]['file'], plist)

            # stage 3, list the tarball contents
            if not self.options.skiptar:
                self.get_tar_files(srpm)
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

        t = self.rtag.lookup(self.options.tag)
        if self.options.tag and not t:
            print 'Tag %s is not a known tag!\n' % self.options.tag
            sys.exit(1)
        elif self.options.tag and t:
            tid = t['id']

        srpm = self.options.showinfo
        print 'Displaying all known information on srpm "%s"\n' % srpm

        if self.options.tag:
            result = SRPM_Package.select().where((SRPM_Package.package == srpm) & (SRPM_Package.tid == tid)).order_by(SRPM_Package.tid.asc())
        else:
            result = SRPM_Package.select().where(SRPM_Package.package == srpm).order_by(SRPM_Package.tid.asc())

        if not result:
            print 'No matches found for package %s' % srpm
            sys.exit(0)

        for row in result:
            tag = SRPM_Tag.get(SRPM_Tag.id == row.tid)
            print 'Results for package %s-%s-%s' % (row.package, row.version, row.release)
            print '  Tag: %-20s Source path: %s' % (tag.tag, tag.path)

            results = SRPM_Source.select().where(SRPM_Source.pid == row.id).order_by(SRPM_Source.stype.desc())
            if results:
                print ''
                print '  Source RPM contains the following source files:'
                for xrow in results:
                    print '  %s' % xrow.file

            results = SRPM_BuildRequires.select().where(SRPM_BuildRequires.pid == row.id).order_by(SRPM_BuildRequires.name.asc())
            if results:
                print ''
                print '  Source RPM has the following BuildRequires:'
                for xrow in results:
                    print '  %s' % xrow.name
            print ''


    def add_records(self, tid, pid, file_list):
        """
        Function to add source records
        """
        logging.debug('in Source.add_records(%s, %s, %s)' % (tid, pid, file_list))

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
            try:
                s = SRPM_Source.create(
                    tid   = tid,
                    pid   = pid,
                    stype = stype,
                    file  = sfile.strip()
                )
                logging.debug('Filed Source with id %d', s.id)
            except Exception, e:
                logging.error('Adding source file %s failed!\n%s', file, e)


    def add_file_records(self, tid, pid, file_list):
        """
        Function to add all source file records
        """
        logging.debug('in Source.add_file_records(%s, %s, %s)' % (tid, pid, file_list))

        for x in file_list.keys():
            good_src = False
            # file_list may contain paths, so strip them; may be due to rpm5
            sfile    = file_list[x]['file'].split('/')[-1]
            logging.debug('processing file: %s' % sfile)

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
                sid = SRPM_Source.find_id(pid, sfile)
                if not sid:
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
                        if break_loop:
                            pass
                        else:
                            self.rcommon.show_progress()
                            if self.options.verbose:
                                print 'File: %s' % dfile
                            try:
                                f = SRPM_File.create(
                                    tid  = tid,
                                    pid  = pid,
                                    sid  = sid,
                                    file = dfile
                                )
                                logging.debug('Filed File with id %d', f.id)
                            except Exception, e:
                                logging.error('Adding file %s failed!\n%s', dfile, e)

            else:
                logging.debug('unwilling to process: %s' % sfile)


    def add_ctag_records(self, tid, pid, cpio_dir):
        """
        Function to run ctags against an unpacked source directory
        and insert records into the database
        """
        logging.debug('in Source.add_ctag_records(%s, %s, %s)' % (tid, pid, cpio_dir))

        # this is likely a double chdir, but let's make sure we're in the right place
        # so we don't have to strip out the path from the ctags output
        os.chdir(cpio_dir)

        # first, identify and expand any tarballs found:
        for fname in os.listdir(cpio_dir):
            if self.re_tar.search(fname):
                # get the s_record for this source from the db
                sid = SRPM_Source.find_id(pid, fname)
                if not sid:
                    logging.critical('!!!!! adding files from %s failed...' % fname)
                    # don't bail, it's logged, continue
                    #sys.exit(1)
                    continue

                comp = 'xf'
                if self.re_targz.search(fname):
                    comp = 'xzf'
                if self.re_tarbz.search(fname):
                    comp = 'xjf'

                excludes = ''
                for f in self.rcommon.get_file_excludes():
                    f = self.fix_excludes(f)

                    excludes = '%s --exclude=%s' % (excludes, f)

                tmpdir  = tempfile.mkdtemp()
                command = 'tar -%s "%s" -C %s %s 2>/dev/null' % (comp, fname.replace(' ', '\ '), tmpdir, excludes)

                (rc, olist) = commands.getstatusoutput(command)
                logging.debug('called tar (rc=%s): %s\n%s' % (rc, command, olist))

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
                        (name, ctype, line, path, extra) = tag.split(None, 4)
                    except:
                        continue

                    # only store some ctags info, not all of it
                    if ctype in self.ctag_map:
                        self.rcommon.show_progress()
                        try:
                            c = SRPM_Ctag.create(
                                tid   = tid,
                                pid   = pid,
                                sid   = sid,
                                name  = name,
                                ctype = self.ctag_map[ctype],
                                line  = line,
                                file  = path,
                                extra = extra
                            )
                            logging.debug('Filed Ctag with id %d', c.id)
                        except Exception, e:
                            logging.error('Adding ctag %s for file %s failed!\n%s', name, fname, e)

                os.chdir(cpio_dir)

                # make sure this is empty or it will eat lots of memory
                output = None

                logging.debug('Removing temporary directory: %s...' % tmpdir)
                try:
                    shutil.rmtree(tmpdir)
                except:
                    # if we can't remove the directory, recursively chmod and try again
                    os.system('chmod -R u+rwx ' + tmpdir)
                    shutil.rmtree(tmpdir)


    def add_buildreq_records(self, tid, pid, cpio_dir):
        """
        Get the build requirements for this package from the spec file
        """
        logging.debug('in Source.add_buildreq_records(%s, %s, %s)' % (tid, pid, cpio_dir))

        specfile = ''
        r        = []

        # this is likely a double chdir, but let's make sure we're in the right place
        # so we don't have to strip out the path from the ctags output
        os.chdir(cpio_dir)

        for fname in os.listdir(cpio_dir):
            if re.search('.spec', fname):
                specfile = fname

        if specfile == '':
            logging.critical('No specfile found, unable to process buildrequirements')
            sys.exit(1)

# TODO: expand macros; gtkhtml2-devel >= %{gtkhtml2_version} doesn't do us much good

        for line in open(specfile):
            reqs  = {}
            count = 0
            if re.search('^buildrequire', line.lower()):
                words = line.split()
                for c in words:
                    if not c.startswith('Build'):
                        # handle BuildRequires: foo,bar,baz
                        for x in c.split(','):
                            reqs[count] = x.strip()
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
                        if re.search('^(>|<|=|>=|<=)$', reqs[x+1]):
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
                    if new not in r:
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

            self.get_buildreq_record(require)

            # record == p_record
            try:
                b = SRPM_BuildRequires.create(
                    tid  = tid,
                    pid  = pid,
                    name = require
                )
                logging.debug('Filed BuildRequires with id %d', b.id)
            except Exception, e:
                logging.error('Unable to add buildrequires %s to database!\n%s', require, e)

        # make sure its empty
        del r[:]


    def cache_get_buildreq(self, name):
        """
        Function to look up the n_record and add it to the cache for buildreqs
        """
        bid = SRPM_BuildRequires.get_id(name)
        if bid:
            # add to the cache
            self.breq_cache[name] = bid
            return bid
        else:
            return False


    def get_buildreq_record(self, name):
        """
        Function to lookup and cache buildrequires info
        """

        # first check the cache
        if name in self.breq_cache:
            return self.breq_cache[name]

        # not cached, check the database
        bid = self.cache_get_buildreq(name)
        if bid:
            return bid

        return None


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

        file_list = []
        file_list.extend(glob(path + "/*.src.rpm"))

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

        for fname in file_list:
            if not os.path.isfile(fname):
                print 'File %s not found!\n' % fname
            elif not self.re_srpm.search(fname):
                print 'File %s is not a source rpm!\n' % fname
            else:
                self.record_add(tag_id, fname)

        # make sure its empty
        del file_list[:]


    def record_add(self, tag_id, fname, update=0):
        """
        Function to add a record to the database
        """
        logging.debug('in Source.record_add(%s, %s, %d)' % (tag_id, fname, update))

        if os.path.isfile(fname):
            path = os.path.abspath(os.path.dirname(fname))
        else:
            path = os.path.abspath(fname)
        logging.debug('Path:\t%s' % path)

        self.rcommon.file_rpm_check(fname)

        record = self.package_add_record(tag_id, fname, update)
        if not record:
            return

        file_list = self.rcommon.rpm_list(fname)
        if not file_list:
            return

        logging.debug('Add source records for package record: %s' % record)
        self.add_records(tag_id, record, file_list)
        cpio_dir = tempfile.mkdtemp()

        try:
            current_dir = os.getcwd()
            os.chdir(cpio_dir)
            self.get_all_files(fname)
            self.add_file_records(tag_id, record, file_list)
            self.add_ctag_records(tag_id, record, cpio_dir)
            self.add_buildreq_records(tag_id, record, cpio_dir)
            os.chdir(current_dir)
        finally:
            logging.debug('Removing temporary directory: %s...' % cpio_dir)
            shutil.rmtree(cpio_dir)

        if self.options.progress:
            sys.stdout.write('\n')


    def package_add_record(self, tid, fname, update=0):
        """
        Function to add a package record
        """
        logging.debug('in Source.package_add_record(%s, %s, %d)' % (tid, fname, update))

        fname   = os.path.basename(fname)
        rpmtags = commands.getoutput("rpm -qp --nosignature --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{BUILDTIME}' " + self.rcommon.clean_shell(fname))
        tlist   = rpmtags.split('|')
        logging.debug("tlist is %s " % tlist)
        package = tlist[0].strip()
        version = tlist[1].strip()
        release = tlist[2].strip()
        pdate   = tlist[3].strip()

        tag   = SRPM_Tag.get_tag(tid)

        if SRPM_Package.in_db(tid, package, version, release):
            print 'File %s-%s-%s is already in the database under tag %s' % (package, version, release, tag)
            return 0

        # TODO: we shouldn't have to have p_tag here as t_record has the same info, but it
        # TODO: sure makes it easier to sort alphabetically and I'm too lazy for the JOINs right now

        self.rcommon.show_progress(fname)
        try:
            p = SRPM_Package.create(
                tid      = tid,
                package  = package,
                version  = version,
                release  = release,
                date     = pdate,
                fullname = fname,
                update   = update
            )
            return p.id
        except Exception, e:
            logging.error('Adding file %s failed!\n%s', fname, e)
            return 0


    def list_updates(self, tag):
        """
        Function to list packages that have been imported due to being in the updates directory
        """
        logging.debug('in Source.list_updates(%s)' % tag)

        print 'Updated packages in tag %s:\n' % tag

        results = SRPM_Package.list_updates(tag)
        if results:
            for xrow in results:
                print '%s' % xrow.fullname
        else:
            print 'No results found.'
