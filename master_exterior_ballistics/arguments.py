from master_exterior_ballistics.projectile import Projectile
from master_exterior_ballistics import version


# common argument handling
def add_projectile_args(parser):
    g = parser.add_argument_group('projectile')
    g.add_argument('-n', '--name',
        action='store',
        help='Projectile name')
    g.add_argument('-m', '--mass',
        action='store',
        type=float,
        help='Projectile mass')
    g.add_argument('-c', '--caliber',
        action='store',
        type=float,
        help='Projectile caliber')
    g.add_argument('--density-function',
        action='store',
        choices=['US', 'UK', 'ICAO'],
        help=(
            'Density Function: US Pre-1945 std, British std,'
            'ICAO std (default US)'
        ))
    gme = g.add_mutually_exclusive_group()
    gme.add_argument('--drag-function',
        action='store',
        choices=Projectile.get_drag_functions(),
        help="Drag function to use (default KD8)")
    gme.add_argument('--drag-function-file',
        action='store',
        help="File to read drag function data from")


def add_conditions_args(parser):
    g = parser.add_argument_group('conditions')
    g.add_argument('-v', '--mv',
        action='store',
        type=float,
        help='Initial velocity')
    g.add_argument('-a', '--altitude',
        action='store',
        type=float,
        help='Initial altitude (default 0)')
    g.add_argument('--air-density-factor',
        action='store',
        type=float,
        help='Air density adjustment factor (default 1.0)')


def add_common_args(parser):
    g = parser.add_argument_group('common options')
    g.add_argument('--config',
        action='store',
        help='Config file')
    g.add_argument('--write-config',
        action='store',
        metavar='CONFIG',
        help='Write config from the command line to a file')
    g.add_argument('-I', '--timestep',
        action='store',
        type=float,
        help="Simulation timestep")
    g.add_argument('--tolerance',
        action='store',
        type=float,
        default=1.0,
        help='Convergance tolerance')


def add_match_args(parser):
    g = parser.add_argument_group('match single shot')
    g.add_argument('-l', '--departure-angle',
        action='store',
        type=float,
        help="Departure Angle")
    g.add_argument('--target-range',
        action='store',
        type=float,
        help='Target range')


def add_form_factors(parser, required=False):
    g = parser.add_argument_group('form factors')
    gme = g.add_mutually_exclusive_group(required=required)
    gme.add_argument('-f', '--form-factor',
        action='store',
        type=float,
        help='Projectile form factor')
    gme.add_argument('-F',
        action='store',
        nargs='+',
        metavar='FF,A',
        help=(
            '(form factor, departure angle) tuple - used to specify a set of'
            ' form factors that will be used to determine the form factor'
            ' for a given shot by interpolation'
        ))


# some global defaults . . .
#
# these are largely so that these attributes will always exist in the args
# namespace, rather than needing to check to see if they're there and then
# check whether they're set to something meaningful
def set_common_defaults(parser):
    parser.set_defaults(
        show_trajectory=False,
        mass=None,
        mv=None,
        caliber=None,
        form_factor=None,
        F=None,
        altitude=None,
        air_density_factor=None,
        drag_function=None,
        drag_function_file=None,
        departure_angle=None,
        save_to_config=None,
        density_function=None,
        timestep=None,
    )
    parser.add_argument('-V', '--version',
        action='version',
        version="Master Exterior Ballistics version %s" % (version.__version__),
        help='Print program version information')
