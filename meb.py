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
from os import listdir
from os import path
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

class Projectile(object):

    I = 0.1
    ALT = None
    M = None
    Cal = None
    MV = None
    L = None
    Traj = []
    Max_Range = None
    mach = []
    kd = []
    departure_angles = []
    form_factors = []
    drag_function = None
    drag_function_file = None

    def __init__(self, args):
        self.set_atmosphere(args)
        self.load_drag_function(args)
        self.load_form_factors(args)

        self.ALT = args.altitude
        self.L = 0.0
        if args.departure_angle:
            self.L = math.radians(args.departure_angle)
        self.MV = args.mv
        self.Cal = args.caliber
        self.AD = args.air_density_factor
        self.M = args.mass
        if "timestep" in args:
            self.I = args.timestep

    # write out an ini-formatted config file for this projectile
    # If filename is not given, write to stdout
    def to_config(self, filename=None):
        cfg = cfgparser()
        cfg.add_section("projectile")
        cfg.set("projectile", "mass", repr(self.M))
        cfg.set("projectile", "caliber", repr(self.Cal))
        if self.drag_function_file:
            cfg.set("projectile", "drag_function_file", self.drag_function_file)
        else:
            cfg.set("projectile", "drag_function", self.drag_function)
        cfg.set("projectile", "density_function", self.density_function)

        cfg.add_section("form_factor")
        for (da, ff) in zip(self.departure_angles, self.form_factors):
            cfg.set("form_factor", repr(math.degrees(da)), repr(ff))

        cfg.add_section("initial_conditions")
        cfg.set("initial_conditions", "alt", repr(self.ALT))
        cfg.set("initial_conditions", "mv", repr(self.MV))
        cfg.set("initial_conditions", "l", repr(math.degrees(self.L)))
        cfg.set("initial_conditions", "ad", repr(self.AD))

        cfg.add_section("simulation")
        cfg.set("simulation", "timestep", repr(self.I))

        if filename:
            with open(filename, "w") as outfile:
                cfg.write(outfile)
            return
        cfg.write(sys.stdout)

    # these are the only things that change during the lifetime of the
    # projectile object
    def set_alt(self, alt):
        self.ALT = alt

    def set_departure_angle(self, l):
        self.L = l

    def set_mv(self, mv):
        self.MV = mv

    def set_atmosphere(self, args):
        self.atmosphere = None
        self.density_function = args.density_function
        if args.density_function == "US":
            self.atmosphere = atmosphere_US
            return
        if args.density_function == "UK":
            self.atmosphere = atmosphere_UK
            return
        if args.density_function == "ICAO":
            self.atmosphere = atmosphere_icao
            return
        print "No atmosphere model specified?"

    def load_drag_function(self, args):
        self.drag_function = None
        self.drag_function_file = None
        if args.drag_function_file:
            self.drag_function_file = args.drag_function_file
            self._load_drag_function(args.drag_function_file)
        else:
            dff = path.join("drag_functions", "%s.conf" % (args.drag_function))
            self.drag_function = args.drag_function
            self._load_drag_function(dff)

    def _load_drag_function(self, df_filename):
        try:
            with open(df_filename) as df:
                self.mach = []
                self.kd = []
                for line in df.readlines():
                    line = line.strip()
                    if line != "":
                        (m, k) = line.split(',', 2)
                        self.mach.append(float(m))
                        self.kd.append(float(k))
        except IOError as e:
            print "Loading drag function failed:", e
            sys.exit(1)

    # this is a class method so that we can access it without needing an object
    @classmethod
    def get_drag_functions(cls):
        try:
            dfs = listdir('drag_functions')
            dfs = [path.basename(path.splitext(t)[0]) for t in dfs]
            dfs.sort()
            return dfs
        except OSError as e:
            print "Failed to open drag function directory: %s" % (e)

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

    def load_form_factors(self, args):
        tda = []
        tff = []
        if not args.F or len(args.F) == 0:
            tda.append(math.radians(args.departure_angle))
            tff.append(args.form_factor)
        else:
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
        z = zip(self.departure_angles, self.form_factors)
        z.sort(key=lambda k: k[0])
        tda, tff = zip(*z)
        self.departure_angles = list(tda)
        self.form_factors = list(tff)

    def get_FF(self, da):
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
        d = self.Cal/10.0
        return self.M/(FF*self.AD*pow(d, 2))

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
        X2 = x0 - (H2*self.I)
        Y2 = y0 - (J2*self.I)
        V2 = math.sqrt(pow(X2, 2) + pow(Y2, 2))
        L2 = math.atan(Y2/X2)
        return (X2, Y2, V2, L2)

    def step(self, alt, v, l, C):
        X0 = v*math.cos(l)
        Y0 = v*math.sin(l)
        (H0, J0) = self.retardation(alt, v, l, C)
        X1 = X0 - (H0 * self.I)
        Y1 = Y0 - (J0 * self.I)
        V1 = math.sqrt(pow(X1, 2) + pow(Y1, 2))
        L1 = math.atan(Y1/X1)
        MY1 = (Y0 + Y1)/2.0
        A1 = MY1 * self.I
        (X2, Y2, V2, L2) = self.iterate_estimate(alt + A1, V1, L1, C, X0, Y0, H0, J0)
        MY2 = (Y0 + Y2)/2.0
        A2 = MY2 * self.I
        (X3, Y3, V3, L3) = self.iterate_estimate(alt + A2, V2, L2, C, X0, Y0, H0, J0)
        MY3 = (Y0 + Y3)/2.0
        MX3 = (X0 + X3)/2.0
        FH = MX3 * self.I
        FV = MY3 * self.I
        return (FH, FV, V3, L3)

    # for Reasons this takes an argument rather than using the copy we own
    def print_trajectory(self, trajectory):
        print "Time Range Height Angle Vel"
        if len(trajectory) < 1:
            return
        (ta, ttt, tr, tv, tl) = trajectory[0]
        del trajectory[0]
        count = 1
        print "%.2f %.2f %.2f %.2f %.2f" % (ttt, tr, ta, math.degrees(tl), tv)
        for (ta, ttt, tr, tv, tl) in trajectory:
            print "%.2f %.2f %.2f %.2f %.2f" % (ttt, tr, ta, math.degrees(tl), tv)
            if count == 5:
                count = 0
                print ""
            count += 1
        print ""

    def one_shot(self, l=None):
        if not l:
            l = self.L
        ff = self.get_FF(l)
        C = self.ballistic_coefficient(ff)
        tt = 0.0
        rg = 0.0
        alt = self.ALT
        mv = self.MV
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
            tt += self.I
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
        alt = self.ALT
        mv = self.MV
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
            alt = self.ALT
        if not mv:
            mv = self.MV
        if not l:
            l = self.L
        high = math.radians(90.0)
        if self.Max_Range:
            (rg_max, da_max) = self.Max_Range
            high = da_max
            if target_range > rg_max + 1:
                raise ValueError("Outside maximum range %f" % (rg_max))
        low = math.radians(0.1)
        mid = high
        rg = 1.0e30
        count = 0
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

            count += 1
            if count >= 100:
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
        count = 0
        while abs(tr - rg) > tol/2.0:
            ff = ff * (rg/tr)
            self.clear_form_factors()
            self.update_form_factors(l, ff)
            (_, rg, _, _) = self.one_shot(l)
            count += 1
        return (ff, l, rg, count)

    def print_configuration(self):
        print "Projectile Configuration:"
        print " Mass: %.3fkg" % (self.M)
        print " Caliber: %.3fmm" % (self.Cal)
        # we want to list something meaningful here, if at all possible
        if len(self.departure_angles) == 1:
            print " Form Factor: %.4f" % (self.form_factors[0])
        elif len(self.departure_angles) > 1:
            print " Form Factor data:"
            i = 0
            while i < len(self.departure_angles):
                print "  %.4fdeg: %.6f" % (math.degrees(self.departure_angles[i]),
                                       self.form_factors[i])
                i += 1
        if self.drag_function_file:
            print " Drag Function from file %s" % (self.drag_function_file)
        else:
            print " Drag function: %s" % (self.drag_function)
        # we don't want to do this calculation here, so we cache it if it's already
        # been done and use that value
        if self.Max_Range:
            print "Est. max range: %.2fm at %.4fdeg" % (self.Max_Range[0],
                                                        math.degrees(self.Max_Range[1]))

    def print_initial_conditions(self):
        print "Initial Conditions:"
        print " Velocity: %.3fm/s" % (self.MV)
        print " Departure Angle: %.4fdeg" % (self.L)
        print " Air Density Factor: %.6f" % (self.AD)


def single_run(args):
    p = Projectile(args)
    p.print_configuration()
    p.print_initial_conditions()
    print ""

    (tt, rg, iv, il) = p.one_shot()
    if args.print_trajectory:
        p.print_trajectory(Traj)
    print "Final conditions:"
    print "Time of flight: %.2fs" % (tt)
    print "Range: %.2fm" % (rg)
    print "Impact Angle: %.4fdeg" % (math.degrees(il))
    print "Impact Velocity: %.2fm/s" % (iv)

def max_range(args):
    p = Projectile(args)
    p.print_configuration()
    print ""

    (rg_max, da) = p.max_range()

    print "Maximum range: %.2fm" % (rg_max)
    print "Departure Angle for maximum range: %.4fdeg" % (math.degrees(da))

def match_range(args):
    p = Projectile(args)
    target_range = args.target_range
    (rg_max, da_max) = p.max_range()
    if target_range > rg_max + 1:
        print "Target range is outside maximum range (%fm)" % (rg_max)
        sys.exit(0)
    tolerance = args.tolerance
    try:
        (tt, rg, iv, il, l) = p.match_range(target_range,
                                            tolerance)
    except ValueError:
        print "Could not converge on range %.1fm" % (target_range)
        sys.exit(0)
    p.print_configuration()
    print ""
    print "Range %.1fm matched at the following conditions:" % (target_range)
    print " Range: %.1fm" % (rg)
    print " Initial Velocity: %.4fm/s" % (p.MV)
    print " Departure Angle: %.4fdeg" % (math.degrees(p.L))
    print " Time of flight: %.2fs" % (tt)
    print " Impact Angle: %.4fdeg" % (math.degrees(il))
    print " Impact Velocity: %.2fm/s" % (iv)

# the form factor is close to linearly related to the range for a given
# departure angle, so we can use a very focused search scheme
def match_form_factor(args):
    target_range = args.target_range
    tolerance = args.tolerance
    p = Projectile(args)
    shots = []
    if args.shot:
        for shot in args.shot:
            (da, tr) = shot.split(',')
            da = math.radians(float(da))
            tr = float(tr)
            (ff, l, rg, count) = p.match_form_factor(da, tr, tolerance)
            shots.append((ff, l, rg, count))
    else:
        (ff, l, rg, count) = p.match_form_factor(p.L, target_range, tolerance)
        shots.append((ff, l, rg, count))
        print "Converged after %d iterations" % (count)
    # the form factor currently cached is meaningless at the moment, so clear
    # it rather than print it along with the rest of the projectile
    # configuration
    p.clear_form_factors()
    p.print_configuration()
    print ""
    print "Form Factor Results (departure angle, form factor):"
    for ((ff, l, rg, count)) in shots:
        print " %.4f,%.6f" % (math.degrees(l), ff)

def range_table(args):
    p = Projectile(args)
    (rg_max, da_max) = p.max_range()
    increment = args.increment
    start = args.start
    end = args.end
    print "Range Table"
    p.print_configuration()
    print "Initial velocity: %.4fm/s" % (p.MV)
    print "Air Density Factor: %.4f" % (p.AD)
    print "Range increments: %.1fm" % (increment)
    print ""
    print " Range Departure Angle of Time of Striking"
    print "        Angle      Fall   Flight    Vel."
    print "-------------------------------------------"
    target_range = start
    tolerance = 1.0
    l = 1.0
    while True:
        try:
            (tt, rg, iv, il, l) = p.match_range(target_range,
                                               tolerance)
            print "% 6.0f % 8.4f % 8.4f % 6.2f % 8.2f" % (
                    rg,
                    math.degrees(l),
                    math.degrees(il),
                    tt,
                    iv
                )
            target_range += increment
            if rg > end:
                break
        except ValueError:
            # range is too great - break out
            break

def range_table_angle(args):
    p = Projectile(args)
    increment = math.radians(args.increment)
    l = math.radians(args.start)
    end = math.radians(args.end)
    (rg_max, da_max) = p.max_range()
    print "Range Table"
    p.print_configuration()
    print "Initial velocity: %.4fm/s" % (p.MV)
    print "Air Density Factor: %.4f" % (p.AD)
    print "Departure Angle increments: %.1fdeg" % (math.degrees(increment))
    print ""
    print " Range Departure Angle of Time of Striking"
    print "        Angle      Fall   Flight    Vel."
    print "-------------------------------------------"

    while l <= ((end*100+1)/100) and l < 90:
        (tt, rg, iv, il) = p.one_shot(l)
        print "% 6.0f % 8.4f % 8.4f % 6.2f % 8.2f" % (
                                                      rg,
                                                      math.degrees(l),
                                                      math.degrees(il),
                                                      tt,
                                                      iv)
        l += increment

def add_common_args(parser):
    parser.add_argument('--config',
        action='store',
        required=False,
        help='Config file')
    parser.add_argument('--write-config',
        action='store',
        required=False,
        help='Write config from the command line to a file')
    parser.add_argument('-v', '--mv',
        action='store',
        required=True,
        type=float,
        help='Initial velocity')
    parser.add_argument('-m', '--mass',
        action='store',
        required=True,
        type=float,
        help='Projectile mass')
    parser.add_argument('-c', '--caliber',
        action='store',
        required=True,
        type=float,
        help='Projectile caliber')
    parser.add_argument('-a', '--altitude',
        action='store',
        required=False,
        type=float,
        default=0.01,
        help='Initial altitude (default 0)')
    parser.add_argument('-I', '--timestep',
        action='store',
        required=False,
        type=float,
        default=0.1,
        help="Simulation timestep")
    parser.add_argument('--air-density-factor',
        action='store',
        required=False,
        type=float,
        default=1.0,
        help='Air density adjustment factor (default 1.0)')
    parser.add_argument('--density-function',
        action='store',
        required=False,
        choices=['US', 'UK', 'ICAO'],
        default="US",
        help=(
            'Density Function: US Pre-1945 std, British std,'
            'ICAO std (default US)'
        ))
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--drag-function',
        action='store',
        choices=Projectile.get_drag_functions(),
        default="KD8",
        help="Drag function to use (default KD8)")
    g.add_argument('--drag-function-file',
        action='store',
        help="File to read drag function data from")

def add_match_args(parser):
    parser.add_argument('--target-range',
        action='store',
        type=float,
        help='Target range')
    parser.add_argument('--tolerance',
        action='store',
        required=False,
        type=float,
        default=1.0,
        help='Convergence tolerance')

def add_form_factors(parser, required=True):
    g = parser.add_mutually_exclusive_group(required=required)
    g.add_argument('-f', '--form-factor',
        action='store',
        type=float,
        help='Projectile form factor')
    g.add_argument('-F',
        action='append',
        metavar='FF,A',
        help=(
            '(form factor, departure angle) tuple - used to specify a set of'
            ' form factors that will be used to determine the form factor'
            ' for a given shot by interpolation'
        ))

def parse_args():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(title="Modes of operation",
        description="<mode> -h/--help for mode help")

    parser_single = subparsers.add_parser('single',
        description="Simulate a single shot",
        help="Single shot mode")
    parser_single.add_argument('-l', '--departure-angle',
        action='store',
        required=True,
        type=float,
        help="Departure Angle")
    parser_single.add_argument('-t', '--print-trajectory',
        action='store_true',
        required=False,
        default=False,
        help="Print projectile trajectory")
    add_form_factors(parser_single)
    add_common_args(parser_single)
    parser_single.set_defaults(func=single_run)

    parser_mr = subparsers.add_parser('match-range',
        description="Match the target range by adjusting departure angle",
        help="Find the departure angle to achieve the specified target range")
    parser_mr.add_argument('-l', '--departure-angle',
        action='store',
        required=False,
        type=float,
        default=45.0,
        help="Initial value for departure angle")
    add_form_factors(parser_mr)
    add_match_args(parser_mr)
    add_common_args(parser_mr)
    parser_mr.set_defaults(func=match_range,
        print_trajectory=False)

    parser_ff = subparsers.add_parser('find-ff',
        description="Match the shot(s) specified by adjusting the form fator",
        help="Find the form factor to achieve the specified target range")
    parser_ff.add_argument('-l', '--departure-angle',
        action='store',
        type=float,
        default=45.0,
        help="Departure Angle")
    parser_ff.add_argument('--shot',
        action='append',
        required=False,
        metavar='A,R',
        help=(
            'Set of <angle,range> tuples - may be used more than once, with '
            'each tuple being simulated'
        ))
    add_match_args(parser_ff)
    add_common_args(parser_ff)
    parser_ff.set_defaults(func=match_form_factor,
        form_factor=1.0,
        print_trajectory=False)

    parser_rt = subparsers.add_parser('range-table',
        description="Calculate a range table based on range increments",
        help="Calculate a range table based on range increments")
    parser_rt.add_argument('--increment',
        action='store',
        required=False,
        type=float,
        default=100.0,
        help='Range steps for range table')
    parser_rt.add_argument('--start',
        action='store',
        required=False,
        type=float,
        default=100.0,
        help='Starting range')
    parser_rt.add_argument('--end',
        action='store',
        required=False,
        type=float,
        default=100000.0,
        help='End range')
    add_form_factors(parser_rt)
    add_common_args(parser_rt)
    parser_rt.set_defaults(func=range_table,
        print_trajectory=False,
        departure_angle=45.0)

    parser_rta = subparsers.add_parser('range-table-angle',
        description="Calculate a range table based on departure angle increments",
        help="Calculate a range table based on departure angle")
    parser_rta.add_argument('--increment',
        action='store',
        required=False,
        type=float,
        default=1.0,
        help='Departure angle steps for range table')
    parser_rta.add_argument('--start',
        action='store',
        required=False,
        type=float,
        default=1.0,
        help='Starting departure angle')
    parser_rta.add_argument('--end',
        action='store',
        required=False,
        type=float,
        default=50.0,
        help='End departure angle')
    add_form_factors(parser_rta)
    add_common_args(parser_rta)
    parser_rta.set_defaults(func=range_table_angle,
        print_trajectory=False,
        departure_angle=45.0)

    parser_mar = subparsers.add_parser('max-range',
        description="Estimate the maximum range for a given projectile configuration",
        help="Find the maximum range for a given projectile configuration")
    add_form_factors(parser_mar)
    add_common_args(parser_mar)
    parser_mar.set_defaults(func=max_range,
        print_trajectory=False,
        departure_angle=45.0)

    return parser.parse_args()

def main():
    args = parse_args()

    if args.print_trajectory:
        global print_traj
        print_traj = True

    if args.write_config:
        p = Projectile(args)
        p.to_config(args.write_config)
        print "Config written to %s" % (args.write_config)
        sys.exit(0)

    args.func(args)

if __name__ == '__main__':
    main()
