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
boattail and a 6crh nose.

To test the drag functions the simplest option is to calculate the form factor
required to match each row in the table using the different drag functions, and
observe the variation. The following table shows the results of this.

Range | Departure Angle | Form Factor KD2 | Form Factor KD6 | Form Factor KD8
:----:|:---------------:|:---------------:|:---------------:|:----------------:
4572  |  2.3            |   0.791331      |   0.653026      |  0.709835       
9144  |  5.1            |   1.031029      |   0.846304      |  0.923617       
13716 |  8.5            |   1.076148      |   0.883124      |  0.965467       
18288 |  12.5           |   1.054688      |   0.867894      |  0.948696       
22860 |  17.5           |   1.059020      |   0.875591      |  0.955478       
27432 |  23.7           |   1.061095      |   0.881796      |  0.959820       
32004 |  32.4           |   1.081135      |   0.903397      |  0.980209        
34290 |  39.2           |   1.091025      |   0.914356      |  0.990151       

Plotting these will make it easier to interpret the data:

![Form Factors for KD2, KD6 and KD8 plotted against Departure
Angle](/examples/16in-45-mk1-ff.svg)

This suggests that none of the form factors are a good match for this
projectile - it appears to have a drag function that differs markedly from any
of the functions tested.
