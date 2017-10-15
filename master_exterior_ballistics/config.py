# Copyright Simon Fowler <sjjfowler@gmail.com>, September 2017.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from ConfigParser import SafeConfigParser as configparser
from ConfigParser import NoSectionError
from ConfigParser import NoOptionError
import os
import sys
from time import time


def get_config_dir():
    if sys.platform == 'win32':
        # windows is a bit odd
        home = os.environ['HOMEPATH']
    else:
        # everything else should be sane enough
        home = os.environ['HOME']

    # should be a no-op, but eh
    if os.path.exists(home):
        confdir = os.path.join(home, ".meb")
        if not os.path.exists(confdir):
            # if this comes up with an error let it go up the stack
            os.mkdir(confdir)
        return confdir
    else:
        raise IOError("Could not find home directory")

# How do we do this . . .
#
# We have two files - one has state information (recent files, last directory
# opened), the other has user defaults (not sure what exactly would go in here
# yet, but we need something separate from the state file). The state file is
# completely automatically managed, but the defaults file has to support user
# editing, which means that aside from generating an initial file we basically
# have to treat it as read-only.
#
# Since the two files have quite different uses we'll have two classes to
# manage the various contents, each with different models - for the recent
# files history we'll provide some stack-like methods, for the last directory
# we'll have a simple set/get, and for the defaults we'll have simple
# get methods (exactly like the underlying ConfigParser objects).
#


conffile = "config.ini"


config_defaults = {
    "recent_file_count": "500"
}


class Config(object):
    def __init__(self, configdir=None):
        self.configdir = configdir
        if not self.configdir:
            self.configdir = get_config_dir()
        self.config = configparser(config_defaults)
        self.config.read(os.path.join(self.configdir, conffile))

    def get(self, section, key):
        return self.config.get(section, key)

    def sections(self):
        return self.config.sections()


statfile = "status.ini"


class Status(object):
    def __init__(self, configdir=None):
        self.configdir = configdir
        if not self.configdir:
            self.configdir = get_config_dir()
        self.statusfile = os.path.join(self.configdir, statfile)
        self.status = configparser()
        self.status.read(self.statusfile)

    def get_last_dir(self):
        try:
            return self.status.get('directories', 'last_open')
        except NoSectionError:
            pass
        except NoOptionError:
            pass
        return None

    def set_last_dir(self, directory):
        if not self.status.has_section('directories'):
            self.status.add_section('directories')
        self.status.set('directories', 'last_open', directory)
        self._write()

    def _write(self):
        with open(self.statusfile, 'w') as f:
            self.status.write(f)

    def _get_tstamps(self):
        try:
            tstamps = [ts for ts in self.status.options('recent_files')]
            tstamps.sort()
            return tstamps
        except NoSectionError:
            return []

    def _get_filenames(self):
        names = {}
        # we do this in timestamp order, so that the most recent appearance of
        # any given file is what wins
        for ts in self._get_tstamps():
            name = self.status.get('recent_files', ts)
            names[name] = ts
        return names

    # What is the actual behaviour that we want fromm this?
    #
    # We can use it as a simple history, or we can use it as a more constrained
    # list of recently seen files - the difference is really what we key off,
    # the timestamp (in the history model) or the filename (in the recently
    # seen files model). The recently seen files model would have the key be
    # the filename and the value the timestamp - this makes it easy to update
    # the timestamp and so forth. Since the key is the filename, though, we
    # lose the ability to record multiple openings of the same file.
    #
    # We can emulate the recenly seen files model using the history model, but
    # not vice-versa (as noted, we can only record one entry per filename if we
    # use that model, but we can record lots of entries for a given filename in
    # the history model). Logically that would suggest that we use the history
    # model and then emulate the recent file model on top of that.
    def push_recent_file(self, filename):
        # the recent file list just needs to have the filename and the
        # timestamp at which we saw it. To support that I'll add a section
        # called 'recent_files', with a collection of entries that consist of
        # the integer timestamp as the option name, and the filename as the
        # value.
        section = 'recent_files'
        if not self.status.has_section(section):
            self.status.add_section(section)
        self.status.set(section, str(int(time())), filename)
        self.set_last_dir(os.path.dirname(os.path.abspath(filename)))

        # and we then clean out old entries
        # technically this should be configurable, but for simplicity's sake
        # we're going to leave it as a fixed limit at the moment. This is quite
        # high so that we don't end up emptying the list if we revisit the same
        # file over and over, unless we do it a /lot/.
        tstamps = self._get_tstamps()
        cfg = Config()
        count = int(cfg.get('DEFAULT', 'recent_file_count'))
        while len(tstamps) >= count:
            self.status.remove_option(section, tstamps[0])
            tstamps = self._get_tstamps()

        self._write()

    def get_recent_files(self, count=10):
        # we return a list of 2-tuples, giving the timestamp and the filename,
        # with only one entry per file - the most recent time it was seen
        tstamps = self._get_tstamps()
        accum = {}
        for i in tstamps:
            fn = self.status.get('recent_files', i)
            accum[fn] = i
        t = [(i, f) for (f, i) in accum.items()]
        t.sort(key=lambda (i, f): i, reverse=True)
        # and then we return only the most recent entries
        return t[:count]

    def get_file_history(self):
        # here we return the full history, with potentially multiple entries
        # per filename
        #
        # Note: we don't use self.status.items('recent_files') because we want
        # to preserve the timestamp ordering.
        tstamps = self._get_tstamps()
        accum = []
        for i in tstamps:
            fn = self.status.get('recent_files', i)
            accum.append((i, fn))
        return accum

    def get_last_file(self):
        tstamps = self._get_tstamps()
        try:
            fn = self.status.get('recent_files', tstamps[-1])
            return (tstamps[-1], fn)
        except IndexError:
            return (None, None)
