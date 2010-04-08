#!/usr/bin/env python
"""
This program extracts data from RPM and SRPM packages and stores it in
a database for later querying.

based on the srpm script of similar function copyright (c) 2005 Stew Benedict <sbenedict@mandriva.com>
copyright (c) 2007-2009 Vincent Danen <vdanen@linsec.ca>

$Id$
"""

import logging, os, sys

def read_config(config_file):
    """
    Function to read the configuration file
    """
    logging.debug("in read_config(%s)" % config_file)

    config = {}
    for line in open(config_file):
        line = line.rstrip()
        if not line:                                        # ignore empties
            continue
        if line.startswith("#") or line.startswith(";"):    # and ignore comments
            continue

        # Split on the first "=", this allows for values to have a "=" in them
        (config_name, config_value) = line.split("=", 1)
        config_name                 = config_name.strip()
        config[config_name]         = config_value

    return config


def get_config(conffile):
    """
    Function to find and read a configuration file
    """
    config = {}

    if conffile:
        if os.path.isfile(conffile):
            config = read_config(conffile)
        else:
            logging.critical('Specified configuration file does not exist: %s' % conffile)
            sys.exit(1)
    else:
        config_file = '/etc/rqrc'
        if os.path.isfile(config_file):             # look for a system-wide one first
            config = read_config(config_file)

        config_file = os.getenv('HOME') + '/.rqrc'
        if os.path.isfile(config_file):             # if we find a local one, overwrite anything defined
            config = read_config(config_file)

    if not config:
        logging.critical('No configuration file found!')
        sys.exit(1)

    return config
