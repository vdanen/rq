#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""

import logging, os, sys, re, commands

class Common:
    """
    define some common functions for use
    """

    def __init__(self, options, rtag, rq_type):
        self.pstate  = 1
        self.options = options
        self.rtag    = rtag
        self.rq_type = rq_type
        self.lprefix = ''

        self.re_srpm    = re.compile(r'\.src\.rpm$')
        self.re_brpm    = re.compile(r'\.rpm$')


    def show_progress(self, prefix=''):
        """
        Function to show progress
        """

        if not self.options.verbose and not self.options.debug and self.options.progress:
            if not prefix:
                if self.pstate == 1:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                self.pstate = self.pstate + 1
                if self.pstate > 150:
                    self.pstate = 1
                return

            if prefix != 'files' and prefix != 'sources' and prefix != '':
                sys.stdout.write("%s: " % prefix.strip())
                sys.stdout.flush()
                self.pstate = 1
                return
            elif prefix != self.lprefix:
                sys.stdout.write('\t%s: ' %prefix)
                sys.stdout.flush()
                self.lprefix = prefix
                return


    def get_file_excludes(self):
        """
        Function to return the file_excludes
        """

        file_excludes = ('/.svn', '/CVS', 'AUTHORS', 'Makefile', 'ChangeLog', 'COPYING', 'TODO', 'README')

        return(file_excludes)


    def rpm_list(self, rpm_file, raw=False):
        """
        Function to get the list of files in an RPM, excluding those files defined
        by files_exclude
        """
        logging.debug('in rpm_list(%s)' % rpm_file)

        rpm_list  = commands.getoutput("rpm -qlvp --nosignature " + self.clean_shell(file))

        if rpm_list == '(contains no files)' or rpm_list == '':
            return False

        if raw:
            return(rpm_list)

        rpm_list  = rpm_list.splitlines()
        rlist     = {}
        count     = 0

        for entry in rpm_list:
            break_loop = False
            logging.debug('processing: %s' % entry) ### DEBUG
            for exclude in self.get_file_excludes():
                # make sure we don't include any files in our exclude list
                if re.search(exclude, entry):
                    logging.debug('found unwanted entry: %s' % entry)
                    break_loop = True

            if break_loop:
                continue

            is_suid = 0
            is_sgid = 0
            fperms     = entry.split()

            # this actually really stinks because we are allowed usernames longer
            # than 8 characters, but rpm -qlv will only display the first 8 characters
            # of the owner/group name -- not cool at all
            if len(fperms[2]) > 8:
                user  = fperms[2][:8]
                group = fperms[2][8:]
                fname = fperms[7]
            else:
                user  = fperms[2]
                group = fperms[3]
                fname = fperms[8]
            if fperms[0][3].lower() == 's':
                is_suid = 1
            if fperms[0][6].lower() == 's':
                is_sgid = 1

            perms = self.get_file_mode(fperms[0])

            rlist[count] = {'file': fname, 'user': user, 'group': group, 'is_suid': is_suid, 'is_sgid': is_sgid, 'perms': perms}
            count       += 1

        return(rlist)


    def file_rpm_check(self, rpm_file):
        """
        Function to check whether the file is a source or binary RPM

        The default is binary
        """
        logging.debug('in file_rpm_check(%s)' % rpm_file)

        re_srpm    = re.compile(r'\.src\.rpm$')
        re_brpm    = re.compile(r'\.rpm$')

        if not os.path.isfile(rpm_file):
            print 'File %s not found!\n' % rpm_file
            sys.exit(1)

        if self.rq_type == 'binary':
            if not re_brpm.search(rpm_file) or re_srpm.search(rpm_file):
                print 'File %s is not a binary rpm!\n' % rpm_file
                sys.exit(1)

        if self.rq_type == 'source':
            if not re_srpm.search(rpm_file):
                print 'File %s is not a source rpm!\n' % rpm_file
                sys.exit(1)


    def get_file_mode(self, mode):
        """
        Function to return the numeric file mode given the r--r--r-- string as input
        """
        user  = mode[1:4]
        group = mode[4:7]
        other = mode[7:]
        perms = {'user': user, 'group': group, 'other': other}

        num   = 0
        for perm_type in perms.keys():

            read    = perms[perm_type][0]
            write   = perms[perm_type][1]
            execute = perms[perm_type][2]

            if perm_type == 'user':
                if read == 'r':
                    num = num + 400
                if write == 'w':
                    num = num + 200
                if execute == 'x':
                    num = num + 100
                elif execute == 'S':
                    num = num + 4000
                elif execute == 's':
                    num = num + 4100
            if perm_type == 'group':
                if read == 'r':
                    num = num + 40
                if write == 'w':
                    num = num + 20
                if execute == 'x':
                    num = num + 10
                elif execute == 'S':
                    num = num + 2000
                elif execute == 's':
                    num = num + 2010
            if perm_type == 'other':
                if read == 'r':
                    num = num + 4
                if write == 'w':
                    num = num + 2
                if execute == 'x':
                    num = num + 1
        num = '%04d' % num
        return(num)


    def clean_shell(string):
        """
        Function to clean shell arguments
        """
        return("%s" %
            string.replace(' ', '\ ')
                  .replace('(', '\(')
                  .replace(')', '\)')
                  .replace('$', '\$')
                  .replace("'", "\'")
                  .replace('"', '\"')
                  .replace('`', '\`')
                  .replace(';', '\;')
                  .replace('*', '\*')
            )


class Config:
    """
    Class to handle the configuration file
    """

    def __init__(self, config_file):
        self.config_file = config_file
        self.config      = {}
        self.__get_config()


    def __getitem__(self, index):
        return self.config[index]


    def __setitem__(self, index, value):
        self.config[index] = value


    def __read_config(self):
        """
        Function to read the configuration file
        """
        logging.debug("in __read_config()")

        for line in open(self.config_file):
            line = line.rstrip()
            if not line:                                        # ignore empties
                continue
            if line.startswith("#") or line.startswith(";"):    # and ignore comments
                continue

            # Split on the first "=", this allows for values to have a "=" in them
            (config_name, config_value) = line.split("=", 1)
            config_name                 = config_name.strip()
            self.config[config_name]    = config_value


    def __get_config(self):
        """
        Function to find and read a configuration file
        """
        logging.debug("in __get_config()")
        if not self.config_file:
            self.config_file = '/etc/rqrc'
            if os.path.isfile(self.config_file):             # look for a system-wide one first
                self.__read_config()

            self.config_file = os.getenv('HOME') + '/.rqrc'
            if os.path.isfile(self.config_file):             # if we find a local one, overwrite anything defined
                self.__read_config()
        else:
            if os.path.isfile(self.config_file):
                self.__read_config()
            else:
                logging.critical('Specified configuration file does not exist: %s' % self.config_file)
                sys.exit(1)

        if not self.config:
            logging.critical('No configuration file found!')
            sys.exit(1)
