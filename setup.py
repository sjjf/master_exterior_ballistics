#!/usr/bin/env python

from distutils.version import StrictVersion
from setuptools import find_packages
from setuptools import setup
from string import ascii_letters
from subprocess import check_output
import sys
import os

name="master_exterior_ballistics"

# Fetch version from git tags, and write to version.py.
# When git is not available, use stored version.py.
git_tags = os.path.join(os.path.dirname(__file__), ".git", "refs", "tags")
version_py = os.path.join(os.path.dirname(__file__), name, 'version.py')

def get_git_tags():
    tags = os.listdir(git_tags)
    versions = [ StrictVersion(t.lstrip(ascii_letters)) for t in tags ]
    versions.sort()
    return versions

# try using git first
try:
    v = check_output(["git", "describe"]).strip()
    sections = v.split('-', 3)
    version_git = sections.pop(0)
    if sections:
        incr = sections.pop(0)
        version_git += "." + incr
    git = ""
    if sections:
        git = sections.pop(0)
        version_git += "+" + git
except:
    # look for git tags and use those
    try:
        versions = get_git_tags()
        version_git = str(versions[-1])
    except:
        # fall back to the existing version.py file
        with open(version_py, 'r') as fh:
            version_git = open(version_py).read().strip().split('=')[-1].replace('"','')

version_msg = "# Do not edit this file, versioning is governed by git tags"
with open(version_py, 'w') as fh:
    version_msg += os.linesep
    version_msg += "__version__=\"%s\"" % (version_git)
    version_msg += os.linesep
    fh.write(version_msg)

readme = open("README.md").read()

description = (
    "An exterior ballistics tool aimed at historical naval artillery."
)


cmdclass = {}
scripts = []
setup_requires = []
if sys.platform == 'win32':

    from install.bdist_wix import bdist_wix
    cmdclass = {
        'bdist_wix': bdist_wix
    }


setup(
    name="master_exterior_ballistics",
    version="{ver}".format(ver=version_git),
    description=description,
    long_description=readme,
    author="Simon Fowler",
    author_email="sjjfowler@gmail.com",
    url="https://github.com/sjjf/master_exterior_ballistics",
    license="GPLv3",
    packages=find_packages(exclude=['install']),
    include_package_data=True,
    setup_requires=setup_requires,
    scripts=scripts,
    entry_points={
        'console_scripts': [
            'meb = master_exterior_ballistics.cli:main',
        ],
        'gui_scripts': [
            'meb-gui = master_exterior_ballistics.gui:main',
        ],
    },
    cmdclass = cmdclass,
    )
