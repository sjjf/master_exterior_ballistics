# Example Modeling Run

This document provides an example of replicating a historical range table
using the program, following the process from determining the projectile
configuration through to re-creating the historical range table to verify the
veracity of the replication.

The historical range table data being used here is available
[here](/examples/16in_rt.md).

# Basic Projectile Configuration

The basic details are quite simple, and mostly involve converting the listed
data from imperial to metric.

The projectile is a 16" caliber, 2100 pound bullet that pre-dates 1935. The
table is calculated at 2600f/s initial velocity. 16 inches is 406.4mm, 2100
pounds is 952.544kg, and 2600f/s is 792.48m/s - these are the common elements
that will be used throughout the modeling run.

# Trajectory Data

Each line in the table presents a single shot, with the departure angle (in
degrees and minutes), the range, angle of fall (again in degrees and minutes),
time of flight, and striking velocity. The independent variable is the range,
with the specified angle being the one required to reach that range - the
table is presented this way because in a gunnery situation the desired range
is known and the departure angle is the information required to make the shot.

The final row specifies a range of 39,600 yards, and indicates that a
departure angle of 45 degrees, 14.9 minutes are required to reach that range.
Converting to metric (and decimal degrees), this gives us 36,210.24m and
45.2483 degrees. The impact angle is 55 degrees, 54 minutes, at 1,559
feet/second - 55.9 degrees, 475.18m/s - after 94.6s. The metric equivalent is
thus:

```
36,210 45.2483 55.9 94.6 475.2
```

# Initial Assumptions

In addition to this information we need to know the drag function and the form
factor in order to be able to replicate this range table.

The drag function can be chosen based on some knowledge of the age and type of
the projectile - in this case, a pre-1935 US design. The closest easy match
would be the KD6 drag function, though the KD1 drag function may also be
appropriate depending on the age of the design in 1935. We'll start with the
KD6 function and see what results we get.

The form factor can only be determined by comparing test shots with the
historical data, but the best option when starting is to specify the form
factor as 1.0 and see how it goes.

# A single shot

To model a single shot the program should be run with the command `single`:

```
$ meb single -h

usage: meb single [-h] -l DEPARTURE_ANGLE [-t] [-m MASS] [-c CALIBER]
                  [--density-function {US,UK,ICAO}]
                  [--drag-function {1938,1940,KD1,KD2,KD6,KD7,KD8} | --drag-function-file DRAG_FUNCTION_FILE]
                  [-f FORM_FACTOR | -F FF,A] [-v MV] [-a ALTITUDE]
                  [--air-density-factor AIR_DENSITY_FACTOR] [--config CONFIG]
                  [--write-config WRITE_CONFIG] [-I TIMESTEP]
                  [--tolerance TOLERANCE]

Simulate a single shot

optional arguments:
  -h, --help            show this help message and exit

shot specifics:
  -l DEPARTURE_ANGLE, --departure-angle DEPARTURE_ANGLE
                        Departure Angle
  -t, --print-trajectory, --show-trajectory
                        Print projectile trajectory

projectile:
  -m MASS, --mass MASS  Projectile mass
  -c CALIBER, --caliber CALIBER
                        Projectile caliber
  --density-function {US,UK,ICAO}
                        Density Function: US Pre-1945 std, British std,ICAO
                        std (default US)
  --drag-function {1938,1940,KD1,KD2,KD6,KD7,KD8}
                        Drag function to use (default KD8)
  --drag-function-file DRAG_FUNCTION_FILE
                        File to read drag function data from

form factors:
  -f FORM_FACTOR, --form-factor FORM_FACTOR
                        Projectile form factor
  -F FF,A               (form factor, departure angle) tuple - used to specify
                        a set of form factors that will be used to determine
                        the form factor for a given shot by interpolation

conditions:
  -v MV, --mv MV        Initial velocity
  -a ALTITUDE, --altitude ALTITUDE
                        Initial altitude (default 0)
  --air-density-factor AIR_DENSITY_FACTOR
                        Air density adjustment factor (default 1.0)

common options:
  --config CONFIG       Config file
  --write-config CONFIG
                        Write config from the command line to a file
  -I TIMESTEP, --timestep TIMESTEP
                        Simulation timestep
  --tolerance TOLERANCE
                        Convergance tolerance
```

Putting the values we determined above onto the command line gives this:

```
$ meb single -m 952.544 -c 406.4 -v 792.48 \
        -l 45.2483 -f 1.0 --drag-function KD6
```

This produces the following output:

```
Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0000
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 45.2483deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 95.14s
Range: 36149.81m
Impact Angle: -56.6591deg
Impact Velocity: 465.34m/s
```

This resulted in a shot that went slightly short of the target range, indicating
that the modelled drag was slightly too high. This can be adjusted by decreasing
the form factor, for example to 0.9.

```
$ ./meb.py single -m 952.544 -c 406.4 -v 792.48 \
    -l 45.2483 -f 0.9 --drag-function KD6

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 0.9000
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 45.2483deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 96.77s
Range: 38032.45m
Impact Angle: -55.6598deg
Impact Velocity: 485.19m/s
```

This time the range is significantly beyond the target, indicating that the form
factor is too low - the correct form factor will be somewhere in between.

# Finding the Form Factor

We could continue with the above approach to narrow down the form factor,
narrowing it down to whatever precision we desired. However, the program
supports doing this automatically, using the `find-ff` command:

```
$ meb find-ff -h

usage: meb find-ff [-h] [--save-to-config SAVE_TO_CONFIG] [-m MASS]
                   [-c CALIBER] [--density-function {US,UK,ICAO}]
                   [--drag-function {1938,1940,KD1,KD2,KD6,KD7,KD8} | --drag-function-file DRAG_FUNCTION_FILE]
                   [-v MV] [-a ALTITUDE]
                   [--air-density-factor AIR_DENSITY_FACTOR] [--shot A,R]
                   [-l DEPARTURE_ANGLE] [--target-range TARGET_RANGE]
                   [--config CONFIG] [--write-config WRITE_CONFIG]
                   [-I TIMESTEP] [--tolerance TOLERANCE]

Match the shot(s) specified by adjusting the form fator

optional arguments:
  -h, --help            show this help message and exit
  --save-to-config CONFIG
                        Save the calculated form factors to the given config
                        file

projectile:
  -m MASS, --mass MASS  Projectile mass
  -c CALIBER, --caliber CALIBER
                        Projectile caliber
  --density-function {US,UK,ICAO}
                        Density Function: US Pre-1945 std, British std,ICAO
                        std (default US)
  --drag-function {1938,1940,KD1,KD2,KD6,KD7,KD8}
                        Drag function to use (default KD8)
  --drag-function-file DRAG_FUNCTION_FILE
                        File to read drag function data from

conditions:
  -v MV, --mv MV        Initial velocity
  -a ALTITUDE, --altitude ALTITUDE
                        Initial altitude (default 0)
  --air-density-factor AIR_DENSITY_FACTOR
                        Air density adjustment factor (default 1.0)

match multiple shots:
  --shot A,R            Set of <angle,range> tuples - may be used more than
                        once, with each tuple being simulated

match single shot:
  -l DEPARTURE_ANGLE, --departure-angle DEPARTURE_ANGLE
                        Departure Angle
  --target-range TARGET_RANGE
                        Target range

common options:
  --config CONFIG       Config file
  --write-config CONFIG
                        Write config from the command line to a file
  -I TIMESTEP, --timestep TIMESTEP
                        Simulation timestep
  --tolerance TOLERANCE
                        Convergance tolerance
```

Given the other elements of the projectile configuration (the mass, caliber and
drag function), this command will find the form factor that is needed to match a
specified shot (a target range and a departure angle).

Using the previously specified shot, with a target range of 36210m at a
departure angle of 45.2483 degrees:

```
$ meb find-ff -m 952.544 -c 406.4 -v 792.48 \
         --drag-function KD6 --target-range 36210 -l 45.2483

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Air Density Factor: 1.000000

Form Factor Results (departure angle, form factor):
 45.2483,0.996695 (8 iterations)
```

The program has found the required form factor to match the shot - 0.996695. As
expected this is between 1.0 and 0.9, the bracketing values we found manually.

To verify that this is correct we can re-run the single shot mode that we tried
before, using the new value for the form factor:

```
$ meb single -m 952.544 -c 406.4 -v 792.48
        -l 45.2483 -f 0.996695 --drag-function KD6

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 0.9967
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 45.2483deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 95.19s
Range: 36209.51m
Impact Angle: -56.6269deg
Impact Velocity: 465.96m/s
```

As expected, the calculated range is 36210m; the impact angle is 56.6 degrees,
compared with 55.9 degrees in the original data; the time of flight is 95.2s
compared with 94.6; and the impact velocity is 465.96m/s compared with 475.2m/s.
These variations are on the order of one or two percent, which is reasonable
given that the original terminal data was mostly derived rather than direct
measurements.

It's important to understand that the form factor isn't consistent across the
full range of available departure angles - it's a simple linear scaling factor
applied to the drag function, and hence cannot capture variations in performance
that aren't linearly related to the drag function. This means that in order to
match an existing range table it will be necessary to use a range of different
form factors.

To get an idea about how closely the chosen drag model matches the performance
of the projectile we can use data from other parts of the range table to
calculate alternative form factors.

Taking the first row in our sample, converted to metric:

```
33832.8 35.4617 47.8 77.7 448.0
```

Modeling this shot gives us:

```
$ meb single -m 952.544 -c 406.4 -v 792.48 \
        -l 35.4617 -f 0.996695 --drag-function KD6

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 0.9967
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 35.4617deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 78.24s
Range: 33834.29m
Impact Angle: -48.5307deg
Impact Velocity: 435.86m/s
```

These numbers are very close, though not a perfect match in all details - in
particular, the range is only a couple of meters off the target. This indicates
that for these two shots the KD6 drag model is a close match for the real
performance. We can go back and run the find-ff command again with this shot as
the target data to quantify this match:

```
$ meb find-ff -m 952.544 -c 406.4 -v 792.48 \
        --drag-function KD6 --target-range 33832.8 -l 35.4617

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Air Density Factor: 1.000000

Form Factor Results (departure angle, form factor):
 35.4617,0.996803 (9 iterations)
```

The resulting form factor differs by 0.0001, or about 1 parts in 10000,
confirming that the match is excellent.

This result is a little unusual, but it makes it easy for us to recreate the
snippet of the range table that we're working with - we can use the same form
factor across the whole of the range table without any issues.

# Recreating the Range Table

Now that we have a form factor and drag model, we can attempt to recreate the
original range table. The data we have starts at a range of 37000 yards and
continues to 39600 yards, and increments by 100 yards - converting this to
metric gives a range from 33832.8m to 36210m in 91.44m increments. The range
table can be replicated using the `range-table` command:

```
$ meb range-table --help

usage: meb range-table [-h] [--increment INCREMENT] [--start START]
                       [--end END] [-m MASS] [-c CALIBER]
                       [--density-function {US,UK,ICAO}]
                       [--drag-function {1938,1940,KD1,KD2,KD6,KD7,KD8} | --drag-function-file DRAG_FUNCTION_FILE]
                       [-f FORM_FACTOR | -F FF,A] [-v MV] [-a ALTITUDE]
                       [--air-density-factor AIR_DENSITY_FACTOR]
                       [--config CONFIG] [--write-config WRITE_CONFIG]
                       [-I TIMESTEP] [--tolerance TOLERANCE]

Calculate a range table based on range increments

optional arguments:
  -h, --help            show this help message and exit

range table options:
  --increment INCREMENT
                        Range steps for range table
  --start START         Starting range
  --end END             End range

projectile:
  -m MASS, --mass MASS  Projectile mass
  -c CALIBER, --caliber CALIBER
                        Projectile caliber
  --density-function {US,UK,ICAO}
                        Density Function: US Pre-1945 std, British std,ICAO
                        std (default US)
  --drag-function {1938,1940,KD1,KD2,KD6,KD7,KD8}
                        Drag function to use (default KD8)
  --drag-function-file DRAG_FUNCTION_FILE
                        File to read drag function data from

form factors:
  -f FORM_FACTOR, --form-factor FORM_FACTOR
                        Projectile form factor
  -F FF,A               (form factor, departure angle) tuple - used to specify
                        a set of form factors that will be used to determine
                        the form factor for a given shot by interpolation

conditions:
  -v MV, --mv MV        Initial velocity
  -a ALTITUDE, --altitude ALTITUDE
                        Initial altitude (default 0)
  --air-density-factor AIR_DENSITY_FACTOR
                        Air density adjustment factor (default 1.0)

common options:
  --config CONFIG       Config file
  --write-config CONFIG
                        Write config from the command line to a file
  -I TIMESTEP, --timestep TIMESTEP
                        Simulation timestep
  --tolerance TOLERANCE
                        Convergance tolerance
```

The projectile details stay the same, and we simply specify the start, end and
increment:

```
$ meb range-table -m 952.544 -c 406.4 -v 792.48 \
        -f 0.996695 --drag-function KD6 --start 33832.8 --end 36210 \
        --increment 91.44

Range Table
Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 0.9967
 Drag Function: KD6
 Density Function: US
Est. max range: 36301.8m at 47.4681deg
Initial velocity: 792.4800m/s
Air Density Factor: 1.0000
Range increments: 91.4m

 Range Departure Angle of Time of Striking
        Angle      Fall   Flight    Vel.
-------------------------------------------
 33833  35.4584 -48.5276  78.23   435.85
 33924  35.6955 -48.7487  78.67   436.51
 34015  35.9383 -48.9735  79.11   437.20
 34107  36.1869 -49.2020  79.56   437.91
 34199  36.4385 -49.4316  80.01   438.64
 34290  36.6929 -49.6620  80.47   439.38
 34382  36.9560 -49.8986  80.95   440.14
 34473  37.2220 -50.1359  81.42   440.93
 34564  37.4937 -50.3767  81.91   441.74
 34656  37.7742 -50.6232  82.41   442.57
 34747  38.0604 -50.8729  82.92   443.43
 34839  38.3553 -51.1282  83.44   444.32
 34930  38.6560 -51.3866  83.98   445.23
 35021  38.9682 -51.6527  84.53   446.18
 35113  39.2920 -51.9265  85.10   447.18
 35205  39.6245 -52.2053  85.68   448.20
 35295  39.9685 -52.4914  86.28   449.26
 35388  40.3328 -52.7918  86.91   450.39
 35479  40.7087 -53.0991  87.56   451.56
 35570  41.1076 -53.4224  88.25   452.81
 35662  41.5297 -53.7613  88.98   454.14
 35753  41.9807 -54.1201  89.74   455.56
 35845  42.4722 -54.5073  90.58   457.11
 35936  43.0100 -54.9266  91.49   458.81
 36028  43.6171 -55.3947  92.50   460.74
 36119  44.3341 -55.9407  93.69   463.04
 36210  45.2593 -56.6350  95.21   466.00
```

Converting the output to imperial units for a direct comparison is an exercise
left to the reader, but a quick eyeballing of the easily comparable numbers
suggest that the departure angles found for each range are close but not perfect
matches, and the terminal conditions are within a percent of the original data.

# A Better Match

In a case like this where the form factor was so consistent across a range of
departure angles it may be worth creating a full range table using this form
factor, but without having access to a wider range of data any extensions beyond
the table produced above would be of questionable validity. However, within the
range of data that we have any simulated shots should be a solid match for
reality.

In a case where the match was less close we can specify multiple values for the
form factor, and the program will interpolate between them when calculating
intermediate ranges. We can determine the form factor for a number of different
known scenarios at once using the `--shot` option:

```
$ meb find-ff -m 952.544 -c 406.4 -v 792.48 --drag-function KD6 \
        --shot 35.4617,33832.8 \
        --shot 45.2483,36210

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Air Density Factor: 1.000000

Form Factor Results (departure angle, form factor):
 35.4617,0.996803 (9 iterations)
 45.2483,0.996695 (8 iterations)
```

Each `--shot` option specifies the departure angle and the target range, and
the program will calulate the form factor for each. There is no limit to the
number of times this option can be used.

Once we have the form factors we can use the `-F` option to pass in a list of
departure angle to form factor pairs - as noted above, the program will
interpolate between the available data points to determine the form factor for
a given departure angle:

```
$ meb range-table -m 952.544 -c 406.4 -v 792.48 --drag-function KD6 \
        --start 33832.8 --end 36210 --increment 91.44 \
        -F 35.4617,0.996803 \
        -F 45.2483,0.996695

Range Table
Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor data:
  35.4617deg: 0.996803
  45.2483deg: 0.996695
 Drag Function: KD6
 Density Function: US
Est. max range: 36302.3m at 47.4757deg
Initial velocity: 792.4800m/s
Air Density Factor: 1.0000
Range increments: 91.4m

 Range Departure Angle of Time of Striking
        Angle      Fall   Flight    Vel.
-------------------------------------------
 33832  35.4612 -48.5313  78.24   435.84
 33924  35.7012 -48.7551  78.68   436.51
 34016  35.9441 -48.9799  79.12   437.20
 34107  36.1898 -49.2058  79.56   437.90
 34198  36.4414 -49.4353  80.02   438.63
 34290  36.6988 -49.6683  80.48   439.37
 34381  36.9590 -49.9022  80.95   440.14
 34472  37.2250 -50.1396  81.43   440.92
 34565  37.4997 -50.3829  81.92   441.74
 34655  37.7773 -50.6268  82.42   442.57
 34747  38.0636 -50.8765  82.93   443.43
 34839  38.3585 -51.1318  83.45   444.32
 34930  38.6621 -51.3926  83.99   445.24
 35022  38.9744 -51.6587  84.54   446.19
 35113  39.2954 -51.9300  85.10   447.17
 35204  39.6279 -52.2088  85.68   448.20
 35296  39.9749 -52.4973  86.29   449.27
 35387  40.3335 -52.7929  86.91   450.38
 35479  40.7152 -53.1049  87.57   451.57
 35570  41.1113 -53.4258  88.26   452.82
 35662  41.5335 -53.7648  88.98   454.14
 35754  41.9875 -54.1258  89.76   455.57
 35844  42.4732 -54.5084  90.58   457.11
 35936  43.0111 -54.9277  91.49   458.81
 36027  43.6183 -55.3958  92.50   460.74
 36118  44.3296 -55.9374  93.68   463.02
 36210  45.2550 -56.6318  95.20   465.99
```

The differences between the two tables are extremely small, but in a case where
the drag function was a less perfect match the result of this will be a better
match for reality. Given sufficient source data this method can be used to give
a reliable result across a wide range of departure angles, always with the
proviso that moving outside the range of the source data can affect the
reliability and accuracy of the results.

# Configuration from a File

The program can also load the projectile configuration from a file, containing
the projectile details, the initial conditions and basic simulation
configuration. The following is a configuration file that can be used to
replicate the range table above:

```
[projectile]
mass = 952.544
caliber = 406.4
drag_function = KD6
density_function = US

[form_factor]
35.4617 = 0.996803
45.2483 = 0.996695

[initial_conditions]
altitude = 0.0001
mv = 792.48
air_density_factor = 1.0

[simulation]
timestep = 0.1
```

The mass, caliber, drag function, density function and form factors define the
basic projectile; the initial conditions define the environmental scenario, and
the simulation configuration defines the behaviour of the simulation.

This configuration file can be produced by simply appending the `--write-config`
argument to the command line that produced the range table:

```
$ meb range-table -m 952.544 -c 406.4 -v 792.48 --drag-function KD6 \
        --start 33832.8 \
        --end 36210 \
        --increment 91.44 \
        -F 35.4617,0.996803 \
        -F 45.2483,0.996695 \
        --write-config -

[projectile]
mass = 952.544
caliber = 406.4
drag_function = KD6
density_function = US

[form_factor]
35.4617 = 0.996803
45.2483 = 0.996695

[initial_conditions]
altitude = 0.0001
mv = 792.48
air_density_factor = 1.0

[simulation]
timestep = 0.1

Config written to -
```

Note that the special filename '-' causes the program to write to the console
rather than to a file.

Once written to a file, the range table command above can be greatly simplified
by using the config file:

```
$ meb range-table --config test.conf \
        --start 33832.8 \
        --end 36210 \
        --increment 91.44

Range Table
Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor data:
  35.4617deg: 0.996803
  45.2483deg: 0.996695
 Drag Function: KD6
 Density Function: US
Est. max range: 36302.3m at 47.4757deg
Initial velocity: 792.4800m/s
Air Density Factor: 1.0000
Range increments: 91.4m

<snip>
```

This is particularly useful when a projectile requires a large range of form
factors to model its behaviour.

The `--config` argument can be used anywhere, in lieu of all the regular
projectile specification arguments. For example, it can make the `max-range`
command particularly simple:

```
$ meb max-range --config test.conf

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor data:
  35.4617deg: 0.996803
  45.2483deg: 0.996695
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Air Density Factor: 1.000000

Maximum range: 36302.28m
Departure Angle for maximum range: 47.4757deg
```

Any argument specified on the command line will override the contents of the
file, allowing you to explore the behaviour of a projectile without having to do
lots of typing:

```
$ meb max-range --config test.conf --mv 780

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor data:
  35.4617deg: 0.996803
  45.2483deg: 0.996695
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 780.000m/s
 Air Density Factor: 1.000000

Maximum range: 35235.52m
Departure Angle for maximum range: 47.3147deg
```

or

```
$ meb max-range --config test.conf --air-density-factor 0.95

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor data:
  35.4617deg: 0.996803
  45.2483deg: 0.996695
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Air Density Factor: 0.950000

Maximum range: 37225.75m
Departure Angle for maximum range: 47.4515deg
```

One final feature, when using the `find-ff` command: adding the
`--save-to-config` option allows the newly calculated form factor data to be
added to the projectile and written out to a file, greatly simplifying the
process of creating a configuration file for a projectile.

```
$ meb find-ff -m 952.544 -c 406.4 -v 792.48 --drag-function KD6 \
        --shot 35.4617,33832.8 \
        --shot 45.2483,36210 \
        --save-to-config -

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Drag Function: KD6
 Density Function: US
Initial Conditions:
 Velocity: 792.480m/s
 Air Density Factor: 1.000000

Form Factor Results (departure angle, form factor):
 35.4617,0.996803 (9 iterations)
 45.2483,0.996695 (8 iterations)

[projectile]
mass = 952.544
caliber = 406.4
drag_function = KD6
density_function = US

[form_factor]
35.4617 = 0.9968025831684211
45.2483 = 0.9966946334692636

[initial_conditions]
altitude = 0.0001
mv = 792.48
air_density_factor = 1.0

[simulation]
timestep = 0.1
```

