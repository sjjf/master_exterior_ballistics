# Master Exterior Ballistics Program

A simple exterior ballistics modeling tool based on code written by W. J.
Jurens, published in Warship International, No. 1, 1984, "Exterior Ballistics
with Microcomputers".

The code is designed to emulate the calculations that were done to generate
range tables prior to the convergence of exterior ballistics and aerodynamics.
This may make the method used a little opaque to more aerodynamically minded
users, but the underlying concepts are closely related and can be easily
translated (though the details are beyond the scope of this document).

# Basic Theory of Operation

At its core this code calculates the trajectory of a projectile by applying
the basic equations of motion combined with a drag model to the initial
conditions to calculate the position after a single timestep, and then
iterating that process until the projectile moves below altitude 0 (i.e. hits
the ground).

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
--form-factor command line option.

Drag functions in this program are presented as a CSV formated table of mach
numbers to drag coefficient values. Historical drag functions are available in
the drag_functions directory, and can be selected using the --drag-function
option. Additional drag function tables can be added manually to this
directory, or a drag function file can be specified directly on the command
line using the --drag-function-file option.

# Modes of Use

This program can be used in a number of ways: to model a single "firing" of a
projectile; to estimate the form factor required to replicate the performance
of a known projectile with a given drag function; and to replicate a standard
range table given a form factor and drag function.

## Single Run

The simplest use case is to fire a single projectile and track its trajectory.
In this mode the projectile caliber, mass, form factor and drag function are
required, along with the initial velocity and departure angle. The output is
the time of flight and range at which the projectile fell below the zero
altitude mark, the impact velocity and impact angle.

## Form Factor Derivation

In order to derive the form factor required to match a particular known
projectile's performance the initial velocity, angle of departure, and range
must be specified. The program then performs multiple runs varying only the
form factor, doing a simple binary search to find the form factor that
produces a sufficiently close match to the specified range.

## Range Table Calculation

In this mode the program will calculate a range table for a projectile at a
given initial velocity, form factor and drag function, plotting increments of
the target range against the departure angle, impact velocity and impact
angle.
