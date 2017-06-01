#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import rq

setup(
    name='rq',
    version=rq.__version__,
    description='RPM Query Tool',
    author='Vincent Danen',
    author_email='vdanen@annvix.com',
    url='https://annvix.com',
    packages=['rq'],
    package_dir={'rq': 'rq'},
    include_package_data=True,
    install_requires=['flask'],
    license="GPL",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GPL License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
    ],
)
