#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""
from configparser import ConfigParser

from setuptools import setup


def get_requirements(section: str) -> list:
    """Read requirements from Pipfile."""
    pip_config = ConfigParser()
    pip_config.read('Pipfile')

    def gen():
        for item in pip_config.items(section):
            lib, version = item
            lib, version = lib.strip('"'), version.strip('"')
            # ungracefully handle wildcard requirements
            if version == '*': version = ''
            yield lib + version

    return list(gen())


packages = get_requirements('packages')
dev_packages = get_requirements('dev-packages')

setup(
    install_requires=packages,
    tests_require=dev_packages,
    extras_require={
        'dev': dev_packages,
    },
    
    entry_points={
        'console_scripts': [
            'hugo_jupyter=hugo_jupyter.cli:main'
        ]
    },
    
)
