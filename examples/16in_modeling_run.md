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
would be the KD8 drag function, though the KD1 drag function may also be
appropriate depending on the age of the design in 1935. We'll start with the
KD8 function and see what results we get.

The form factor can only be determined by comparing test shots with the
historical data, but the best option when starting is to specify the form
factor as 1.0 and see how it goes.

# A single shot

To model a single shot the program should be run with the command `single`:

```
$ ./master_exterior_ballistics.py single -h 
usage: master_exterior_ballistics.py single [-h] -l DEPARTURE_ANGLE [-t] -f
                                            FORM_FACTOR -v MV -m MASS -c
                                            CALIBER [-a ALTITUDE]
                                            [-I TIMESTEP]
                                            [--air-density-factor AIR_DENSITY_FACTOR]
                                            [--density-function {US,UK,ICAO}]
                                            [--drag-function DRAG_FUNCTION]
                                            [--drag-function-file
DRAG_FUNCTION_FILE]

optional arguments:
  -h, --help            show this help message and exit
  -l DEPARTURE_ANGLE, --departure-angle DEPARTURE_ANGLE
                        Departure Angle
  -t, --print-trajectory
                        Print projectile trajectory
  -f FORM_FACTOR, --form-factor FORM_FACTOR
                        Projectile form factor
  -v MV, --mv MV        Initial velocity
  -m MASS, --mass MASS  Projectile mass
  -c CALIBER, --caliber CALIBER
                        Projectile caliber
  -a ALTITUDE, --altitude ALTITUDE
                        Initial altitude (default 0)
  -I TIMESTEP, --timestep TIMESTEP
                        Simulation timestep
  --air-density-factor AIR_DENSITY_FACTOR
                        Air density adjustment factor (default 1.0)
  --density-function {US,UK,ICAO}
                        Density Function: US Pre-1945 std, British std,ICAO
                        std (default US)
  --drag-function DRAG_FUNCTION
                        Drag function to use (default KD8)
  --drag-function-file DRAG_FUNCTION_FILE
                        File to read drag function data from
```

Putting the values we determined above onto the command line gives this:

```
$ ./master_exterior_ballistics.py single -m 952.544 -c 406.4 -v 792.48 \
        -l 45.2483 -f 1.0 --drag-function KD8
```

This produces the following output:

```
Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0000
 Drag function: KD8
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 45.2483deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 96.58s
Range: 37575.33m
Impact Angle: -56.1381deg
Impact Velocity: 477.11m/s
```

This resulted in a shot that went significantly further than the desired
range, indicating that the modelled drag was significantly too low. This can
be adjusted by increasing the form factor, for example to 1.1:

```
$ ./master_exterior_ballistics.py single -m 952.544 -c 406.4 -v 792.48 \
    -l 45.2483 -f 1.1 --drag-function KD8

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.1000
 Drag function: KD8
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 45.2483deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 95.10s
Range: 35829.68m
Impact Angle: -57.1354deg
Impact Velocity: 458.43m/s
```

This time the range is somewhat short of the target, indicating that the new
form factor is too high - the correct form factor will be somewhere in
between.

# Finding the Form Factor

We could continue with the above approach to narrow down the form factor,
narrowing it down to whatever precision we desired. However, the program
supports doing this automatically, using the `find-ff` command:

```
usage: master_exterior_ballistics.py find-ff [-h] -l DEPARTURE_ANGLE
                                             [-f FORM_FACTOR] --target-range
                                             TARGET_RANGE
                                             [--tolerance TOLERANCE] -v MV -m
                                             MASS -c CALIBER [-a ALTITUDE]
                                             [-I TIMESTEP]
                                             [--air-density-factor AIR_DENSITY_FACTOR]
                                             [--density-function {US,UK,ICAO}]
                                             [--drag-function DRAG_FUNCTION]
                                             [--drag-function-file DRAG_FUNCTION_FILE]

optional arguments:
  -h, --help            show this help message and exit
  -l DEPARTURE_ANGLE, --departure-angle DEPARTURE_ANGLE
                        Departure Angle
  -f FORM_FACTOR, --form-factor FORM_FACTOR
                        Projectile form factor
  --target-range TARGET_RANGE
                        Target range
  --tolerance TOLERANCE
                        Convergence tolerance
  -v MV, --mv MV        Initial velocity
  -m MASS, --mass MASS  Projectile mass
  -c CALIBER, --caliber CALIBER
                        Projectile caliber
  -a ALTITUDE, --altitude ALTITUDE
                        Initial altitude (default 0)
  -I TIMESTEP, --timestep TIMESTEP
                        Simulation timestep
  --air-density-factor AIR_DENSITY_FACTOR
                        Air density adjustment factor (default 1.0)
  --density-function {US,UK,ICAO}
                        Density Function: US Pre-1945 std, British std,ICAO
                        std (default US)
  --drag-function DRAG_FUNCTION
                        Drag function to use (default KD8)
  --drag-function-file DRAG_FUNCTION_FILE
                        File to read drag function data from
```

Given the other elements of the projectile configuration (the mass, caliber and
drag function), this command will find the form factor that is needed to match a
specified shot (a target range and a departure angle).

Using the previously specified shot, with a target range of 36210m at a
departure angle of 45.2483 degrees:

```
$ ./master_exterior_ballistics.py find-ff -m 952.544 -c 406.4 -v 792.48 \
         --drag-function KD8 --target-range 36210 -l 45.2483

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0000
 Drag function: KD8

Form Factor: 1.077591

Form Factor found for projectile at the following conditions:
Target Range 36210.00m matched at:
 Range: 36210.06m
 Departure Angle: 45.2483deg

```

The program has found the required form factor to match the shot - 1.077591. As
expected this is between 1.0 and 1.1, the bracketing values we found manually.

To verify that this is correct we can re-run the single shot mode that we tried
before, using the new value for the form factor:

```
$ ./master_exterior_ballistics.py single -m 952.544 -c 406.4 -v 792.48
        -l 45.2483 -f 1.077591 --drag-function KD8

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0776
 Drag function: KD8
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 45.2483deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 95.43s
Range: 36210.06m
Impact Angle: -56.9131deg
Impact Velocity: 462.53m/s
```

As expected, the calculated range is 36210m; the impact angle is 56.9 degrees,
compared with 55.9 degrees in the original data; the time of flight is 95.4s
compared with 94.6; and the impact velocity is 462.5m/s compared with 475.2m/s.
These variations are on the order of one or two percent, which is reasonable
given that the original terminal data was mostly derived rather than direct
measurements.

To verify that the calculated form factor is a good match we can use other data
from the table. The first row, converted to metric, has the following
information:

```
33832.8 35.4617 47.8 77.7 448.0
```

Modeling this shot gives us:

```
$ ./master_exterior_ballistics.py single -m 952.544 -c 406.4 -v 792.48 \
        -l 35.4617 -f 1.077591 --drag-function KD8

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0776
 Drag function: KD8
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 35.4617deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 78.47s
Range: 33865.42m
Impact Angle: -48.8472deg
Impact Velocity: 431.21m/s
```

Again these numbers are close, though not a perfect match. We can go back and
run the find-ff command again with this shot as the target data - this can give
us an idea for how closely the chosen drag function matches the original data:

```
$ ./master_exterior_ballistics.py find-ff -m 952.544 -c 406.4 -v 792.48 \
		 --drag-function KD8 --target-range 33832.8 -l 35.4617

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0000
 Drag function: KD8

Form Factor: 1.079720

Form Factor found for projectile at the following conditions:
Target Range 33832.80m matched at:
 Range: 33832.60m
 Departure Angle: 35.4617deg
```

The resulting form factor differs by 0.002, or about 2 parts in 1000, suggesting
the match is reasonably solid. To finally verify that, running the previous
single shot with the new form factor will give us an idea of the variation in
results between the two values:

```
$ ./master_exterior_ballistics.py single -m 952.544 -c 406.4 -v 792.48 \
        -l 45.2483 -f 1.079720 --drag-function KD8

Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0797
 Drag function: KD8
Initial Conditions:
 Velocity: 792.480m/s
 Departure Angle: 45.2483deg
 Air Density Factor: 1.000000

Final conditions:
Time of flight: 95.40s
Range: 36173.66m
Impact Angle: -56.9342deg
Impact Velocity: 462.14m/s
```
The original data for this shot was:

```
36,210 45.2483 55.9 94.6 475.2 
```

The data calculated using the first form factor estimate was:

```
36,210 45.2483 56.9 95.4 462.5
```

and the data calculated using the second form factor estimate was:

```
36,174 45.2483 56.9 95.4 462.1
```

Between the two form factors the variation is minimal, though the small
variations in terminal conditions between the two modeling runs and the original
data may indicate some inconsistencies between the chosen drag function and the
drag function used to derive the historical data. However, the variations are
all on the order of 1%, which suggests that this is a decent match for the
original range table.

In theory the same process could be done to match all rows in the original
table, and the resulting form factors could be averaged to get the best possible
match, but the trivial differences between the two values tested here suggest
that would gain us little additional accuracy. In this case we'll just average
the two values we now have to get 1.0786555.

# Recreating the Range Table

Now that we have a reasonably good form factor we can attempt to recreate the
original range table. The data we have starts at a range of 37000 yards and
continues to 39600 yards, and increments by 100 yards - converting this to
metric gives a range from 33832.8m to 36210m in 91.44m increments. The range
table can be replicated using the `range-table` command:

```
$ ./master_exterior_ballistics.py range-table --help

usage: master_exterior_ballistics.py range-table [-h] -f FORM_FACTOR
                                                 [--increment INCREMENT]
                                                 [--start START] [--end END]
                                                 -v MV -m MASS -c CALIBER
                                                 [-a ALTITUDE] [-I TIMESTEP]
                                                 [--air-density-factor AIR_DENSITY_FACTOR]
                                                 [--density-function {US,UK,ICAO}]
                                                 [--drag-function DRAG_FUNCTION]
                                                 [--drag-function-file DRAG_FUNCTION_FILE]

optional arguments:
  -h, --help            show this help message and exit
  -f FORM_FACTOR, --form-factor FORM_FACTOR
                        Projectile form factor
  --increment INCREMENT
                        Range steps for range table
  --start START         Starting range
  --end END             End range
  -v MV, --mv MV        Initial velocity
  -m MASS, --mass MASS  Projectile mass
  -c CALIBER, --caliber CALIBER
                        Projectile caliber
  -a ALTITUDE, --altitude ALTITUDE
                        Initial altitude (default 0)
  -I TIMESTEP, --timestep TIMESTEP
                        Simulation timestep
  --air-density-factor AIR_DENSITY_FACTOR
                        Air density adjustment factor (default 1.0)
  --density-function {US,UK,ICAO}
                        Density Function: US Pre-1945 std, British std,ICAO
                        std (default US)
  --drag-function DRAG_FUNCTION
                        Drag function to use (default KD8)
  --drag-function-file DRAG_FUNCTION_FILE
                        File to read drag function data from
```

The projectile details stay the same, and we simply specify the start, end and
increment:

```
$ ./master_exterior_ballistics.py range-table -m 952.544 -c 406.4 -v 792.48 \
        -f 1.0786555 --drag-function KD8 --start 33832.8 --end 36210 \
         --increment 91.44

Range Table
Projectile Configuration:
 Mass: 952.544kg
 Caliber: 406.400mm
 Form Factor: 1.0787
 Drag function: KD8
Initial velocity: 792.4800m/s
Air Density Factor: 1.0000
Range increments: 91.4m

 Range Departure Angle of Time of Striking
        Angle      Fall   Flight    Vel.
-------------------------------------------
 33833  35.4194 -48.8192  78.38   430.90
 33924  35.6588 -49.0430  78.82   431.58
 34016  35.9039 -49.2706  79.27   432.29
 34107  36.1519 -49.4990  79.72   433.01
 34199  36.4057 -49.7310  80.18   433.75
 34290  36.6624 -49.9639  80.64   434.51
 34381  36.9248 -50.2001  81.11   435.30
 34473  37.1959 -50.4423  81.60   436.11
 34564  37.4699 -50.6850  82.09   436.94
 34656  37.7525 -50.9334  82.60   437.81
 34747  38.0409 -51.1849  83.11   438.70
 34838  38.3350 -51.4393  83.63   439.61
 34930  38.6407 -51.7015  84.18   440.57
 35022  38.9580 -51.9712  84.74   441.57
 35113  39.2810 -52.2435  85.30   442.59
 35204  39.6184 -52.5253  85.89   443.68
 35296  39.9702 -52.8166  86.51   444.82
 35388  40.3365 -53.1170  87.15   446.01
 35478  40.7172 -53.4264  87.80   447.26
 35570  41.1238 -53.7538  88.50   448.60
 35662  41.5535 -54.0964  89.24   450.03
 35753  42.0149 -54.4606  90.03   451.56
 35845  42.5167 -54.8527  90.88   453.24
 35936  43.0704 -55.2805  91.81   455.10
 36028  43.7049 -55.7650  92.87   457.23
 36119  44.4605 -56.3354  94.12   459.75
 36210  45.4929 -57.1049  95.81   463.13
```

Converting the output to imperial units for a direct comparison is an exercise
left to the reader, but a quick eyeballing of the easily comparable numbers
suggest that the departure angles found for each range are close but not perfect
matches, and the terminal conditions are within a percent of the original data.

Having verified that we have a workable model we can now generate a range table
covering any portion of the gun range that we're interested in, or experiment
with any of the other variables that can be introduced (variations in
atmospheric density, variations in initial velocity, variations in projectile
mass, and so on).

# Conclusion

This document outlines one use case (possibly the most important) for the master
exterior ballistics program - that of recreating a historical range table. It
demonstrates the core functionality and some of the limitations of the program,
but does not attempt to provide complete coverage. Other information can be
found in the README file, and in the help information.
