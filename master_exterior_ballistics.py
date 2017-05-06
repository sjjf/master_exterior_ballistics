#!/usr/bin/env python
#
# Translated from the Master Exterior Ballistics Program, written by W. J. Jurens
# with the following copyright header
# **************************************
#   Copyright (c) 1983 W. J. Jurens
#          62 Fidler Avenue
#     Winnipeg, Manitoba, Canada
#             R3J 2R7
#           Ph. 204-837-3125
# **************************************
#
# Translation and subsequent modification by Simon Fowler <sjjfowler@gmail.com>
#

import argparse
import math
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
CS = 344

# ICAO atmospheric model constants
Z4 = 1.34279408e-18
Z3 = 9.87941429e-14
Z2 = 3.90848966e-9
Z1 = 9.69888125e-5

def atmosphere_icao(alt):
    return Z4 * alt**4 + Z3 * alt**3 + Z2 * alt**2 + Z1 * alt + 1

def atmosphere_US(alt):
    return 10**-(0.000045*alt)

def atmosphere_UK(alt):
    return .1**(.141*(alt/3048.0))

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
# whereas this gvies us kg/cm^2). Presumably there's a scaling factor hidden
# somewhere else that makes it all work, because it does seem to work . . .
def ballistic_coefficient(m, FF, AD, d):
    # note that this needs to be in cm rather than mm
    d = d/10.0
    return m/(FF*AD*d**2)

# little bit cheaty, but eh
I = 0.1

def retardation(alt, v, l, C):
    d = atmosphere(alt)
    G = gravity(alt)
    KD = get_KD(v, alt)
    R = KD*(DF/10000.0)*v**2
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
    V2 = math.sqrt(X2**2 + Y2**2)
    L2 = math.atan(Y2/X2)
    return (X2, Y2, V2, L2)

def step(alt, v, l, C):
    X0 = v*math.cos(l)
    Y0 = v*math.sin(l)
    (H0, J0) = retardation(alt, v, l, C)
    X1 = X0 - (H0 * I)
    Y1 = Y0 - (J0 * I)
    V1 = math.sqrt(X1**2 + Y1**2)
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
    tt1 = 0.0
    rg1 = 0.0
    mv1 = 0.0
    l1 = 0.0
    alt1 = 0.0
    if args.print_trajectory:
        print "Time Range Height Angle Vel"
        print round(tt, 2), round(rg, 2), round(alt, 2), round(math.degrees(l), 2), round(mv, 2)
    while alt >= 0.0:
        (FH, FV, V, L) = step(alt, mv, l, C)
        if args.print_trajectory:
            print round(tt, 2), round(rg, 2), round(alt, 2), round(math.degrees(l), 2), round(mv, 2)
        rg1 = rg
        tt1 = tt
        mv1 = mv
        l1 = l
        alt1 = alt
        rg += FH
        alt += FV
        mv = V
        l = L
        tt += I
    tt = interpolate(0, alt, alt1, tt, tt1)
    rg = interpolate(0, alt, alt1, rg, rg1)
    mv = interpolate(0, alt, alt1, mv, mv1)
    l = interpolate(0, alt, alt1, l, l1)
    return (tt, rg, mv, l)

def interpolate(a, x1, x2, y1, y2):
    # a is a value between x1 and x2 - interpolate a value between y1 and y2
    return y1 + ((y2 - y1)*((a - x1)/x2 - x1))

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

def single_run(args):
    (alt, l, mv, C) = common_setup(args)
    print "Initial conditions:"
    print "Projectile Caliber: %.1fmm" % (args.caliber)
    if args.drag_function_file:
        print "Projectile drag function from file %s" % (args.drag_function_file)
    else:
        print "Projectile drag function: %s" % (args.drag_function)
    print "Projectile mass: %.3fkg" % (args.mass)
    print "Initial Velocity: %.3fm/s" % (mv)
    print "Departure Angle: %.4fdeg" % (math.degrees(l))
    print "Form Factor: %.6f" % (args.form_factor)
    print "Air Density Factor: %.6f" % (args.air_density_factor)
    print "Calculated Ballistic Coefficient: %fkg/cm^2" % (C)
    print ""

    (tt, rg, iv, l) = one_shot(alt, mv, l, C, args)
    print "Final conditions:"
    print "Time of flight: %.2fs" %(tt)
    print "Range: %.2fm" % (rg)
    print "Impact Angle: %.4fdeg" % (math.degrees(l))
    print "Impact Velocity: %.2fm/s" % (iv)

# split out so that we can reuse this to calculate range tables
#
# Note: this will converge on a departure angle of 90 degrees if the projectile
# can't actually achieve the target range.
def _match_range(target_range, tolerance, alt, mv, C, args):
    low = math.radians(0.1)
    high = math.radians(90.0)
    mid = (high + low)/2.0
    (tt, rg, iv, il) = one_shot(alt, mv, mid, C, args)
    count = 0
    while abs(target_range - rg) > tolerance:
        if rg > target_range:
            high = mid
        elif rg < target_range:
            low = mid
        mid = (high + low)/2.0
        (tt, rg, iv, il) = one_shot(alt, mv, mid, C, args)
        count += 1
        if count >= 100:
            if abs(high - low) < 0.0001:
                break
            else:
                print "Iteration limit exceeded calculating range and angle not converged"
                sys.exit(1)
    if mid == math.radians(90.0) and abs(rg) < 0.01:
        raise ValueError("Could not converge")
    return (tt, rg, iv, il, mid)

def match_range(args):
    (alt, _, mv, C) = common_setup(args)
    target_range = args.target_range
    tolerance = args.range_tolerance
    try:
        (tt, rg, iv, il, l) = _match_range(target_range,
                                           tolerance,
                                           alt,
                                           mv,
                                           C,
                                           args)
    except ValueError:
        print "Could not converge on range %.1fm" % (target_range)
        sys.exit(0)
    print "Range %.1fm matched at the following conditions:" % (target_range)
    print "Range: %.1fm" % (rg)
    print "Initial Velocity: %.4fm/s" % (mv)
    print "Departure Angle: %.4fdeg" % (math.degrees(l))
    print "Time of flight: %.2fs" % (tt)
    print "Impact Angle: %.4fdeg" % (math.degrees(il))
    print "Impact Velocity: %.2fm/s" % (iv)

def match_form_factor(args):
    (alt, l, mv, _) = common_setup(args)
    target_range = args.target_range
    tolerance = args.range_tolerance
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
    while abs(target_range - rg) > tolerance:
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
    print "Form Factor found for projectile at the following conditions:"
    print "Target Range: %.2fm" % (target_range)
    if args.drag_function_file:
        print "Drag Function from file %s" % (args.drag_function_file)
    else:
        print "Drag Function: %s" % (args.drag_function)
    print "Form Factor: %.6f" % (mid)

def range_table(args):
    (alt, _, mv, C) = common_setup(args)
    increment = args.increment
    start = args.start
    end = args.end
    print "Range Table"
    print "Projectile mass: %.3fkg" % (args.mass)
    print "Initial velocity: %.4fm/s" % (mv)
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
                                               C,
                                               args)
            print "% 6.0f % 8.4f % 8.4f % 6.2f % 8.2f" % (
                    rg,
                    math.degrees(l),
                    math.degrees(il),
                    tt,
                    iv
                )
            target_range += increment
        except ValueError as e:
            # range is too great - break out
            break

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
    return ((m - m1)/(m2 - m1))*(k2 - k1) + k1

def add_common_args(parser):
    parser.add_argument('-v', '--mv', action='store', required=True,
                        type=float, help='Initial velocity')
    parser.add_argument('-m', '--mass', action='store', required=True,
                        type=float, help='Projectile mass')
    parser.add_argument('-c', '--caliber', action='store', required=True,
                        type=float, help='Projectile caliber')
    parser.add_argument('-a', '--altitude', action='store', required=False,
                        type=float,
                        help='Initial altitude (default 0)',
                        default="0.0")
    parser.add_argument('-I', '--timestep', action='store', required=False,
                        type=float, help="Simulation timestep", default="0.1")
    parser.add_argument('--air-density-factor', action='store', required=False,
                        type=float,
                        help='Air density adjustment factor (default 1.0)',
                        default="1.0")
    parser.add_argument('--density-function', action='store', required=False,
                        choices=['US', 'UK', 'ICAO'],
                        help=(
                            'Density Function: US Pre-1945 std, British std,'
                            'ICAO std (default US)'
                        ),
                        default="US")
    parser.add_argument('--drag-function', action='store', required=False,
                        help="Drag function to use (default KD8)", default="KD8")
    parser.add_argument('--drag-function-file', action='store', required=False,
                        help="File to read drag function data from")

def add_match_args(parser):
    parser.add_argument('--target-range', action='store', required=True,
                        type=float, help='Target range')
    parser.add_argument('--range-tolerance', action='store', required=False,
                        type=float, default=1.0,
                        help='Range tolerance')

def parse_args():
#    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(title="Modes of operation",
                                       description="<mode> -h/--help for mode help")
    parser_single = subparsers.add_parser('single', help="Single shot mode")
    parser_single.add_argument('-l', '--departure-angle', action='store',
                               required=True,
                               type=float,
                               help="Departure Angle")
    parser_single.add_argument('-t', '--print-trajectory', action='store_true',
                               required=False, default=False,
                               help="Print projectile trajectory")
    parser_single.add_argument('-f', '--form-factor', action='store', required=True,
                               type=float, help='Projectile form factor')
    add_common_args(parser_single)
    parser_single.set_defaults(func=single_run)
    parser_mr = subparsers.add_parser('match-range',
                                      help=(
                                          "Find the departure angle to achieve"
                                          " the specified target range"
                                      ))
    parser_mr.add_argument('-l', '--departure-angle', action='store',
                           required=False,
                           type=float,
                           default=45.0,
                           help="Initial value for departure angle")

    parser_mr.add_argument('-f', '--form-factor', action='store', required=True,
                           type=float, help='Projectile form factor')

    add_match_args(parser_mr)
    add_common_args(parser_mr)
    parser_mr.set_defaults(func=match_range, print_trajectory=False)
    parser_ff = subparsers.add_parser('find-ff',
                                      help=(
                                          "Find the form factor to achieve the"
                                          " specified target range"
                                      ))
    parser_ff.add_argument('-l', '--departure-angle', action='store',
                                  required=True,
                                  type=float,
                                  help="Departure Angle")
    parser_ff.add_argument('-f', '--form-factor', action='store',
                           required=False,
                           type=float,
                           help='Projectile form factor',
                           default=1.0)

    add_match_args(parser_ff)
    add_common_args(parser_ff)
    parser_ff.set_defaults(func=match_form_factor, print_trajectory=False)
    parser_rt = subparsers.add_parser('range-table',
                                      help="Calculate a range table")
    parser_rt.add_argument('-f', '--form-factor', action='store',
                           required=True,
                           type=float,
                           help='Projectile form factor')
    parser_rt.add_argument('--increment', action='store',
                           required=False,
                           type=float,
                           default=100.0,
                           help='Range steps for range table')
    parser_rt.add_argument('--start', action='store',
                           required=False,
                           type=float,
                           default=100.0,
                           help='Starting range')
    parser_rt.add_argument('--end', action='store',
                           required=False,
                           type=float,
                           default=100000.0,
                           help='End range')
    add_common_args(parser_rt)
    parser_rt.set_defaults(func=range_table,
                           print_trajectory=False,
                           departure_angle=45.0)
    return parser.parse_args()

def main() :
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
