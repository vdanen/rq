#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""

import logging, os, sys

class Config:
    """
    Class to handle the configuration file
    """

    def __init__(self, config_file):
        self.config_file = config_file
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

        self.config = {}
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

