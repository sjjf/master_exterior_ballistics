#!/usr/bin/env python
#
# Based on the Master Exterior Ballistics Program, written by W. J.  Jurens
# with the following copyright header
# **************************************
#   Copyright (c) 1983 W. J. Jurens
#          62 Fidler Avenue
#     Winnipeg, Manitoba, Canada
#             R3J 2R7
#           Ph. 204-837-3125
# **************************************
#
# Reimplementation in Python copyright Simon Fowler <sjjfowler@gmail.com>,
# April-May 2017.
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

import argparse
from master_exterior_ballistics import commands
from master_exterior_ballistics import projectile
from master_exterior_ballistics import arguments
import sys


# implemented as a mixin class so that we can keep the logic implementing the
# actual analysis separate from the logic of the comand line processing
class CLIMixin(object):

    # this is a wrapper that implements the command line processing logic, and
    # can be used as the target function in the argument parser defaults
    #
    # The default should be sufficient, as long as nothing hinky is going on
    def process_command_line(self, args):
        self.create_projectile(args)
        self.run_analysis()
        text = self.format_header()
        text += self.format_output()
        print text

    # We override this here because in the command line processing case we
    # /want/ to catch all the errors at this level
    def create_projectile(self, args):
        self.args = args
        try:
            self.projectile = projectile.Projectile(args)
            return self.projectile
        except IOError as e:
            print e
        except projectile.MissingAttribute as e:
            print e
        print "Exiting"
        sys.exit(1)

    # Override the argument parser to point it at the process_command_line
    # method
    def add_arguments(self, subparser):
        parser = super(CLIMixin, self).add_arguments(subparser)
        parser.set_defaults(func=self.process_command_line)


class SingleRunCLI(CLIMixin, commands.SingleRun):
    pass


class MaxRangeCLI(CLIMixin, commands.MaxRange):
    pass


class MatchRangeCLI(CLIMixin, commands.MatchRange):
    pass


class MatchFormFactorCLI(CLIMixin, commands.MatchFormFactor):
    pass


class RangeTableCLI(CLIMixin, commands.RangeTable):
    pass


class RangeTableAngleCLI(CLIMixin, commands.RangeTableAngle):
    pass


class MakeConfigCLI(CLIMixin, commands.MakeConfig):

    # we need to override this because we're not doing any actual processing,
    # just calling one projectile method
    def process_command_line(self, args):
        self.process(args)


def parse_args():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    arguments.set_common_defaults(parser)
    subparsers = parser.add_subparsers(title="Modes of operation",
        description="<mode> -h/--help for mode help")

    # note that these are scoped to here, but the objects are still accessible
    # because they're bound into the parser object (via the
    # process_command_line function pointer).
    single_run = SingleRunCLI()
    single_run.add_arguments(subparsers)
    match_range = MatchRangeCLI()
    match_range.add_arguments(subparsers)
    find_ff = MatchFormFactorCLI()
    find_ff.add_arguments(subparsers)
    range_table = RangeTableCLI()
    range_table.add_arguments(subparsers)
    range_table_angle = RangeTableAngleCLI()
    range_table_angle.add_arguments(subparsers)
    max_range = MaxRangeCLI()
    max_range.add_arguments(subparsers)
    make_config = MakeConfigCLI()
    make_config.add_arguments(subparsers)

    return parser.parse_args()


def main():
    args = parse_args()

    if args.write_config:
        p = projectile.Projectile(args)
        p.to_config(args.write_config)
        print "Config written to %s" % (args.write_config)
        sys.exit(0)

    args.func(args)


if __name__ == '__main__':
    main()
