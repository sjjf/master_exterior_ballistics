#!/usr/bin/env python
#
# Translated from the Master Exterior Ballistics Program, written by W. J. Jurens
# with the following copyright header
# **************************************
#   Copyright (c) 1983 W. J. Jurens
#          61 Fidler Avenue
#     Winnipeg, Manitoba, Canada
#             R3J 2R7
#           Ph. 204-837-3125
# **************************************
#
# Translation and subsequent modification by Simon Fowler <sjjfowler@gmail.com>
#

import argparse
import math

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

def ballistic_coefficient(args):
    m = float(args.mass)
    FF = float(args.form_factor)
    AD = float(args.air_density_factor)
    # note that this needs to be in cm rather than mm
    d = float(args.caliber)/10.0
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

kd_KD8 = [
    0.0825,
    0.0825,
    0.0825,
    0.0825,
    0.0825,
    0.094,
    0.14,
    0.172,
    0.175,
    0.175,
    0.1725,
    0.169,
    0.166,
    0.1625,
    0.1605,
    0.157,
    0.1535,
    0.151,
    0.149,
    0.146,
    0.143,
    0.14,
    0.138,
    0.136,
    0.1335,
    0.132,
    0.129,
    0.127,
    0.125,
    0.123,
    0.121,
    0.119,
    0.1175,
    0.116,
    0.1145,
    0.112,
    0.111,
    0.109,
    0.108,
    0.106,
    0.105,
    0.104,
    0.103,
    0.09,
    0.08,
    0.075,
    0.0735,
]

mach_KD8 = [
    0.3,
    0.5,
    0.7,
    0.8,
    0.9,
    0.95,
    1.0,
    1.05,
    1.1,
    1.15,
    1.2,
    1.25,
    1.3,
    1.35,
    1.4,
    1.45,
    1.5,
    1.55,
    1.6,
    1.65,
    1.7,
    1.75,
    1.8,
    1.85,
    1.9,
    1.95,
    2.0,
    2.05,
    2.1,
    2.15,
    2.2,
    2.25,
    2.3,
    2.35,
    2.4,
    2.45,
    2.5,
    2.55,
    2.6,
    2.65,
    2.7,
    2.75,
    2.8,
    3.25,
    3.8,
    4.15,
    4.4,
]

def get_KD(v, alt):
    mach = v/(CS - (0.004*alt))
    for i in range(1, len(mach_KD8)):
        if mach < mach_KD8[i]:
            break
    m1 = mach_KD8[i-1]
    m2 = mach_KD8[i]
    k1 = kd_KD8[i-1]
    k2 = kd_KD8[i]
    return ((mach - m1)/(m2 - m1))*(k2 - k1) + k1

def parse_args():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument('-v', '--mv', action='store', required=True,
                        help='Initial velocity')
    parser.add_argument('-m', '--mass', action='store', required=True,
                        help='Projectile mass')
    parser.add_argument('-c', '--caliber', action='store', required=True,
                        help='Projectile caliber')
    parser.add_argument('-f', '--form-factor', action='store', required=True,
                        help='Projectile form factor')
    parser.add_argument('-a', '--altitude', action='store', required=False,
                        help='Initial altitude (default 0)', default="0.0")
    parser.add_argument('-l', '--departure_angle', action='store', required=True,
                        help="Angle of elevation")
    parser.add_argument('-I', '--timestep', action='store', required=False,
                        help="Simulation timestep", default="0.1")
    parser.add_argument('--air-density-factor', action='store', required=False,
                        help='Air density adjustment factor (default 1.0)',
                        default="1.0")
    parser.add_argument('--density-function', action='store', required=True,
                        choices=['US', 'UK', 'ICAO'],
                        help=(
                            'Density Function: US Pre-1945 std, British std,'
                            'ICAO std'
                        ),
                        default="US")
    return parser.parse_args()

def main() :
    args = parse_args()
    print args

    set_atmosphere(args)
    C = ballistic_coefficient(args)
    alt = float(args.altitude)
    l = math.radians(float(args.departure_angle))
    mv = float(args.mv)
    if "timestep" in args:
        global I
        I = float(args.timestep)
    rg = 0.0
    tt = 0.0
    print C, alt, l, mv, I, rg, tt

    print "Time Range Height Angle Vel"
    print round(tt, 2), round(rg, 2), round(alt, 2), round(math.degrees(l), 2), round(mv, 2)
    while alt >= 0.0:
        (FH, FV, V, L) = step(alt, mv, l, C)
        print round(tt, 2), round(rg, 2), round(alt, 2), round(math.degrees(l), 2), round(mv, 2)
        rg += FH
        alt += FV
        mv = V
        l = L
        tt += I
    print "Final conditions:"
    print "Time of flight: %f" %(tt)
    print "Range: %f" % (rg)
    print "Impact Angle: %f" % (math.degrees(l))
    print "Impact Velocity: %f" % (mv)

if __name__ == '__main__':
    main()
