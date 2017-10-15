import argparse
import math
from ConfigParser import SafeConfigParser as cfgparser
from os import path
import pkg_resources
import sys

# constants

# surface air density (kg/m^3)
DF = 1.2250

# surface gravity (m/s^2)
G = 9.80665


def gravity(altitude):
    return G - (0.000003665 * altitude)


# surface speed of sound
CS = 344.0

# ICAO atmospheric model constants
Z4 = 1.34279408e-18
Z3 = -9.87941429e-14
Z2 = 3.90848966e-9
Z1 = -9.69888125e-5


def atmosphere_icao(alt):
    return Z4 * alt**4 + Z3 * alt**3 + Z2 * alt**2 + Z1 * alt + 1


def atmosphere_US(alt):
    return 10.0**-(0.000045 * alt)


def atmosphere_UK(alt):
    return 0.1**(0.141 * (alt / 3048.0))


def interpolate(a, x1, x2, y1, y2):
    # a is a value between x1 and x2 - interpolate a corresponding value
    # between y1 and y2
    return y1 + ((y2 - y1) * ((a - x1) / (x2 - x1)))


def str2bool(v):
    return v.lower() in ['yes', 'true', 'y', 't', '1']


def str2rad(v):
    return math.radians(float(v))


def rad2str(v):
    return str(math.degrees(v))


def cmp_projectiles(p1, p2, verbose=False):
    if not p1 or not p2:
        return
    same = True
    if p1.name != p2.name:
        if verbose:
            print "Name"
            print "-%s" % (p1.name)
            print "+%s" % (p2.name)
        same = False
    if p1.mass != p2.mass:
        if verbose:
            print "Mass"
            print "-%f" % (p1.mass)
            print "+%f" % (p2.mass)
        same = False
    if p1.caliber != p2.caliber:
        if verbose:
            print "Caliber"
            print "-%f" % (p1.caliber)
            print "+%f" % (p2.caliber)
        same = False
    if p1.mv != p2.mv:
        if verbose:
            print "MV"
            print "-%f" % (p1.mv)
            print "+%f" % (p2.mv)
        same = False
    if p1.drag_function != p2.drag_function:
        if verbose:
            print "Drag Function"
            print "-%s" % (p1.drag_function)
            print "+%s" % (p2.drag_function)
        same = False
    if p1.drag_function_file != p2.drag_function_file:
        if verbose:
            print "Drag Function File"
            print "-%s" % (p1.drag_function_file)
            print "+%s" % (p2.drag_function_file)
        same = False
    if p1.density_function != p2.density_function:
        if verbose:
            print "Density Function"
            print "-%s" % (p1.density_function)
            print "+%s" % (p2.density_function)
        same = False
    if p1.air_density_factor != p2.air_density_factor:
        if verbose:
            print "Air Density Factor"
            print "-%f" % (p1.air_density_factor)
            print "+%f" % (p2.air_density_factor)
        same = False
    ff1 = p1.copy_form_factors()
    ff2 = p2.copy_form_factors()
    same_ffs = True
    if len(ff1) != len(ff2):
        same_ffs = False
    else:
        i = 0
        while i < len(ff1):
            (d1, f1) = ff1[i]
            (d2, f2) = ff2[i]
            if d1 != d2:
                same_ffs = False
                break
            if f1 != f2:
                same_ffs = False
                break
            i += 1
    if not same_ffs:
        if verbose:
            print "Form Factors"
            print "-%s" % (repr(ff1))
            print "+%s" % (repr(ff2))
        same = False
    return same


# Trying to move error handling away from the print a message and sys.exit()
# model, since we're going to be moving this code down the stack and we don't
# want it bailing out all the way unexpectedly.
#
# I'm not sure if the custom exceptions are worth it, but it at least makes for
# a more meaningful error message
class MissingAttribute(Exception):
    def __init__(self, attrs, msg):
        if isinstance(attrs, list):
            self.attrs = attrs
        else:
            self.attrs = [attrs]
        text = msg + "\n"
        text += "Missing attributes:\n"
        for attr in self.attrs:
            text += attr + "\n"
        self.msg = text

    def __str__(self):
        return self.msg


class Projectile(object):

    filename = None
    name = ""
    timestep = 0.1
    altitude = None
    mass = None
    caliber = None
    mv = None
    departure_angle = None
    air_density_factor = None
    density_function = None
    atmosphere = None
    show_trajectory = None
    Traj = []
    Max_Range = None
    mach = None
    kd = None
    departure_angles = None
    form_factors = None
    drag_function = None
    drag_function_file = None

    count = 0

    # Some stuff is required for us to be able to do anything useful, and other
    # stuff can have a default. Since we're pulling from a config file at the
    # same time as we're pulling from command line arguments, we can't simply
    # use the argparse 'require' feature - it's more complex than that.
    # Instead, we need to know here what values are needed, and what we have
    # defaults for, and we need to deal with the argument status ourselves.
    #
    # The logic here is that if a config file has been specified we load stuff
    # from it, and then after that we update the object based on the command
    # line arguments, and finally we check that all the necessary data is
    # available before we return, setting the defaults if any of them are
    # missing.
    _required = ['mass', 'caliber', 'mv', 'form_factors', 'drag_function']
    _defaults = {
        'timestep': 0.1,
        'altitude': 0.0001,
        'air_density_factor': 1.0,
        'show_trajectory': False,
        'density_function': 'US',
        'drag_function': 'KD8',
    }

    # for all the stuff that doesn't have a meaningful default value, but which
    # we need to have /some/ idea about so we can fake up a projectile for
    # interative use.
    _default_attributes = {
        'name': "",
        'mass': 0.0,
        'caliber': 0.0,
        'mv': 0.0,
        'form_factor': None,
        'F': None,
        'departure_angle': None,
        'drag_function_file': None,
        'tolerance': 1.0,
        'target_range': None,
        'shot': None,
        'increment': 1.0,
        'start': None,
        'end': None,
        'filename': None,
        'config': None,
        'save_to_config': None,
    }

    _wrapper_in = {
        'mass': float,
        'caliber': float,
        'mv': float,
        'timestep': float,
        'altitude': float,
        'departure_angle': str2rad,
        'air_density_factor': float,
        'show_trajectory': str2bool,
    }

    _wrapper_out = {
        'departure_angle': rad2str,
    }

    @classmethod
    def make_args(cls):
        args = argparse.Namespace()
        for (attr, value) in cls._defaults.items():
            setattr(args, attr, value)
        for (attr, value) in cls._default_attributes.items():
            setattr(args, attr, value)
        return args

    @classmethod
    def from_defaults(cls):
        args = Projectile.make_args()
        return Projectile(args)

    @classmethod
    def from_file(cls, filename):
        p = Projectile()
        args = argparse.Namespace()
        args.config = filename
        p.load_config(args)
        p.verify()
        return p

    def __init__(self, args=None):
        # do nothing if we have no args - the caller has to do the
        # configuration themselves
        if not args:
            return

        self.load_config(args)
        self.set_atmosphere(args)
        self.load_drag_function(args)
        self.load_form_factors(args)

        if isinstance(args.altitude, float):
            self.altitude = args.altitude
        if isinstance(args.departure_angle, float):
            self.departure_angle = math.radians(args.departure_angle)
        if isinstance(args.mv, float):
            self.mv = args.mv
        if isinstance(args.caliber, float):
            self.caliber = args.caliber
        if isinstance(args.air_density_factor, float):
            self.air_density_factor = args.air_density_factor
        if isinstance(args.mass, float):
            self.mass = args.mass
        if isinstance(args.timestep, float):
            self.timestep = args.timestep
        if args.show_trajectory:
            self.show_trajectory = args.show_trajectory
        if 'name' in args:
            self.name = args.name

        self.verify()

    def verify(self):
        # check for required values
        invalid = False
        missing = []
        for attr in self._required:
            t = getattr(self, attr)
            # this is odd, but we want to allow an empty list, which evaluates
            # as False in the simple boolean context
            if isinstance(t, list):
                pass
            elif t is None:
                invalid = True
                missing.append(attr)
        if invalid:
            raise MissingAttribute(missing, "Projectile not fully configured")

        # fix missing defaults
        for (attr, default) in self._defaults.items():
            t = getattr(self, attr)
            if not t:
                setattr(self, attr, default)

    # write out an ini-formatted config file for this projectile
    # If filename is not given, write to stdout
    def to_config(self, filename=None):
        cfg = cfgparser()

        cfg.add_section("projectile")
        if self.name:
            cfg.set("projectile", "name", self.name)
        cfg.set("projectile", "mass", repr(self.mass))
        cfg.set("projectile", "caliber", repr(self.caliber))
        if self.drag_function_file:
            cfg.set("projectile", "drag_function_file", self.drag_function_file)
        else:
            cfg.set("projectile", "drag_function", self.drag_function)
        cfg.set("projectile", "density_function", self.density_function)

        cfg.add_section("form_factor")
        for (da, ff) in zip(self.departure_angles, self.form_factors):
            cfg.set("form_factor", repr(math.degrees(da)), repr(ff))

        cfg.add_section("initial_conditions")
        cfg.set("initial_conditions", "altitude", repr(self.altitude))
        cfg.set("initial_conditions", "mv", repr(self.mv))
        cfg.set("initial_conditions", "air_density_factor", repr(self.air_density_factor))

        cfg.add_section("simulation")
        cfg.set("simulation", "timestep", repr(self.timestep))

        if filename != '-':
            with open(filename, "w") as outfile:
                cfg.write(outfile)
            return
        print ""
        cfg.write(sys.stdout)

    def load_config(self, args):
        if not args.config:
            return
        filename = args.config
        cfg = cfgparser()
        try:
            with open(filename) as fp:
                cfg.readfp(fp, filename)
        except IOError as e:
            # Update the error message so that it's a bit more meaningful
            raise IOError("Unable to load config file %s: %s" % (filename, e))

        for section in cfg.sections():
            # form factor needs to be treated specially
            if section == "form_factor":
                self.clear_form_factors()
                for (da, ff) in cfg.items(section):
                    self.update_form_factors(math.radians(float(da)), float(ff))
            else:
                for (attr, value) in cfg.items(section):
                    try:
                        w = self._wrapper_in[attr]
                        value = w(value)
                    except KeyError:
                        pass
                    setattr(self, attr, value)
        self.filename = filename

    # a few things are cached, and we need to invalidate those things in order
    # to make sure that we don't have stuff carried over during processing
    def invalidate(self):
        self.Max_range = None
        self.Traj = None

    # these are the only things that change during the lifetime of the
    # projectile object
    def set_altitude(self, alt):
        self.altitude = alt

    def set_departure_angle(self, l):
        self.departure_angle = l

    # sometimes we want to get rid of this
    def unset_departure_angle(self):
        self.departure_angle = None

    def set_mv(self, mv):
        self.mv = mv

    def set_atmosphere(self, args):
        if args.density_function:
            self.density_function = args.density_function
        self._set_atmosphere(self.density_function)

    def _set_atmosphere(self, df):
        self.density_function = df
        if not self.density_function and 'density_function' in self._defaults:
            self.density_function = self._defaults['density_function']
        if self.density_function == "US":
            self.atmosphere = atmosphere_US
            return
        if self.density_function == "UK":
            self.atmosphere = atmosphere_UK
            return
        if self.density_function == "ICAO":
            self.atmosphere = atmosphere_icao
            return
        print "No atmosphere model specified?"

    def set_density_function(self, df):
        self._set_atmosphere(df)

    @classmethod
    def get_density_functions(cls):
        return ["US", "UK", "ICAO"]

    def set_drag_function(self, df):
        self.drag_function = None
        self.drag_function_file = None
        if df in Projectile.get_drag_functions():
            self.drag_function = df
            self._load_drag_function_std()
        else:
            self.drag_function_file = df
            self._load_drag_function_file()

    # the drag function can be specified in a file, or picked from a list of
    # already defined options. Anything specified on the command line takes
    # precedence over the config file; in a config file the drag_function_file
    # option takes precedence over the drag_function option
    def load_drag_function(self, args):
        self.drag_function = None
        self.drag_function_file = None
        if args.drag_function_file:
            self.drag_function_file = args.drag_function_file
            self.drag_function = "file"
            self._load_drag_function_file()
            return
        if args.drag_function:
            self.drag_function = args.drag_function
            self._load_drag_function_std()
            return
        if self.drag_function_file:
            self._load_drag_function_file()
            return
        if self.drag_function:
            self._load_drag_function_std()
            return
        # at this point we have nothing specified anywhere, but we do have a
        # default!
        if 'drag_function' in self._defaults:
            self.drag_function = self._defaults['drag_function']
            self._load_drag_function_std()

    def _load_drag_function_file(self):
        try:
            with open(self.drag_function_file) as df:
                self._load_drag_function(df)
        except IOError as e:
            print "Could not load drag function from file ",
            print "%s: %s" % (self.drag_function_file, e)
            sys.exit(1)

    def _load_drag_function_std(self):
        df_resource = "drag_functions/%s.conf" % (self.drag_function)
        df = pkg_resources.resource_stream('master_exterior_ballistics',
                                           df_resource)
        self._load_drag_function(df)

    def _load_drag_function(self, df):
        mach = []
        kd = []
        try:
            for line in df.readlines():
                line = line.strip()
                if line != "":
                    (m, k) = line.split(',', 2)
                    mach.append(float(m))
                    kd.append(float(k))
            self.mach = mach
            self.kd = kd
        except ValueError:
            raise ValueError("Invalid drag function file format")

    # this is a class method so that we can access it without needing an object
    @classmethod
    def get_drag_functions(cls):
        try:
            dfs = pkg_resources.resource_listdir('master_exterior_ballistics',
                                                 'drag_functions')
            dfs = [path.basename(path.splitext(t)[0]) for t in dfs]
            dfs.sort()
            return dfs
        except OSError as e:
            print "Failed to find drag function resources: %s" % (e)

    def get_KD(self, v, alt):
        m = v / (CS - (0.004 * alt))
        i = 1
        while i < len(self.mach) - 1:
            if m < self.mach[i]:
                break
            i += 1
        m1 = self.mach[i - 1]
        m2 = self.mach[i]
        k1 = self.kd[i - 1]
        k2 = self.kd[i]
        t = ((m - m1) / (m2 - m1)) * (k2 - k1) + k1
        return t

    # as with all the other stuff, we allow the command line arguments to
    # override the config file.
    #
    # The logic is to set defaults, from the config file if available (that
    # happens before now), then look through the arguments for values to
    # replace them.
    #
    # Note that we /want/ to allow a scenario where the form factor lists are
    # defined as lists (rather than None), but are empty
    def load_form_factors(self, args):
        # set defaults
        tda = []
        tff = []
        if self.departure_angles:
            # these will be from the config file
            tda = self.departure_angles
            tff = self.form_factors

        # nothing available to replace the current values
        if "F" not in args and "form_factor" not in args:
            pass
        # -f/--form-factor was specified but no departure angle was specified
        elif args.form_factor and not args.departure_angle:
            tda = [45.0]
            tff = [args.form_factor]
        # F is in args, but with no meaningful data - in this case we pull in
        # the form_factor/departure_angle pair that are in the arguments, or we
        # leave things unchanged if neither of them are available
        elif not args.F or len(args.F) == 0:
            # if we have arguments, use them
            if args.departure_angle and args.form_factor:
                tda = [math.radians(args.departure_angle)]
                tff = [args.form_factor]
        # finally we have the case where F is available with useful data
        elif len(args.F) > 0:
            tda = []
            tff = []
            for ff in args.F:
                (da, ff) = ff.split(',')
                da = math.radians(float(da))
                ff = float(ff)
                tda.append(da)
                tff.append(ff)
        # these need to be sorted
        self.departure_angles = tda
        self.form_factors = tff
        self.sort_form_factors()

    def clear_form_factors(self):
        self.departure_angles = []
        self.form_factors = []

    def update_form_factors(self, da, ff):
        self.departure_angles.append(da)
        self.form_factors.append(ff)
        self.sort_form_factors()

    def reset_form_factors(self, ffs):
        if len(ffs) == 0:
            self.departure_angles = []
            self.form_factors = []
            return
        tda, tff = zip(*ffs)
        self.departure_angles = list(tda)
        self.form_factors = list(tff)
        self.sort_form_factors()

    def sort_form_factors(self):
        if len(self.departure_angles) == 0:
            return
        z = zip(self.departure_angles, self.form_factors)
        z.sort(key=lambda k: k[0])
        tda, tff = zip(*z)
        self.departure_angles = list(tda)
        self.form_factors = list(tff)

    def get_FF(self, da):
        # empty list? We've messed up somewhere . . .
        if len(self.departure_angles) == 0:
            raise ValueError("Missing form factors?")
        # only one form factor specified?
        if len(self.departure_angles) == 1:
            return self.form_factors[0]
        i = 1
        while i < len(self.departure_angles) - 1:
            if da < self.departure_angles[i]:
                break
            i += 1
        da1 = self.departure_angles[i - 1]
        da2 = self.departure_angles[i]
        ff1 = self.form_factors[i - 1]
        ff2 = self.form_factors[i]
        return interpolate(da, da1, da2, ff1, ff2)

    def copy_form_factors(self):
        return zip(self.departure_angles, self.form_factors)

    def format_form_factors(self):
        text = ""
        for (da, ff) in zip(self.departure_angles, self.form_factors):
            text += "%.4f: %.6f\n" % (math.degrees(da), ff)
        return text

    # this doesn't fit with the definition from the paper, but the number we
    # get from the code is less than 1 - I'm guessing it's just a question of
    # units (the calculation in the paper would result in units of kg/mm^2,
    # whereas this gives us kg/cm^2). Presumably there's a scaling factor hidden
    # somewhere else that makes it all work, because it does seem to work . . .
    def ballistic_coefficient(self, FF):
        # note that this needs to be in cm rather than mm
        d = self.caliber / 10.0
        return self.mass / (FF * self.air_density_factor * pow(d, 2))

    def retardation(self, alt, v, l, C):
        d = self.atmosphere(alt)
        G = gravity(alt)
        KD = self.get_KD(v, alt)
        R = KD * (DF / 10000.0) * pow(v, 2)
        E = R / (C / d)
        H = E * math.cos(l)
        J = E * math.sin(l) + G
        return (H, J)

    def iterate_estimate(self, alt, v, l, C, x0, y0, h0, j0):
        (H1, J1) = self.retardation(alt, v, l, C)
        H2 = (h0 + H1) / 2.0
        J2 = (j0 + J1) / 2.0
        X2 = x0 - (H2 * self.timestep)
        Y2 = y0 - (J2 * self.timestep)
        V2 = math.sqrt(pow(X2, 2) + pow(Y2, 2))
        L2 = math.atan(Y2 / X2)
        return (X2, Y2, V2, L2)

    def step(self, alt, v, l, C):
        X0 = v * math.cos(l)
        Y0 = v * math.sin(l)
        (H0, J0) = self.retardation(alt, v, l, C)
        X1 = X0 - (H0 * self.timestep)
        Y1 = Y0 - (J0 * self.timestep)
        V1 = math.sqrt(pow(X1, 2) + pow(Y1, 2))
        L1 = math.atan(Y1 / X1)
        MY1 = (Y0 + Y1) / 2.0
        A1 = MY1 * self.timestep
        (X2, Y2, V2, L2) = self.iterate_estimate(alt + A1, V1, L1, C, X0, Y0, H0, J0)
        MY2 = (Y0 + Y2) / 2.0
        A2 = MY2 * self.timestep
        (X3, Y3, V3, L3) = self.iterate_estimate(alt + A2, V2, L2, C, X0, Y0, H0, J0)
        MY3 = (Y0 + Y3) / 2.0
        MX3 = (X0 + X3) / 2.0
        FH = MX3 * self.timestep
        FV = MY3 * self.timestep
        return (FH, FV, V3, L3)

    # for Reasons this takes an argument rather than using the copy we own
    def format_trajectory(self, trajectory=None):
        if not self.show_trajectory:
            return ""
        if not trajectory:
            trajectory = self.Traj
        text = "\nTime Range Height Angle Vel\n"
        if len(trajectory) < 1:
            return text
        (ta, ttt, tr, tv, tl) = trajectory[0]
        del trajectory[0]
        count = 1
        text += "%.2f %.2f %.2f %.2f %.2f\n" % (ttt, tr, ta, math.degrees(tl), tv)
        for (ta, ttt, tr, tv, tl) in trajectory:
            text += "%.2f %.2f %.2f %.2f %.2f\n" % (ttt, tr, ta, math.degrees(tl), tv)
            if count == 5:
                count = 0
                text += "\n"
            count += 1
        text += "\n"
        return text

    def print_trajectory(self, trajectory=None):
        text = self.format_trajectory(trajectory)
        print text

    def one_shot(self, l=None):
        if not l:
            l = self.departure_angle
        ff = self.get_FF(l)
        C = self.ballistic_coefficient(ff)
        tt = 0.0
        rg = 0.0
        alt = self.altitude
        mv = self.mv
        self.Traj = []
        self.Traj.append((alt, tt, rg, mv, l))
        while alt >= 0.0:
            (FH, FV, V, L) = self.step(alt, mv, l, C)
            alt1 = alt
            tt1 = tt
            rg1 = rg
            mv1 = mv
            l1 = l
            rg += FH
            alt += FV
            mv = V
            l = L
            tt += self.timestep
            self.Traj.append((alt, tt, rg, mv, l))
        tt = interpolate(0, alt, alt1, tt, tt1)
        rg = interpolate(0, alt, alt1, rg, rg1)
        mv = interpolate(0, alt, alt1, mv, mv1)
        l = interpolate(0, alt, alt1, l, l1)
        return (tt, rg, mv, l)

    # Knowing the maximum range is important for matching a range using the binary
    # search algorithm we're using below - this is because a binary search is only
    # reliable when the search space is monotonically increasing or decreasing. In
    # the case of ballistic trajectories the range increases smoothly to a maximum,
    # then decreases smoothly down to zero as you continue to increase the
    # departure angle - we're generally only interested in the up side of this
    # curve, so we want to use a binary search on the range space from zero up to
    # the maximum.
    #
    # Since we know that the curve is smooth and well behaved we can use a pretty
    # simple approach to find the maximum: bracketing the maximum value and then
    # narrowing the window until it converges on the maximum. At each iteration we
    # replace the edge of the window that corresponds to the lowest range with a
    # point half-way between the old edge and the mid point.
    def max_range(self):
        tolerance = math.radians(0.05)
        low = math.radians(0.0)
        high = math.radians(90.0)
        rg_max = -1e30
        rg_low = -1000
        rg_high = 0
        da_max = None
        mid = (low + high) / 2.0
        l = (mid + low) / 2.0
        h = (mid + high) / 2.0
        (_, rg_low, _, _) = self.one_shot(l)
        (_, rg_high, _, _) = self.one_shot(h)
        self.count = 2
        while abs(high - low) > tolerance:
            if rg_low < rg_high:
                low = l
                l = (mid + low) / 2.0
                (_, rg_low, _, _) = self.one_shot(l)
            else:
                high = h
                h = (mid + high) / 2.0
                (_, rg_high, _, _) = self.one_shot(h)
            if rg_low > rg_max:
                rg_max = rg_low
                da_max = l
            if rg_high > rg_max:
                rg_max = rg_high
                da_max = h
            mid = (low + high) / 2.0
            self.count += 1
        self.Max_Range = (rg_max, da_max)
        return (rg_max, da_max)

    # split out so that we can reuse this to calculate range tables
    #
    # Note: this will converge on a departure angle of 90 degrees if the projectile
    # can't actually achieve the target range.
    def match_range(self,
                    target_range,
                    tolerance,
                    alt=None,
                    mv=None,
                    l=None):
        if not alt:
            alt = self.altitude
        if not mv:
            mv = self.mv
        if not l:
            l = self.departure_angle
        high = math.radians(90.0)
        if self.Max_Range:
            (rg_max, da_max) = self.Max_Range
            high = da_max
            if target_range > rg_max + 1:
                raise ValueError("Outside maximum range %f" % (rg_max))
        low = math.radians(0.1)
        mid = high
        rg = 1.0e30
        self.count = 0
        while abs(target_range - rg) > tolerance / 2:
            if rg > target_range:
                high = mid
            elif rg < target_range:
                low = mid
            l1 = mid
            mid = (high + low) / 2.0
            rg1 = rg
            (tt, rg, iv, il) = self.one_shot(mid)
            if rg < rg1 and l1 < mid:
                # we're shooting higher and not going as far - we're on the far
                # end of the curve. At this point we need to ...
                pass

            self.count += 1
            if self.count >= 100:
                if abs(high - low) < 0.0001:
                    break
                else:
                    raise ValueError("Could not converge - iteration limit exceeded")
        if mid == math.radians(90.0) and abs(rg) < 0.01:
            raise ValueError("Could not converge")
        return (tt, rg, iv, il, mid)

    def match_form_factor(self, l, tr, tol):
        self.clear_form_factors()
        ff = 1.0
        self.update_form_factors(l, ff)
        (_, rg, _, _) = self.one_shot(l)
        self.count = 1
        while abs(tr - rg) > tol / 2.0 and ff > 0.000001:
            ff = ff * (rg / tr)
            self.clear_form_factors()
            self.update_form_factors(l, ff)
            (_, rg, _, _) = self.one_shot(l)
            self.count += 1
        if ff <= 0.000001:
            raise ValueError("Could not converge - FF at %.6f " % (ff) +
                    "after %d iterations" % (self.count))
        return (ff, l, rg)

    def format_configuration(self):
        text = "Projectile Configuration:\n"
        if self.name:
            text += " Name: %s\n" % (self.name)
        text += " Mass: %.3fkg\n" % (self.mass)
        text += " Caliber: %.3fmm\n" % (self.caliber)
        # we want to list something meaningful here, if at all possible
        if len(self.departure_angles) == 1:
            text += " Form Factor: %.4f\n" % (self.form_factors[0])
        elif len(self.departure_angles) > 1:
            text += " Form Factor data:\n"
            i = 0
            while i < len(self.departure_angles):
                text += "  %.4fdeg: %.6f\n" % (math.degrees(self.departure_angles[i]),
                                               self.form_factors[i])
                i += 1
        if self.drag_function_file:
            text += " Drag Function from file %s\n" % (self.drag_function_file)
        else:
            text += " Drag Function: %s\n" % (self.drag_function)
        text += " Density Function: %s\n" % (self.density_function)
        # we don't want to do this calculation here, so we cache it if it's already
        # been done and use that value
        if self.Max_Range:
            text += "Est. max range: %.1fm at %.4fdeg\n" % (self.Max_Range[0],
                                                            math.degrees(self.Max_Range[1]))
        return text

    def print_configuration(self):
        text = self.format_configuration()
        print text

    def format_initial_conditions(self):
        text = "Initial Conditions:\n"
        text += " Velocity: %.3fm/s\n" % (self.mv)
        # departure angle isn't always set
        if self.departure_angle:
            text += " Departure Angle: %.4fdeg\n" % (math.degrees(self.departure_angle))
        text += " Air Density Factor: %.6f\n" % (self.air_density_factor)
        return text

    def print_initial_conditions(self):
        text = self.format_initial_conditions()
        print text

    def __str__(self):
        text = self.format_configuration()
        text += self.format_initial_conditions()
        return text
