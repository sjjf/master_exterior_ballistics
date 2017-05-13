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
from os import listdir
from os import path
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
Z3 = 9.87941429e-14
Z2 = 3.90848966e-9
Z1 = 9.69888125e-5

def atmosphere_icao(alt):
    return Z4 * alt**4 + Z3 * alt**3 + Z2 * alt**2 + Z1 * alt + 1

def atmosphere_US(alt):
    return 10.0**-(0.000045*alt)

def atmosphere_UK(alt):
    return 0.1**(0.141*(alt/3048.0))

atmosphere = None
def set_atmosphere(args):
    global atmosphere
    if args.density_function == "US":
        atmosphere = atmosphere_US
        return
    if args.density_function == "UK":
        atmosphere = atmosphere_UK
        return
    if args.density_function == "ICAO":
        atmosphere = atmosphere_icao
        return
    print "No atmosphere model specified?"

# this doesn't fit with the definition from the paper, but the number we
# get from the code is less than 1 - I'm guessing it's just a question of
# units (the calculation in the paper would result in units of kg/mm^2,
# whereas this gives us kg/cm^2). Presumably there's a scaling factor hidden
# somewhere else that makes it all work, because it does seem to work . . .
def ballistic_coefficient(m, FF, AD, d):
    # note that this needs to be in cm rather than mm
    d = d/10.0
    return m/(FF*AD*pow(d, 2))

# little bit cheaty, but eh
I = 0.1

def retardation(alt, v, l, C):
    d = atmosphere(alt)
    G = gravity(alt)
    KD = get_KD(v, alt)
    R = KD*(DF/10000.0)*pow(v, 2)
    E = R/(C/d)
    H = E * math.cos(l)
    J = E * math.sin(l) + G
    return (H, J)

def iterate_estimate(alt, v, l, C, x0, y0, h0, j0):
    (H1, J1) = retardation(alt, v, l, C)
    H2 = (h0 + H1)/2.0
    J2 = (j0 + J1)/2.0
    X2 = x0 - (H2*I)
    Y2 = y0 - (J2*I)
    V2 = math.sqrt(pow(X2, 2) + pow(Y2, 2))
    L2 = math.atan(Y2/X2)
    return (X2, Y2, V2, L2)

def step(alt, v, l, C):
    X0 = v*math.cos(l)
    Y0 = v*math.sin(l)
    (H0, J0) = retardation(alt, v, l, C)
    X1 = X0 - (H0 * I)
    Y1 = Y0 - (J0 * I)
    V1 = math.sqrt(pow(X1, 2) + pow(Y1, 2))
    L1 = math.atan(Y1/X1)
    MY1 = (Y0 + Y1)/2.0
    A1 = MY1 * I
    (X2, Y2, V2, L2) = iterate_estimate(alt + A1, V1, L1, C, X0, Y0, H0, J0)
    MY2 = (Y0 + Y2)/2.0
    A2 = MY2 * I
    (X3, Y3, V3, L3) = iterate_estimate(alt + A2, V2, L2, C, X0, Y0, H0, J0)
    MY3 = (Y0 + Y3)/2.0
    MX3 = (X0 + X3)/2.0
    FH = MX3 * I
    FV = MY3 * I
    return (FH, FV, V3, L3)

def one_shot(alt, mv, l, C, args):
    tt = 0.0
    rg = 0.0
    trajectory = []
    trajectory.append((alt, tt, rg, mv, l))
    while alt >= 0.0:
        (FH, FV, V, L) = step(alt, mv, l, C)
        alt1 = alt
        tt1 = tt
        rg1 = rg
        mv1 = mv
        l1 = l
        rg += FH
        alt += FV
        mv = V
        l = L
        tt += I
        trajectory.append((alt, tt, rg, mv, l))
    tt = interpolate(0, alt, alt1, tt, tt1)
    rg = interpolate(0, alt, alt1, rg, rg1)
    mv = interpolate(0, alt, alt1, mv, mv1)
    l = interpolate(0, alt, alt1, l, l1)
    if args.print_trajectory:
        print "Time Range Height Angle Vel"
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
    return (tt, rg, mv, l)

def interpolate(a, x1, x2, y1, y2):
    # a is a value between x1 and x2 - interpolate a corresponding value
    # between y1 and y2
    return y1 + ((y2 - y1)*((a - x1)/(x2 - x1)))

def common_setup(args):
    C = ballistic_coefficient(
            args.mass,
            args.form_factor,
            args.air_density_factor,
            args.caliber)
    alt = args.altitude
    l = math.radians(args.departure_angle)
    mv = args.mv
    if "timestep" in args:
        global I
        I = args.timestep
    return (alt, l, mv, C)

def print_projectile_configuration(args):
    print "Projectile Configuration:"
    print " Mass: %.3fkg" % (args.mass)
    print " Caliber: %.3fmm" % (args.caliber)
    print " Form Factor: %.4f" % (args.form_factor)
    if args.drag_function_file:
        print " Drag Function from file %s" % (args.drag_function_file)
    else:
        print " Drag function: %s" % (args.drag_function)

def print_initial_conditions(args):
    print "Initial Conditions:"
    print " Velocity: %.3fm/s" % (args.mv)
    print " Departure Angle: %.4fdeg" % (args.departure_angle)
    print " Air Density Factor: %.6f" % (args.air_density_factor)

def single_run(args):
    (alt, l, mv, C) = common_setup(args)
    print_projectile_configuration(args)
    print_initial_conditions(args)
    print ""

    (tt, rg, iv, il) = one_shot(alt, mv, l, C, args)
    print "Final conditions:"
    print "Time of flight: %.2fs" % (tt)
    print "Range: %.2fm" % (rg)
    print "Impact Angle: %.4fdeg" % (math.degrees(il))
    print "Impact Velocity: %.2fm/s" % (iv)

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
def _max_range(alt, mv, C, args):
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
    (_, rg_low, _, _) = one_shot(alt, mv, l, C, args)
    (_, rg_high, _, _) = one_shot(alt, mv, h, C, args)
    while abs(high - low) > tolerance:
        if rg_low < rg_high:
            low = l
            l = (mid + low)/2.0
            (_, rg_low, _, _) = one_shot(alt, mv, l, C, args)
        else:
            high = h
            h = (mid + high)/2.0
            (_, rg_high, _, _) = one_shot(alt, mv, h, C, args)
        if rg_low > rg_max:
            rg_max = rg_low
            da_max = l
        if rg_high > rg_max:
            rg_max = rg_high
            da_max = h
        mid = (low + high)/2.0
    return (rg_max, da_max)

def max_range(args):
    (alt, l, mv, C) = common_setup(args)
    print_projectile_configuration(args)
    print ""

    (rg_max, da) = _max_range(alt, mv, C, args)

    print "Maximum range: %.2fm" % (rg_max)
    print "Departure Angle for maximum range: %.4fdeg" % (math.degrees(da))

# split out so that we can reuse this to calculate range tables
#
# Note: this will converge on a departure angle of 90 degrees if the projectile
# can't actually achieve the target range.
def _match_range(target_range,
                 tolerance,
                 alt,
                 mv,
                 l,
                 C,
                 args,
                 rg_max=None,
                 da_max=None):
    high = math.radians(90.0)
    if rg_max and da_max:
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
        (tt, rg, iv, il) = one_shot(alt, mv, mid, C, args)
        if rg < rg1 and l1 < mid:
            # we're shooting higher and not going as far - we're on the far
            # end of the curve. At this point we need to ...
            pass

        count += 1
        if count >= 100:
            if abs(high - low) < 0.0001:
                break
            else:
                print (
                    "Iteration limit exceeded calculating"
                    " range and angle not converged"
                )
                sys.exit(1)
    if mid == math.radians(90.0) and abs(rg) < 0.01:
        raise ValueError("Could not converge")
    return (tt, rg, iv, il, mid)

def match_range(args):
    (alt, l, mv, C) = common_setup(args)
    target_range = args.target_range
    (rg_max, da_max) = _max_range(alt, mv, C, args)
    if target_range > rg_max + 1:
        print "Target range is outside maximum range (%fm)" % (rg_max)
        sys.exit(0)
    tolerance = args.tolerance
    try:
        (tt, rg, iv, il, l) = _match_range(target_range,
                                           tolerance,
                                           alt,
                                           mv,
                                           l,
                                           C,
                                           args)
    except ValueError:
        print "Could not converge on range %.1fm" % (target_range)
        sys.exit(0)
    print_projectile_configuration(args)
    print ""
    print "Range %.1fm matched at the following conditions:" % (target_range)
    print " Range: %.1fm" % (rg)
    print " Initial Velocity: %.4fm/s" % (mv)
    print " Departure Angle: %.4fdeg" % (math.degrees(l))
    print " Time of flight: %.2fs" % (tt)
    print " Impact Angle: %.4fdeg" % (math.degrees(il))
    print " Impact Velocity: %.2fm/s" % (iv)

def match_form_factor(args):
    (alt, l, mv, C) = common_setup(args)
    target_range = args.target_range
    tolerance = args.tolerance
    low = 0.0
    # this is crazy high, but it'll only add a couple of extra steps while
    # making sure we're not accidentally outside the actual range
    high = 10.0
    # not actually the middle, of course . . .
    mid = 1.0
    C = ballistic_coefficient(
            args.mass,
            mid,
            args.air_density_factor,
            args.caliber)
    (tt, rg, iv, il) = one_shot(alt, mv, l, C, args)
    count = 0
    while abs(target_range - rg) > tolerance/2:
        # Note: if the form factor is smaller, the projectile will go further
        # hence we invert the normal ordering tests
        if rg < target_range:
            high = mid
        elif rg > target_range:
            low = mid
        mid = (high + low)/2
        C = ballistic_coefficient(
                args.mass,
                mid,
                args.air_density_factor,
                args.caliber)
        (tt, rg, iv, il) = one_shot(alt, mv, l, C, args)
        count += 1
        if count >= 100:
            print "Iteration limit exceeded calculating form factor"
            sys.exit(1)
    print_projectile_configuration(args)
    print ""
    print "Form Factor: %.6f" % (mid)
    print ""
    print "Form Factor found for projectile at the following conditions:"
    print "Target Range %.2fm matched at:" % (target_range)
    print " Range: %.2fm" % (rg)
    print " Departure Angle: %.4fdeg" % (math.degrees(l))

def range_table(args):
    (alt, l, mv, C) = common_setup(args)
    (rg_max, da_max) = _max_range(alt, mv, C, args)
    increment = args.increment
    start = args.start
    end = args.end
    print "Range Table"
    print_projectile_configuration(args)
    print "Initial velocity: %.4fm/s" % (mv)
    print "Air Density Factor: %.4f" % (args.air_density_factor)
    print "Range increments: %.1fm" % (increment)
    print ""
    print " Range Departure Angle of Time of Striking"
    print "        Angle      Fall   Flight    Vel."
    print "-------------------------------------------"
    target_range = start
    tolerance = 1.0
    while True:
        try:
            (tt, rg, iv, il, l) = _match_range(target_range,
                                               tolerance,
                                               alt,
                                               mv,
                                               l,
                                               C,
                                               args,
                                               rg_max=rg_max,
                                               da_max=da_max)
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
    (alt, _, mv, C) = common_setup(args)
    increment = math.radians(args.increment)
    l = math.radians(args.start)
    end = math.radians(args.end)
    print "Range Table"
    print_projectile_configuration(args)
    print "Initial velocity: %.4fm/s" % (mv)
    print "Air Density Factor: %.4f" % (args.air_density_factor)
    print "Departure Angle increments: %.1fdeg" % (math.degrees(increment))
    print ""
    print " Range Departure Angle of Time of Striking"
    print "        Angle      Fall   Flight    Vel."
    print "-------------------------------------------"

    while l <= end and l < 90:
        (tt, rg, iv, il) = one_shot(alt, mv, l, C, args)
        print "% 6.0f % 8.4f % 8.4f % 6.2f % 8.2f" % (
                                                      rg,
                                                      math.degrees(l),
                                                      math.degrees(il),
                                                      tt,
                                                      iv)
        l += increment

mach = []
kd = []

def load_drag_function(df_filename):
    try:
        with open(df_filename) as df:
            mach = []
            kd = []
            for line in df.readlines():
                line = line.strip()
                if line != "":
                    (m, k) = line.split(',', 2)
                    mach.append(float(m))
                    kd.append(float(k))
            return (mach, kd)
    except IOError as e:
        print "Loading drag function failed:", e
        sys.exit(1)

def get_KD(v, alt):
    m = v/(CS - (0.004*alt))
    for i in range(1, len(mach)):
        if m < mach[i]:
            break
    m1 = mach[i-1]
    m2 = mach[i]
    k1 = kd[i-1]
    k2 = kd[i]
    t = ((m - m1)/(m2 - m1))*(k2 - k1) + k1
    return t

def get_drag_functions():
    try:
        dfs = listdir('drag_functions')
        dfs = [path.basename(path.splitext(t)[0]) for t in dfs]
        dfs.sort()
        return dfs
    except OSError as e:
        print "Failed to open drag function directory: %s" % (e)

def add_common_args(parser):
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
        help='Initial altitude (default 0)',
        default="0.0")
    parser.add_argument('-I', '--timestep',
        action='store',
        required=False,
        type=float,
        help="Simulation timestep",
        default="0.1")
    parser.add_argument('--air-density-factor',
        action='store',
        required=False,
        type=float,
        help='Air density adjustment factor (default 1.0)',
        default="1.0")
    parser.add_argument('--density-function',
        action='store',
        required=False,
        choices=['US', 'UK', 'ICAO'],
        help=(
            'Density Function: US Pre-1945 std, British std,'
            'ICAO std (default US)'
        ),
        default="US")
    parser.add_argument('--drag-function',
        action='store',
        required=False,
        choices=get_drag_functions(),
        help="Drag function to use (default KD8)",
        default="KD8")
    parser.add_argument('--drag-function-file',
        action='store',
        required=False,
        help="File to read drag function data from")

def add_match_args(parser):
    parser.add_argument('--target-range',
        action='store',
        required=True,
        type=float,
        help='Target range')
    parser.add_argument('--tolerance',
        action='store',
        required=False,
        type=float,
        default=1.0,
        help='Convergence tolerance')

def parse_args():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(title="Modes of operation",
        description="<mode> -h/--help for mode help")

    parser_single = subparsers.add_parser('single',
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
    parser_single.add_argument('-f', '--form-factor',
        action='store',
        required=True,
        type=float,
        help='Projectile form factor')
    add_common_args(parser_single)
    parser_single.set_defaults(func=single_run)

    parser_mr = subparsers.add_parser('match-range',
        help="Find the departure angle to achieve the specified target range")
    parser_mr.add_argument('-l', '--departure-angle',
        action='store',
        required=False,
        type=float,
        default=45.0,
        help="Initial value for departure angle")
    parser_mr.add_argument('-f', '--form-factor',
        action='store',
        required=True,
        type=float,
        help='Projectile form factor')
    add_match_args(parser_mr)
    add_common_args(parser_mr)
    parser_mr.set_defaults(func=match_range,
        print_trajectory=False)

    parser_ff = subparsers.add_parser('find-ff',
        help="Find the form factor to achieve the specified target range")
    parser_ff.add_argument('-l', '--departure-angle',
        action='store',
        required=True,
        type=float,
        help="Departure Angle")
    parser_ff.add_argument('-f', '--form-factor',
        action='store',
        required=False,
        type=float,
        help='Projectile form factor',
        default=1.0)
    add_match_args(parser_ff)
    add_common_args(parser_ff)
    parser_ff.set_defaults(func=match_form_factor,
        print_trajectory=False)

    parser_rt = subparsers.add_parser('range-table',
        help="Calculate a range table based on range increments")
    parser_rt.add_argument('-f', '--form-factor',
        action='store',
        required=True,
        type=float,
        help='Projectile form factor')
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
    add_common_args(parser_rt)
    parser_rt.set_defaults(func=range_table,
        print_trajectory=False,
        departure_angle=45.0)

    parser_rta = subparsers.add_parser('range-table-angle',
        help="Calculate a range table based on departure angle")
    parser_rta.add_argument('-f', '--form-factor',
        action='store',
        required=True,
        type=float,
        help='Projectile form factor')
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
    add_common_args(parser_rta)
    parser_rta.set_defaults(func=range_table_angle,
        print_trajectory=False,
        departure_angle=45.0)

    parser_mr = subparsers.add_parser('max-range',
        help="Find the maximum range for a given projectile configuration")
    parser_mr.add_argument('-f', '--form-factor',
        action='store',
        required=True,
        type=float,
        help='Projectile form factor')
    add_common_args(parser_mr)
    parser_mr.set_defaults(func=max_range,
        print_trajectory=False,
        departure_angle=45.0)

    return parser.parse_args()

def main():
    args = parse_args()

    global mach
    global kd
    if args.drag_function_file:
        (mach, kd) = load_drag_function(args.drag_function_file)
    else:
        dff = path.join("drag_functions", "%s.conf" % (args.drag_function))
        (mach, kd) = load_drag_function(dff)

    set_atmosphere(args)
    args.func(args)

if __name__ == '__main__':
    main()
