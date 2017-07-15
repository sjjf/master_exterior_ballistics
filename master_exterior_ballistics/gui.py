#!/usr/bin/env python2

import argparse
import math
import Tkinter as tk
import ttk
import tkFileDialog as tkfd
import tkMessageBox as tkmb

from master_exterior_ballistics import projectile
from master_exterior_ballistics import commands
from master_exterior_ballistics import arguments
from master_exterior_ballistics import version

# The basic gui app has two panels, a projectile configuration panel on the
# left, and a command panel. The projectile config panel will have input
# widgets to take the various projectile options; the command panel will have a
# number of buttons at the top that selects the command to be run, and
# underneath the buttons will be a window that has the output data. Initially
# I'll stick with pretty much the same output format as the command line
# interface, but I'd like to add graphs where possible.

def add_entry(frame, label, default="0", side=tk.TOP):
    t = tk.LabelFrame(frame, text=label)
    t.pack(side=side)
    e = tk.Entry(t)
    e.insert(tk.INSERT, default)
    e.pack()
    return e

def popup_message(label, message):
    top = tk.Toplevel()
    t = tk.LabelFrame(top, text=label)
    t.pack()
    m = tk.Message(t, text=message)
    m.pack()


class App(object):
    def __init__(self, master, proj):

        self.panes = tk.PanedWindow(master, orient=tk.HORIZONTAL, showhandle=False)
        self.panes.pack(fill=tk.BOTH, expand=1)
        self.pframe = tk.LabelFrame(self.panes, text="Projectile Details", bd=0)
        self.panes.add(self.pframe)
        self.panes.paneconfigure(self.pframe, minsize=200, width=200)
        self._add_projectile_cntl(proj)

        self.cframe = ttk.Notebook(self.panes)
        self.panes.add(self.cframe)
        self._add_command_cntl()

    def _add_projectile_cntl(self, proj):
        self.pcntl = ProjectileCntl(self.pframe, proj)

    def _add_command_cntl(self):
        self.ccntl = CommandCntl(self.cframe, self.pcntl)

    def print_contents(self):
        self.update()
        self.output.insert(tk.END, "Mass: %.3f\n" % (self.mass))
        self.output.insert(tk.INSERT, "Caliber: %.2f\n" % (self.caliber))
        self.output.insert(tk.INSERT, "Muzzle Velocity: %.2f\n" % (self.mv))
        self.output.insert(tk.INSERT, "Form Factor Data:\n")
        for i in range(0, len(self.FF)):
            self.output.insert(tk.INSERT, " %.2f, %.6f\n" % (self.DA[i], self.FF[i]))


# our master is the top level left panel frame
class ProjectileCntl(object):
    def __init__(self, master, proj):
        self.root = master
        self.projectile = proj

        self._mass = add_entry(master, "Mass", default=proj.mass)
        self._caliber = add_entry(master, "Caliber", default=proj.caliber)
        self._mv = add_entry(master, "Muzzle Velocity", default=proj.mv)

        # this is a bit klunky, but then so is everything here . . .
        #
        # We have a label frame wrapping everything, two entry boxes for the
        # departure angle and form factor pairing, and a text box to list them.
        # At the bottom we have three buttons to clear the current form
        # factors, add the current values, or clear and add in one step.
        t = tk.LabelFrame(master, text="Form Factor")
        t.pack(side=tk.TOP)
        f = tk.Frame(t)
        f.pack(side=tk.TOP)
        l = tk.Label(f, text="DA")
        l.pack(side=tk.LEFT)
        self._da = tk.Entry(f)
        self._da.insert(tk.INSERT, "0")
        self._da.pack(side=tk.LEFT)
        f = tk.Frame(t)
        f.pack(side=tk.TOP)
        l = tk.Label(f, text="FF")
        l.pack(side=tk.LEFT)
        self._ff = tk.Entry(f)
        self._ff.insert(tk.INSERT, "0")
        self._ff.pack(side=tk.LEFT)
        f = tk.Frame(t)
        f.pack(side=tk.BOTTOM)
        b = tk.Button(f, text="Clear FF", command=self.clear_ff)
        b.pack()
        f = tk.Frame(t)
        f.pack(side=tk.BOTTOM)
        b = tk.Button(f, text="Add", command=self.add_ff)
        b.pack(side=tk.LEFT)
        b = tk.Button(f, text="Replace", command=self.replace_ff)
        b.pack(side=tk.LEFT)
        f = tk.Frame(t)
        f.pack(side=tk.BOTTOM)
        s = tk.Scrollbar(f)
        s.pack(side=tk.RIGHT, fill=tk.Y)
        self._ff_display = tk.Text(f, height=10, yscrollcommand=s.set)
        t = self.projectile.format_form_factors()
        self._ff_display.pack(fill=tk.Y)
        s.config(command=self._ff_display.yview)

        # more klunkiness . . .
        #
        # We have a label frame wrapping everything, then a spin box listing the known drag function options, with the option of setting your own filename (by editing the value directly).
        t = tk.LabelFrame(master, text="Drag Function")
        t.pack(side=tk.TOP)

        self.std_drag_functions = projectile.Projectile.get_drag_functions()
        values = self.std_drag_functions
        values.append("Specify File")
        self._drag_function = tk.Spinbox(t, values=values)
        self._drag_function.delete(tk.INSERT, tk.END)
        if proj.drag_function_file:
            self._drag_function.insert(tk.INSERT, proj.drag_function_file)
        else:
            self._drag_function.insert(tk.INSERT, proj.drag_function)
        self._drag_function.pack()
        b = tk.Button(t, text="Update", command=self.replace_drag_function)
        b.pack(side=tk.BOTTOM)

        self.show_ff()

    def clear_ff(self):
        self.projectile.clear_form_factors()
        self.show_ff()

    def add_ff(self):
        da = float(self._da.get())
        ff = float(self._ff.get())
        self.projectile.update_form_factors(da, ff)
        self.show_ff()

    def replace_ff(self):
        self.clear_ff()
        self.add_ff()
        self.show_ff()

    def show_ff(self):
        text = self.projectile.format_form_factors()
        self._ff_display.delete(1.0, tk.END)
        self._ff_display.insert(tk.INSERT, text)

    def replace_drag_function(self):
        df = self._drag_function.get()
        self.projectile.set_drag_function(df)

    def update(self):
        try:
            self.mass = float(self._mass.get())
            self.caliber = float(self._caliber.get())
            self.mv = float(self._mv.get())
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))

    def get_projectile(self):
        return self.projectile


def make_output(master):
    t = tk.LabelFrame(master, text="Output")
    t.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)
    s = tk.Scrollbar(t)
    s.pack(side=tk.RIGHT, fill=tk.Y)
    output = tk.Text(t, yscrollcommand=s.set)
    output.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)
    s.config(command=output.yview)
    return output

# this needs to be changed to a two paned vertical display
class CommandCntl(object):
    def __init__(self, master, pcntl):
        self.root = master
        self.pcntl = pcntl

        self._singlerun = SingleRunGUI(master, pcntl)
        master.add(self._singlerun.setup_display(), text="Single Run")

    def single(self):
        pass

# As with the CLIMixin, this is implemented here as a mixin class. This code
# takes control of a frame and adds the necessary widgets and the like, runs
# the analysis and prints the output to a text box.
#
# The interface presented is a setup function that creates all the necessary
# widgets, a process function that runs the analysis, and an output function
# that displays the results. We're assuming that within a single session a
# number of runs will be done, so the output will be treated as a single text
# document rather than restarted from clean at every run. This obviously
# implies a mechanism for saving the actual output to a file or similar, and
# resetting the output as required.
#
# On top of that, we need to be able to accept at least a few events from the
# rest of the app, the most important of which is when the user has updated the
# definition of the current projectile.
class GUIMixin(object):
    def __init__(self, master, pcntl):
        self.master = master
        self.pcntl = pcntl
        self.undo = []
        super(GUIMixin, self).__init__()

    def setup_display(self):
        raise NotImplemented

    def process_gui(self):
        raise NotImplemented

    def update_output(self):
        raise NotImplemented

    def save_output(self):
        raise NotImplemented

    def reset_output(self):
        raise NotImplemented

    def reset_projectile(self):
        raise NotImplemented

class SingleRunGUI(GUIMixin, commands.SingleRun):

    def __init__(self, master, pcntl):
        self.frame = None
        super(SingleRunGUI, self).__init__(master, pcntl)

    # we need to take the departure angle, and a checkbox to determine whether
    # to print out the trajectory
    def setup_display(self):
        # we want a frame at the top with the two inputs, and a "run" button
        # which gets connected to the process_gui() method

        # we're resetting the whole display, so we need to clear the
        # config_printed flag
        self.config_printed = False

        if self.frame:
            # start by tossing all the existing widgets (I think?)
            for child in self.frame.pack_slaves():
                child.pack_forget()
        else:
            self.frame = tk.Frame(self.master)
            self.frame.pack(side=tk.TOP)
        t = tk.Frame(self.frame)
        t.pack(side=tk.TOP)
        daf = tk.LabelFrame(t, text="Departure Angle")
        daf.pack(side=tk.LEFT)
        self._departure_angle = tk.Entry(daf)
        self._departure_angle.insert(tk.INSERT, "0")
        self._departure_angle.pack()
        self._print_trajectory = tk.IntVar()
        c = tk.Checkbutton(t, text="Print Trajectory", variable=self._print_trajectory)
        c.pack(side=tk.LEFT)
        t = tk.Frame(self.frame)
        t.pack(side=tk.TOP)
        b = tk.Button(t, text="Run Simulation", command=self.process_gui)
        b.pack(side=tk.LEFT)
        b = tk.Button(t, text="Clear Output", command=self.reset_output)
        b.pack(side=tk.RIGHT)
        self.output = make_output(self.frame)
        return self.frame

    def process_gui(self):
        self.projectile = self.pcntl.get_projectile()
        try:
            self.departure_angle = float(self._departure_angle.get())
            self.departure_angle = math.radians(self.departure_angle)
            self.projectile.set_departure_angle(self.departure_angle)
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))
            return
        if self._print_trajectory:
            self.projectile.show_trajectory = True
        self.run_analysis()
        text = ""
        if not self.config_printed:
            text = self.format_configuration()
            self.config_printed = True
        text += "\n"
        text += self.format_conditions()
        text += self.format_output()
        self.output.insert(tk.INSERT, text)

    def reset_output(self):
        self.undo.append(self.output.get(1.0, tk.END))
        self.output.delete(1.0, tk.END)


def parse_args():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    arguments.set_common_defaults(parser)
    arguments.add_common_args(parser)
    return parser.parse_args()


def main():
    root = tk.Tk()

    args = parse_args()

    if 'config' in args:
        p = projectile.Projectile(args)
    else:
        empty_args = projectile.Projectile.make_args()
        p = projectile.Projectile(empty_args)

    app = App(root, p)

    root.mainloop()

if __name__ == '__main__':
    main()

