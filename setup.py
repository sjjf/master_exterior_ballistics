#!/usr/bin/env python

from setuptools import find_packages
from setuptools import setup

readme = open("README.md").read()

description = (
    "An exterior ballistics tool aimed at historical naval artillery."
)

setup(
    name="master_exterior_ballistics",
    version="0.11.0",
    description=description,
    long_description=readme,
    author="Simon Fowler",
    author_email="sjjfowler@gmail.com",
    url="https://github.com/sjjf/master_exterior_ballistics",
    license="GPLv3",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'meb = master_exterior_ballistics.meb:main',
        ],
    },
    )
