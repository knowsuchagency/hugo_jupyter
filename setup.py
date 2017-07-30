#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""
from utils import _verify_lockfile as verify_lockfile
from utils import get_packages_from_lockfile

from setuptools import setup

verify_lockfile()

packages = get_packages_from_lockfile()

setup(
    install_requires=packages.default,
    tests_require=packages.development,
    extras_require={
        'dev': packages.development,
    },

    entry_points={
        'console_scripts': [
            'hugo_jupyter=hugo_jupyter.cli:main'
        ]
    },

)
