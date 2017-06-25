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
import math
from ConfigParser import SafeConfigParser as cfgparser
from os import path
from master_exterior_ballistics import version
import pkg_resources
import sys

# To make this usable outside the immediate context I'm going to move most
# stuff into a single class and have that class expose the simulation
# functions.

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
    return 10.0**-(0.000045*alt)


def atmosphere_UK(alt):
    return 0.1**(0.141*(alt/3048.0))


def interpolate(a, x1, x2, y1, y2):
    # a is a value between x1 and x2 - interpolate a corresponding value
    # between y1 and y2
    return y1 + ((y2 - y1)*((a - x1)/(x2 - x1)))


def str2bool(v):
    return v.lower() in ['yes', 'true', 'y', 't', '1']


def str2rad(v):
    return math.radians(float(v))


def rad2str(v):
    return str(math.degrees(v))


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

    def __init__(self, args):
        self.load_config(args)
        self.set_atmosphere(args)
        self.load_drag_function(args)
        self.load_form_factors(args)

        if args.altitude:
            self.altitude = args.altitude
        if args.departure_angle:
            self.departure_angle = math.radians(args.departure_angle)
        if args.mv:
            self.mv = args.mv
        if args.caliber:
            self.caliber = args.caliber
        if args.air_density_factor:
            self.air_density_factor = args.air_density_factor
        if args.mass:
            self.mass = args.mass
        if args.timestep:
            self.timestep = args.timestep
        if args.show_trajectory:
            self.show_trajectory = args.show_trajectory

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
            elif not t:
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

    # the drag function can be specified in a file, or picked from a list of
    # already defined options. Anything specified on the command line takes
    # precedence over the config file; in a config file the drag_function_file
    # option takes precedence over the drag_function option
    def load_drag_function(self, args):
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
        for line in df.readlines():
            line = line.strip()
            if line != "":
                (m, k) = line.split(',', 2)
                mach.append(float(m))
                kd.append(float(k))
        self.mach = mach
        self.kd = kd

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
        m = v/(CS - (0.004*alt))
        i = 1
        while i < len(self.mach)-1:
            if m < self.mach[i]:
                break
            i += 1
        m1 = self.mach[i-1]
        m2 = self.mach[i]
        k1 = self.kd[i-1]
        k2 = self.kd[i]
        t = ((m - m1)/(m2 - m1))*(k2 - k1) + k1
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
        while i < len(self.departure_angles)-1:
            if da < self.departure_angles[i]:
                break
            i += 1
        da1 = self.departure_angles[i-1]
        da2 = self.departure_angles[i]
        ff1 = self.form_factors[i-1]
        ff2 = self.form_factors[i]
        return interpolate(da, da1, da2, ff1, ff2)

    # this doesn't fit with the definition from the paper, but the number we
    # get from the code is less than 1 - I'm guessing it's just a question of
    # units (the calculation in the paper would result in units of kg/mm^2,
    # whereas this gives us kg/cm^2). Presumably there's a scaling factor hidden
    # somewhere else that makes it all work, because it does seem to work . . .
    def ballistic_coefficient(self, FF):
        # note that this needs to be in cm rather than mm
        d = self.caliber/10.0
        return self.mass/(FF*self.air_density_factor*pow(d, 2))

    def retardation(self, alt, v, l, C):
        d = self.atmosphere(alt)
        G = gravity(alt)
        KD = self.get_KD(v, alt)
        R = KD*(DF/10000.0)*pow(v, 2)
        E = R/(C/d)
        H = E * math.cos(l)
        J = E * math.sin(l) + G
        return (H, J)

    def iterate_estimate(self, alt, v, l, C, x0, y0, h0, j0):
        (H1, J1) = self.retardation(alt, v, l, C)
        H2 = (h0 + H1)/2.0
        J2 = (j0 + J1)/2.0
        X2 = x0 - (H2*self.timestep)
        Y2 = y0 - (J2*self.timestep)
        V2 = math.sqrt(pow(X2, 2) + pow(Y2, 2))
        L2 = math.atan(Y2/X2)
        return (X2, Y2, V2, L2)

    def step(self, alt, v, l, C):
        X0 = v*math.cos(l)
        Y0 = v*math.sin(l)
        (H0, J0) = self.retardation(alt, v, l, C)
        X1 = X0 - (H0 * self.timestep)
        Y1 = Y0 - (J0 * self.timestep)
        V1 = math.sqrt(pow(X1, 2) + pow(Y1, 2))
        L1 = math.atan(Y1/X1)
        MY1 = (Y0 + Y1)/2.0
        A1 = MY1 * self.timestep
        (X2, Y2, V2, L2) = self.iterate_estimate(alt + A1, V1, L1, C, X0, Y0, H0, J0)
        MY2 = (Y0 + Y2)/2.0
        A2 = MY2 * self.timestep
        (X3, Y3, V3, L3) = self.iterate_estimate(alt + A2, V2, L2, C, X0, Y0, H0, J0)
        MY3 = (Y0 + Y3)/2.0
        MX3 = (X0 + X3)/2.0
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
        mid = (low + high)/2.0
        l = (mid + low)/2.0
        h = (mid + high)/2.0
        (_, rg_low, _, _) = self.one_shot(l)
        (_, rg_high, _, _) = self.one_shot(h)
        self.count = 2
        while abs(high - low) > tolerance:
            if rg_low < rg_high:
                low = l
                l = (mid + low)/2.0
                (_, rg_low, _, _) = self.one_shot(l)
            else:
                high = h
                h = (mid + high)/2.0
                (_, rg_high, _, _) = self.one_shot(h)
            if rg_low > rg_max:
                rg_max = rg_low
                da_max = l
            if rg_high > rg_max:
                rg_max = rg_high
                da_max = h
            mid = (low + high)/2.0
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
        while abs(target_range - rg) > tolerance/2:
            if rg > target_range:
                high = mid
            elif rg < target_range:
                low = mid
            l1 = mid
            mid = (high + low)/2.0
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
        while abs(tr - rg) > tol/2.0:
            ff = ff * (rg/tr)
            self.clear_form_factors()
            self.update_form_factors(l, ff)
            (_, rg, _, _) = self.one_shot(l)
            self.count += 1
        return (ff, l, rg)

    def format_configuration(self):
        text = "Projectile Configuration:\n"
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

    def format_output(self):
        raise NotImplementedError

    def add_arguments(self, subparser):
        raise NotImplementedError

    # this doesn't catch any errors - that's up to higher levels
    def create_projectile(self, args):
        self.projectile = Projectile(args)
        return self.projectile

    def run_analysis(self):
        raise NotImplementedError

    def process(self, args):
        self.create_projectile(args)
        self.run_analysis()


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
            self.projectile = Projectile(args)
            return self.projectile
        except IOError as e:
            print e
        except MissingAttribute as e:
            print e
        print "Exiting"
        sys.exit(1)

    # Override the argument parser to point it at the process_command_line
    # method
    def add_arguments(self, subparser):
        parser = super(CLIMixin, self).add_arguments(subparser)
        parser.set_defaults(func=self.process_command_line)


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
        add_projectile_args(parser)
        add_form_factors(parser)
        add_conditions_args(parser)
        add_common_args(parser)
        return parser

    def run_analysis(self):
        (self.tt, self.rg, self.iv, self.il) = self.projectile.one_shot()


class SingleRunCLI(CLIMixin, SingleRun):
    pass


class MaxRange(Command):

    def format_output(self):
        text = "Maximum range: %.2fm\n" % (self.rg_max)
        text += "Departure Angle for maximum range: %.4fdeg\n" % (math.degrees(self.da))
        return text

    def run_analysis(self):
        (self.rg_max, self.da) = self.projectile.max_range()

    def add_arguments(self, subparser):
        parser = subparser.add_parser('max-range',
            description="Estimate the maximum range for a given projectile configuration",
            help="Find the maximum range for a given projectile configuration")
        add_projectile_args(parser)
        add_form_factors(parser)
        add_conditions_args(parser)
        add_common_args(parser)
        parser.set_defaults(func=self.process_command_line,
            print_trajectory=False)
        return parser


class MaxRangeCLI(CLIMixin, MaxRange):
    pass


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
        add_projectile_args(parser)
        add_form_factors(parser)
        add_conditions_args(parser)
        add_common_args(parser)
        return parser


class MatchRangeCLI(CLIMixin, MatchRange):
    pass


class MatchFormFactor(Command):

    def format_output(self):
        text = "\n"
        text += "Form Factor Results (departure angle, form factor):\n"
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
        self.projectile.clear_form_factors()
        self.projectile.unset_departure_angle()

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
        add_projectile_args(parser)
        add_conditions_args(parser)
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
        add_match_args(parser)
        add_common_args(parser)
        parser.set_defaults(form_factor=1.0)
        return parser


class MatchFormFactorCLI(CLIMixin, MatchFormFactor):
    pass


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
        add_projectile_args(parser)
        add_form_factors(parser)
        add_conditions_args(parser)
        add_common_args(parser)
        return parser


class RangeTableCLI(CLIMixin, RangeTable):
    pass


class RangeTableAngle(RangeTableCommon):

    def run_analysis(self):
        self.increment = math.radians(self.args.increment)
        l = math.radians(self.args.start)
        end = math.radians(self.args.end)
        self.projectile.max_range()
        self.mv = self.projectile.mv
        self.air_density_factor = self.projectile.air_density_factor

        self.shots = []
        while l <= ((end*100+1)/100) and l < 90:
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
        add_projectile_args(parser)
        add_form_factors(parser)
        add_conditions_args(parser)
        add_common_args(parser)
        return parser


class RangeTableAngleCLI(CLIMixin, RangeTableAngle):
    pass


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
        add_projectile_args(parser)
        add_form_factors(parser)
        add_conditions_args(parser)
        add_common_args(parser)
        return parser


class MakeConfigCLI(CLIMixin, MakeConfig):

    # we need to override this because we're not doing any actual processing,
    # just calling one projectile method
    def process_command_line(self, args):
        self.process(args)


# common argument handling
def add_projectile_args(parser):
    g = parser.add_argument_group('projectile')
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


def parse_args():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    # some global defaults . . .
    #
    # these are largely so that these attributes will always exist in the args
    # namespace, rather than needing to check to see if they're there and then
    # check whether they're set to something meaningful
    parser.set_defaults(
        show_trajectory=False,
        mass=None,
        mv=None,
        caliber=None,
        form_factor=None,
        F=None,
        drag_function=None,
        departure_angle=None,
        save_to_config=None,
    )
    parser.add_argument('-V', '--version',
        action='version',
        version="Master Exterior Ballistics version %s" % (version.__version__),
        help='Print program version information')

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
        p = Projectile(args)
        p.to_config(args.write_config)
        print "Config written to %s" % (args.write_config)
        sys.exit(0)

    args.func(args)


if __name__ == '__main__':
    main()
