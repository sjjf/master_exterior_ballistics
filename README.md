# Master Exterior Ballistics Program

A simple exterior ballistics modeling tool based on code written by W. J.
Jurens, published in Warship International, No. 1, 1984, "Exterior Ballistics
with Microcomputers".

The code is designed to emulate the calculations that were done to generate
range tables prior to the convergence of exterior ballistics and aerodynamics.
This may make the method used a little opaque to more aerodynamically minded
users, but the underlying concepts are closely related and can be easily
translated (though the details are beyond the scope of this document).

# WARNING

Though some effort has been made to ensure that this code is well behaved and
correctly models real world ballistics, this code has no warranty and is not
distributed as fit for any purpose. The results should should be confirmed by
other methods before being used for anything other than casual purposes.

# Licensing

The original BASIC code is distributed with the following notice:

```
The program given in this paper can be freely reproduced if used in strictly
non-commercial applications.
```

The Python reimplementation is distributed under the terms of the GNU General
Public License, Version 3 or later.

# Basic Theory of Operation

At its core this code calculates the trajectory of a projectile by applying
the basic equations of motion to the initial conditions to calculate the
position after a single timestep, and then iterating that process until the
projectile moves below altitude 0 (i.e. hits the ground). The basic model is
modified by a drag model which applies a resistive force to the projectile
throughout it's trajectory.

At the core of the drag model is the ballistic coefficient C, which is
determined by the mass and caliber of the projectile, and the drag function,
which is an empirically derived measure of the drag the projectile experiences
across a wide range of velocities. These are then used to calculate the
retarding force that acts on the projectile - the actual drag force the
projectile experiences.

The drag function is determined by the projectile shape. There are multiple
drag functions that have been used historically, each most directly applicable
to one variety of projectile - blunt ogival nosed projectiles, conical nosed
projectiles, long secant ogival nosed projectiles, variations on boattails,
and so on. To account for differences between the test projectiles that were
used to derive the drag function, a form factor is used to scale the chosen
drag function to match the performance of the real projectile.

The form factor is specified as a single floating point number, using the
`--form-factor` command line option. Since it acts to scale the retarding force
experienced by the projectile, a larger form factor results in more drag, and a
shorter range.

Drag functions in this program are presented as a CSV formatted table of mach
numbers mapped to drag coefficient values. Historical drag functions are
available in the `drag_functions` directory, and can be selected using the
`--drag-function` option. Additional drag function tables can be added manually
to this directory, or a drag function file can be specified directly on the
command line using the `--drag-function-file` option.

The model performance may also be modified using the `--air-density-factor`
option, which applies a scaling factor to the ballistic coefficient to account
for changes in air density.

# Modes of Use

This program can be used in a number of ways: to model a single "firing" of a
projectile; to estimate the form factor required to replicate the performance
of a known projectile with a given drag function; to calculate the maximum
range of a given projectile configuration; and to calculate range tables.

In all these modes the projectile configuration is specified by the mass,
caliber, drag function and form factor. A single "shot" will also specify the
departure angle and initial velocity; an attempt to match a range will specify
the initial velocity and allow the departure angle to vary until shots achieve
the targeted range; and an attempt to find the form factor will specify the
initial velocity, departure angle, and the expected range for the shot, and
then vary the form factor until the shot matches the specified range.

## Single Run

The simplest use case is to fire a single projectile and track its trajectory.
In this mode the projectile caliber, mass, form factor and drag function are
required, along with the initial velocity and departure angle. The output is
the time of flight and range at which the projectile fell below the zero
altitude mark, the impact velocity and impact angle, with the option to print
out the trajectory in detail.

## Form Factor Derivation

In order to derive the form factor required to match a particular projectile's
performance a known set of initial velocity, angle of departure, and range must
be specified. The program then performs multiple runs varying only the form
factor until a shot matching the specified conditions is achieved.

## Maximum Range Calculation

In this mode the program will perform multiple runs to search for the departure
angle which results in the maximum range for particular projectile configuration
, displaying the range and departure angle found.

## Range Table Calculation

The program supports creating two varieties of range table, one calculated for
increments of departure angle, and one calculated for increments of range -
this method emulates historical range tables. The start and end values can be
specified, as well as the increments.

# Limitations

The program is intended to emulate the methods used historically to calculate
range tables, and hence does *not* implement more sophisticated methods that
would be applied in modern exterior ballistics code. Projectile motion is
modeled as a set of linear steps; drag coefficients are derived from tabular
data using linear interpolation; the atmospheric models supplied are simplistic
in the extreme both in terms of density at altitude and determining the speed of
sound. While these reflect the methods used historically they also constrain the
accuracy of the results, both in absolute terms and in terms of matching
historical data. Minor differences in the digitisation of calculations that
were originally done by hand, as well as differences in the digitisation of the
input data, lead to small but significant differences between the historical
results and the results of the program. A good match will have variations from
known data of less than 1% in most cases, but a closer match than that should
not be expected.

# Further Documentation

Some documented examples are available in the [examples](/examples) directory,
in particular the [range table recreation
example](/examples/16in_modeling_run.md). The program also prints usage
information when run with the `-h` or `--help` options, both for the main
program and for each of the commands.

