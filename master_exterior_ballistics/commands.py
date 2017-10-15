from master_exterior_ballistics import projectile
from master_exterior_ballistics import arguments
import math


# The idea here is that the entry points for the different commands will be
# broken out into objects that encapsulate the argument collection, processing
# and output, but split up such that the relevant bits can be accessed from
# both the command line code and the GUI code.
#
# The command object handles setting up its own argument parsing code (adding
# arguments to a top level parser), creating a Projectile object based on
# arguments that are handed to it (with the actual call to parse_args() done
# elsewhere), running the actual command processing, and then formatting the
# output.
#
# The base object is mostly empty, since all the meaningful stuff will be
# pretty command-specific.
class Command(object):

    def __init__(self):
        pass

    # most headers are identical
    def format_header(self):
        header = self.projectile.format_configuration()
        header += self.projectile.format_initial_conditions()
        return header

    def format_configuration(self):
        return self.projectile.format_configuration()

    def format_conditions(self):
        return self.projectile.format_initial_conditions()

    def format_output(self):
        raise NotImplementedError

    def add_arguments(self, subparser):
        raise NotImplementedError

    # this doesn't catch any errors - that's up to higher levels
    def create_projectile(self, args):
        self.projectile = projectile.Projectile(args)
        return self.projectile

    def run_analysis(self):
        raise NotImplementedError

    def process(self, args):
        self.create_projectile(args)
        self.run_analysis()


class SingleRun(Command):

    def format_output(self):
        text = self.projectile.format_trajectory()
        text += "Final conditions:\n"
        text += "Time of flight: %.2fs\n" % (self.tt)
        text += "Range: %.2fm\n" % (self.rg)
        text += "Impact Angle: %.4fdeg\n" % (math.degrees(self.il))
        text += "Impact Velocity: %.2fm/s\n" % (self.iv)
        return text

    def add_arguments(self, subparser):
        parser = subparser.add_parser('single',
            description="Simulate a single shot",
            help="Simulate a single shot")
        g = parser.add_argument_group('shot specifics')
        g.add_argument('-l', '--departure-angle',
            action='store',
            required=True,
            type=float,
            help="Departure Angle")
        g.add_argument('-t', '--print-trajectory', '--show-trajectory',
            dest='show_trajectory',
            action='store_true',
            required=False,
            help="Print projectile trajectory")
        arguments.add_projectile_args(parser)
        arguments.add_form_factors(parser)
        arguments.add_conditions_args(parser)
        arguments.add_common_args(parser)
        return parser

    def run_analysis(self):
        (self.tt, self.rg, self.iv, self.il) = self.projectile.one_shot()


class MaxRange(Command):

    def format_output(self):
        text = "Initial Velocity: %.4fm/s\n" % (self.projectile.mv)
        text += "Maximum range: %.2fm\n" % (self.rg_max)
        text += "Departure Angle for maximum range: %.4fdeg\n" % (math.degrees(self.da))
        return text

    def run_analysis(self):
        (self.rg_max, self.da) = self.projectile.max_range()

    def add_arguments(self, subparser):
        parser = subparser.add_parser('max-range',
            description="Estimate the maximum range for a given projectile configuration",
            help="Find the maximum range for a given projectile configuration")
        arguments.add_projectile_args(parser)
        arguments.add_form_factors(parser)
        arguments.add_conditions_args(parser)
        arguments.add_common_args(parser)
        parser.set_defaults(func=self.process_command_line,
            print_trajectory=False)
        return parser


class MatchRange(Command):

    def format_output(self):
        text = ""
        # we want to separate the notes with an empty line
        if len(self.runtime_notes) > 0:
            text = "\n"
        text += self.runtime_notes
        for (tr, tt, rg, iv, il, l, count) in self.shots:
            text += "\n"
            text += "Range %.1fm matched at the following conditions:\n" % (tr)
            text += " Range: %.1fm\n" % (rg)
            text += " Initial Velocity: %.4fm/s\n" % (self.mv)
            text += " Departure Angle: %.4fdeg\n" % (math.degrees(l))
            text += " Time of flight: %.2fs\n" % (tt)
            text += " Impact Angle: %.4fdeg\n" % (math.degrees(il))
            text += " Impact Velocity: %.2fm/s\n" % (iv)
            text += " Converged in %d iterations\n" % (count)
        return text

    def run_analysis(self):
        tolerance = self.args.tolerance
        (self.rg_max, self.da_max) = self.projectile.max_range()
        targets = []
        for tr in self.args.target_range:
            tr = float(tr)
            targets.append(tr)

        self.shots = []
        self.runtime_notes = ""
        self.mv = self.projectile.mv
        for tr in targets:
            if tr > self.rg_max + 1:
                self.runtime_notes += "Target range %.0fm " % (tr)
                self.runtime_notes += "is outside maximum range (%.0fm)\n" % (self.rg_max)
                continue
            try:
                (tt, rg, iv, il, l) = self.projectile.match_range(tr, tolerance)
            except ValueError:
                self.runtime_notes += "Could not converge on range %.1fm\n" % (tr)
                continue
            self.shots.append((tr, tt, rg, iv, il, l, self.projectile.count))

    def add_arguments(self, subparser):
        parser = subparser.add_parser('match-range',
            description="Match the target range by adjusting departure angle",
            help="Find the departure angle to achieve the specified target range")
        g = parser.add_argument_group('match multiple shots')
        g.add_argument('--target-range',
            action='store',
            required=False,
            nargs='+',
            metavar='RANGE',
            help=(
                'Set of target ranges - may be used more than once, with each '
                'range being matched'
            ))
        arguments.add_projectile_args(parser)
        arguments.add_form_factors(parser)
        arguments.add_conditions_args(parser)
        arguments.add_common_args(parser)
        return parser


class MatchFormFactor(Command):

    def format_header(self):
        self.projectile.clear_form_factors()
        self.projectile.unset_departure_angle()
        header = super(MatchFormFactor, self).format_header()
        header += "\n"
        header += "Form Factor Results (departure angle, form factor):\n"
        return header

    def format_output(self):
        text = ""
        for (ff, l, rg, count) in self.shots:
            text += " %.4f,%.6f (%d iterations)\n" % (math.degrees(l), ff, count)
        return text

    def run_analysis(self):
        target_range = self.args.target_range
        tolerance = self.args.tolerance
        targets = []
        if self.args.shot:
            for shot in self.args.shot:
                (da, tr) = shot.split(',')
                da = math.radians(float(da))
                tr = float(tr)
                targets.append((da, tr))
        else:
            targets.append(self.projectile.departure_angle, target_range)

        self.shots = []
        for (da, tr) in targets:
            (ff, l, rg) = self.projectile.match_form_factor(da, tr, tolerance)
            self.shots.append((ff, l, rg, self.projectile.count))

        if self.args.save_to_config:
            for (ff, l, rg, count) in self.shots:
                self.projectile.update_form_factors(l, ff)
            self.projectile.to_config(self.args.save_to_config)

    def add_arguments(self, subparser):
        parser = subparser.add_parser('find-ff',
            description="Match the shot(s) specified by adjusting the form fator",
            help="Find the form factor to match the specified shots")
        parser.add_argument('--save-to-config',
            action='store',
            required=False,
            metavar='CONFIG',
            help='Save the calculated form factors to the given config file')
        arguments.add_projectile_args(parser)
        arguments.add_conditions_args(parser)
        g = parser.add_argument_group('match multiple shots')
        g.add_argument('--shot',
            action='store',
            required=False,
            metavar='A,R',
            nargs='+',
            help=(
                'Set of <angle,range> tuples - may be used more than once, with '
                'each tuple being simulated'
            ))
        arguments.add_match_args(parser)
        arguments.add_common_args(parser)
        parser.set_defaults(form_factor=1.0)
        return parser


# The two range table commands share the same header and output formats
class RangeTableCommon(Command):

    # we need to override this, since it's a very different header format
    def format_header(self):
        text = "Range Table\n"
        text += self.projectile.format_configuration()
        text += "Initial velocity: %.4fm/s\n" % (self.mv)
        text += "Air Density Factor: %.4f\n" % (self.air_density_factor)
        text += "Range increments: %.1fm\n" % (self.increment)
        return text

    def format_output(self):
        text = "\n"
        text += " Range Departure Angle of Time of Striking\n"
        text += "        Angle      Fall   Flight    Vel.\n"
        text += "-------------------------------------------\n"
        for (tt, rg, iv, il, l) in self.shots:
                text += "% 6.0f % 8.4f % 8.4f % 6.2f % 8.2f\n" % (
                    rg,
                    math.degrees(l),
                    math.degrees(il),
                    tt,
                    iv
                )
        return text


class RangeTable(RangeTableCommon):

    def run_analysis(self):
        # this stores the max range data in the projectile object, so we don't
        # need to save it here
        self.projectile.max_range()
        self.increment = self.args.increment
        start = self.args.start
        end = self.args.end
        self.mv = self.projectile.mv
        self.air_density_factor = self.projectile.air_density_factor
        target_range = start
        tolerance = 1.0
        l = 1.0
        self.shots = []
        while True:
            try:
                (tt, rg, iv, il, l) = self.projectile.match_range(target_range,
                                                                  tolerance)
                self.shots.append((tt, rg, iv, il, l))
                target_range += self.increment
                if rg > end:
                    break
            except ValueError:
                # range is too great - break out
                break

    def add_arguments(self, subparser):
        parser = subparser.add_parser('range-table',
            description="Calculate a range table based on range increments",
            help="Calculate a range table based on range increments")
        g = parser.add_argument_group('range table options')
        g.add_argument('--increment',
            action='store',
            required=False,
            type=float,
            default=100.0,
            help='Range steps for range table')
        g.add_argument('--start',
            action='store',
            required=False,
            type=float,
            default=100.0,
            help='Starting range')
        g.add_argument('--end',
            action='store',
            required=False,
            type=float,
            default=100000.0,
            help='End range')
        arguments.add_projectile_args(parser)
        arguments.add_form_factors(parser)
        arguments.add_conditions_args(parser)
        arguments.add_common_args(parser)
        return parser


class RangeTableAngle(RangeTableCommon):

    def run_analysis(self):
        self.increment = math.radians(self.args.increment)
        l = math.radians(self.args.start)
        end = math.radians(self.args.end)
        self.projectile.max_range()
        self.mv = self.projectile.mv
        self.air_density_factor = self.projectile.air_density_factor

        self.shots = []
        while l <= ((end * 100 + 1) / 100) and l < 90:
            (tt, rg, iv, il) = self.projectile.one_shot(l)
            self.shots.append((tt, rg, iv, il, l))
            l += self.increment

    def add_arguments(self, subparser):
        parser = subparser.add_parser('range-table-angle',
            description="Calculate a range table based on departure angle increments",
            help="Calculate a range table based on departure angle")
        g = parser.add_argument_group('range table options')
        g.add_argument('--increment',
            action='store',
            required=False,
            type=float,
            default=1.0,
            help='Departure angle steps for range table')
        g.add_argument('--start',
            action='store',
            required=False,
            type=float,
            default=1.0,
            help='Starting departure angle')
        g.add_argument('--end',
            action='store',
            required=False,
            type=float,
            default=50.0,
            help='End departure angle')
        arguments.add_projectile_args(parser)
        arguments.add_form_factors(parser)
        arguments.add_conditions_args(parser)
        arguments.add_common_args(parser)
        return parser


class MakeConfig(Command):

    # this is a pretty minimal thing, the intent being to make this
    # functionality available via the same interface for both CLI and GUI
    # users. Because it doesn't have any kind of output or whatever, the only
    # Command level interfaces it needs to present are process() and
    # add_arguments().
    def process(self, args):
        self.create_projectile(args)
        self.projectile.to_config(args.filename)

    def add_arguments(self, subparser):
        parser = subparser.add_parser('make-config',
            description="Create a configuration file with the specified contents",
            help="Create a config file")
        g = parser.add_argument_group('config file details')
        g.add_argument('--filename',
            action='store',
            required=True,
            help="Config file name")
        arguments.add_projectile_args(parser)
        arguments.add_form_factors(parser)
        arguments.add_conditions_args(parser)
        arguments.add_common_args(parser)
        return parser
