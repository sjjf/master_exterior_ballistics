# UK 16in Mark1B

In this example we have a coarse range table (specifying details at 5000yd
increments) and plenty of detail about the projectile, its history, and the guns
that fired it, sourced from the [NavWeaps](http://www.navweaps.com) site. The
specific data is
[here](http://navweaps.com/Weapons/WNBR_16-45_mk1.php)

## Prerequisites

It is strongly recommended that the user has worked through the [previous
example](/examples/16in_modeling_run.md) - the current example will not cover
the usage of the program in detail, merely the inputs and outputs.

## The source data

The range data for this projectile can be found
[here](http://navweaps.com/Weapons/WNBR_16-45_mk1.php#Range). It provides
departure angles, ranges and terminal conditions at 5000 yard intervals.

## The goal

We'd like to create a more detailed range table using this data set - something
more along the lines of the 100yd increments used in historical range tables.

## The method

First we need to develop some understanding of the projectile and how its
performance matches some of the common drag functions, and then we need to
select an appropriate drag function. Finally, we need to determine appropriate
form factors to use across the full range of the table, and use those to produce
the full table.

# Drag Functions

We know a reasonable amount about this projectile so we should be able to use
that knowledge to select an appropriate drag function (in theory, at least).

The projectile has a conical nose that is 6crh, and a flat base with no
boattail. Though it's not a perfect match the KD2 drag function looks like the
closest, with the next closest option being the KD8 drag function - with no
boattail, but with a shorter 5/10crh nose, or the KD6 drag function, with no
boattail and a 6crh nose. We also know that it's a British design, so using the
UK atmospheric model makes sense.

To test the drag functions the simplest option is to calculate the form factor
required to match each row in the table using the different drag functions
(using the program's find-ff command), and observe the variation. The
following table shows the results of this.

| Range | Departure Angle | Form Factor KD2 | Form Factor KD6 | Form Factor KD8  |
|:-----:|:---------------:|:---------------:|:---------------:|:----------------:|
| 4572  |     2.3         |    0.791396     |    0.65308      |    0.709893      |
| 9144  |     5.1         |    1.031422     |    0.84663      |    0.923971      |
| 13716 |     8.5         |    1.077233     |    0.884012     |    0.966435      |
| 18288 |     12.5        |    1.056845     |    0.869662     |    0.950629      |
| 22860 |     17.5        |    1.06292      |    0.87881      |    0.95898       |
| 27432 |     23.7        |    1.067552     |    0.887086     |    0.965627      |
| 32004 |     32.4        |    1.091568     |    0.911992     |    0.989613      |
| 34290 |     39.2        |    1.104528     |    0.925493     |    1.002287      |

Plotting these will make it easier to interpret the data:

![Form Factors for KD2, KD6 and KD8 plotted against Departure
Angle](/examples/16in-45-mk1-ff.png)

This suggests that none of the drag functions are a good match for this
projectile - it appears to have a drag function that differs markedly from any
of the functions tested. The shape of the form factor plot for each is almost
identical, so it probably won't make much difference which we use.

The shape of the plot also suggests that there may be two different modeling
regimes encapsulated in this range data: a nearly straight line above 15
degrees, and a more complex curve below 15 degrees, with some kind of
smoothing between the two cases. This may be a result of the original range
table being calculated using two different methods - historically, it was
common for the low-angle portion of the range table to be calculated using a
simpler approximation to numerical integration which was sufficiently accurate
for flat fire (typically something like the Siacci method), with a more
complete numerical integration technique used for the remainder, and some form
of graphical smoothing applied to meld the two.  This doesn't affect the
validity of the form factors determined by this method, but it does mean that
attempting to extrapolate outside the source data on the low end will be very
questionable - we should start our range table at 5000 yards, rather than try
and extrapolate further.

It's also worth noting that the higher portion of the range table is quite
flat, but with a significant slope - this indicates that even in the best case
none of the drag functions match what might be called the "native" drag
function of the projectile. The slope of the line for a perfectly matched drag
function would be zero (i.e. the form factor would be constant across the
whole range).

For our purposes we will pick the KD8 drag function, but any of these would
provide a solid match.

# Calculating the Range Table

We now have a drag function that we've determined should provide a reasonable
match, and we've got a set of departure angle to form factor pairs which we
can use to model the range table. We're using the KD8 drag function, which
gives us the following form factor data:

| Departure Angle | Form Factor |
|:---------------:|:-----------:|
|     2.3         |   0.709893  |
|     5.1         |   0.923971  |
|     8.5         |   0.966435  |
|     12.5        |   0.950629  |
|     17.5        |   0.95898   |
|     23.7        |   0.965627  |
|     32.4        |   0.989613  |
|     39.2        |   1.002287  |

and we're using the UK atmospheric model.

Having decide on the drag function and form factors, we'll create a config file
for this projectile. In a case like this where we've collected a bunch of
information and we need to pull it all together into a config file we can either
manually edit the file, or we can use the `make-config` command, which takes all
the normal projectile configuration arguments and then writes them to a config
file.

```
$ meb make-config -h

usage: meb make-config [-h] --filename FILENAME [-m MASS] [-c CALIBER]
                       [--density-function {US,UK,ICAO}]
                       [--drag-function {1938,1940,KD1,KD2,KD6,KD7,KD8} | --drag-function-file DRAG_FUNCTION_FILE]
                       [-f FORM_FACTOR | -F FF,A] [-v MV] [-a ALTITUDE]
                       [--air-density-factor AIR_DENSITY_FACTOR]
                       [--config CONFIG] [--write-config CONFIG] [-I TIMESTEP]
                       [--tolerance TOLERANCE]

Make a configuration file

optional arguments:
  -h, --help            show this help message and exit

config file details:
  --filename FILENAME   Config file name

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

We can build a configuration for our current projectile thusly:

```
$ meb make-config -m 928.927 -c 406.4 -v 769.62 \
        --drag-function KD8 --density-function UK \
        -F 2.3,0.709893   \
        -F 5.1,0.923971   \
        -F 8.5,0.966435   \
        -F 12.5,0.950629  \
        -F 17.5,0.95898   \
        -F 23.7,0.965627  \
        -F 32.4,0.989613  \
        -F 39.2,1.002287  \
        --filename -

[projectile]
mass = 928.927
caliber = 406.4
drag_function = KD8
density_function = UK

[form_factor]
2.3000000000000003 = 0.709893
5.1 = 0.923971
8.5 = 0.966435
12.5 = 0.950629
17.5 = 0.95898
23.7 = 0.965627
32.4 = 0.989613
39.2 = 1.002287

[initial_conditions]
altitude = 0.0001
mv = 769.62
air_density_factor = 1.0

[simulation]
timestep = 0.1
```

This can now be used to specify the range table calculation. Note that we start
at the bottom of the range we have source data for (4572m), and we end close to
the top of the range we have source data for (35000m). We use a 500yd (457.2m)
increment for this example.

```
$ meb --config test.conf \
        --start 4572 --end 35000 \
        --increment 457.2

Range Table
Projectile Configuration:
 Mass: 928.927kg
 Caliber: 406.400mm
 Form Factor data:
  2.3000deg: 0.709893
  5.1000deg: 0.923971
  8.5000deg: 0.966435
  12.5000deg: 0.950629
  17.5000deg: 0.958980
  23.7000deg: 0.965627
  32.4000deg: 0.989613
  39.2000deg: 1.002287
 Drag Function: KD8
 Density Function: UK
Est. max range: 35167.5m at 46.2920deg
Initial velocity: 769.6200m/s
Air Density Factor: 1.0000
Range increments: 457.2m

 Range Departure Angle of Time of Striking
        Angle      Fall   Flight    Vel.
-------------------------------------------
  4572   2.3005  -2.4373   6.21   705.65
  5029   2.5507  -2.7232   6.87   697.56
  5486   2.8059  -3.0198   7.54   689.15
  5943   3.0666  -3.3287   8.22   680.40
  6401   3.3338  -3.6512   8.92   671.28
  .
  .
  .
 30175  28.4710 -40.3711  64.27   423.19
 30632  29.3788 -41.4554  65.99   424.01
 31090  30.3317 -42.5613  67.79   425.11
 31547  31.3354 -43.6912  69.65   426.50
 32004  32.4011 -44.8534  71.61   428.22
 32461  33.5063 -46.0081  73.63   430.42
 32918  34.6975 -47.2103  75.78   433.00
 33376  36.0042 -48.4814  78.11   436.05
 33833  37.4731 -49.8552  80.69   439.70
 34290  39.1985 -51.4016  83.66   444.24
 34748  41.4371 -53.3119  87.43   450.43
```

Plotting the calculated data against the source data to compare the accuracy
gives the following for departure and impact angles:

![Range vs Departure and Impact Angles, source vs calculated
data](/examples/16in-45-mk1-rt-angles.png)

and for impact velocity:

![Range vs Impact Velocity, source vs calculated
data](/examples/16in-45-mk1-rt-iv.png)

The calculated data matches the source data very well across the full range,
with the biggest discrepancies being in the impact velocity. The impact
velocity is the value that was hardest to measure historically, and hence the
one which was most reliant on numerical modeling - in this case our value is
as likely to be accurate as the historical value.

# Conclusion

In this example we have demonstrated that given reasonable source data we can
recreate a nearly complete range table with a good degree of accuracy. We've
been able to determine that the projectile's "native" drag function is
significantly different to the standard drag functions we tested - the conical
nose and lack of boattail makes its performance noticeably different to any of
the standard projectiles. We've also been able to find some information about
the source data - the probable use of a different calculation method for flat
fire portions of the range table. 
