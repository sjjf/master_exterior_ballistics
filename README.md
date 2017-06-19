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

# Running the Program

This is currently a pure command line program, and requires the Python 2.7
runtime to be installed. Python can be downloaded from
https://www.python.org/downloads/ for a wide range of platforms, and the
program should run on any platform that Python runs on.

Once Python has been installed the program can be run from within a command
line window (on Unix based systems this can be done using a terminal program
like xterm, on Windows this can be done using the command window or a
powershell window).

An installer is provided for Windows, accessible from the project's github
releases page; for other platforms the recommended installation method is to
download a release tarball and run the setup.py script contained.

Once installed the program can be run by typing `meb` on the command line, for
example:

```
meb --help
```

will print out the basic help text. From there it is strongly recommended that
you read the documentation, in particular the [examples](/examples/).

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

The form factor can be specified as a single floating point number, using the
`--form-factor` command line option, or as a collection of departure angle and
form factor pairs using the `-F` option, which together define a "form factor
function" which is used to determine the form factor across a range of
departure angles.  Since it acts to scale the retarding force experienced by
the projectile, a larger form factor results in more drag, and a shorter range.

Drag functions in this program are presented as a CSV formatted table of mach
numbers mapped to drag coefficient values. Historical drag functions are
available in the `drag_functions` directory, and can be selected using the
`--drag-function` option. Additional drag function tables can be added manually
to this directory, or a drag function file can be specified directly on the
command line using the `--drag-function-file` option.

The model performance may also be modified using the `--air-density-factor`
option, which applies a simple scaling factor to the ballistic coefficient to
account for changes in air density.

In addition, there is support for writing a projectile configuration to a config
file that can be re-used - this can make the program much easier to use.

# Modes of Use

This program can be used in a number of ways: to model a single "firing" of a
projectile; to estimate the form factor(s) required to replicate the
performance of a known projectile with a given drag function under specified
conditions; to estimate the maximum range of a given projectile configuration;
and to calculate range tables.

In all these modes the projectile configuration is specified by the mass,
caliber, drag function and some form factor data. A single "shot" will also
specify the departure angle and initial velocity; an attempt to match a range
will specify the initial velocity and allow the departure angle to vary until
shots achieve the targeted range; and an attempt to determine the form factor
data will specify the initial velocity, departure angle, and the expected range
for the set of known shots, and then vary the form factor until each shot
matches the specified range.

All the command line arguments can also be specified in a configuration file.
Add the `--write-config` argument to a command line and specify a filename (or a
single - to specify writing to the console) for a sample of the format.

## Single Run

The simplest use case is to fire a single projectile and track its trajectory.
In this mode the projectile caliber, mass, form factor and drag function are
required, along with the initial velocity and departure angle. The output is
the time of flight and range at which the projectile fell below the zero
altitude mark, the impact velocity and impact angle, with the option to print
out the trajectory in detail.

## Form Factor Derivation

In order to derive the form factor required to match a particular projectile's
performance for a known set of initial conditions a target range and angle of
departure must be specified. The program then performs multiple runs varying
only the form factor until a shot matching the specified conditions is
achieved. Support is also included for specifying a list of departure angle and
range pairs, with each of these pairs being modeled separately. Finally, it's
possible to write a projectile configuration file with the newly calculated form
factor data.

Note that the form factor is not consistent across all possible initial
conditions, since it attempts to encapsulate a range of physical properties not
all of which are constant for all mach numbers. In most cases the form factor
will need to be specified for multiple departure angles in order to achieve
results consistent with historical data.

## Maximum Range Calculation

In this mode the program will perform multiple runs to search for the departure
angle which results in the maximum range for a particular projectile
configuration, displaying the range and departure angle found. Due to
variability in the form factor this should be considered a reasonable estimate,
not a precise calculation.

## Range Table Calculation

The program supports creating two varieties of range table, one calculated for
increments of departure angle, and one calculated for increments of range -
this method emulates historical range tables. The start and end values can be
specified, as well as the increments.

Without source data across the full range being modeled this will produce a
very rough estimate, since the form factor will almost certainly vary
significantly across the range table. The best results will be obtained by
"filling in" the gaps in an already well specified range table.

# Limitations and Caveats

The program is intended to emulate the methods used historically to calculate
range tables, and hence does *not* implement more sophisticated methods that
would be applied in modern exterior ballistics code. Projectile motion is
modeled as a set of linear steps; drag coefficients are derived from tabular
data using linear interpolation; the atmospheric models supplied are simplistic
in the extreme both in terms of density at altitude and determining the speed of
sound. In addition, the use of the program cannot automate away all the manual
work done historically during the compilation of range tables - to achieve good
results the user needs to have a solid understanding of the constraints and
limitations of the methodology the program is implementing.

While the intent is to reflect the methods used historically this also
constrains the accuracy of the results, both in absolute terms and in terms of
matching historical data. The available data at this point is vastly more
limited than that available to the historical engineers compiling the original
range tables and gun performance data, meaning that attempting to apply the same
methodology will inevitably require assumptions, estimates and approximations
for any missing data. In addition, minor differences in the digitisation of
calculations that were originally done by hand, as well as differences in the
digitisation of the input data, lead to small but significant differences
between the historical results and the results of the program.

A good result will have variations from known data of less than 1% in most
cases, but a closer match than that should not be expected. Where insufficient
information is available the results will represent at best a reasonable
estimate, and the results should be reported with appropriate care.

# Further Documentation

Some documented examples are available in the [examples](/examples) directory,
in particular the [range table recreation
example](/examples/16in_modeling_run.md). The program also prints usage
information when run with the `-h` or `--help` options, both for the main
program and for each of the commands.

