#!/usr/bin/env python2

import argparse
import copy
import math
from os import path
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
    t.pack(side=side, anchor=tk.W)
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


title = "Master Exterior Ballistics"
title_with = title + " - %s"

master_window = None
def set_title(name=None, filename=None):
    if name:
        master_window.title(title_with % (name))
    elif filename:
        master_window.title(title_with % (filename))
    else:
        master_window.title(title)


# Back to design thinking . . .
#
# We have an important question here, moving on from simply building an
# approximation of the command line interface: what kind of workflow do we
# design the interface around?
#
# I think there are two main use cases: analysing and developing a model for a
# projectile, and making use of an existing model to answer questions about
# particular scenarios (i.e. making test "shots", determining the terminal
# conditions at a particular range, and things like that). Both these use cases
# can be supported pretty easily, but there are wrinkles in the analysis use
# case that need thought.
#
# The current interface design treats the projectile as a separate entity which
# the analysis/modeling tools make use of directly. In the modeling tools this
# isn't a problem, but the analysis/development tools really need to operate on
# a copy. We should probably keep a history of the changed states (so we have
# undo support), and we also need to be able to push an externally updated copy
# back into the projectile side of the interface (to make use of the updated
# form factors).
#
# Testing suggests that simly using copy.deepcopy() will work, so I'll go with
# that for now.
class App(object):
    def __init__(self, master, proj):

        self.last_savefile = None
        global master_window
        master_window = master

        self.menu = tk.Frame(master)
        self.menu.pack(side=tk.TOP, anchor=tk.W)
        self._file = tk.Menubutton(self.menu, text="File")
        self._file.pack(side=tk.LEFT)
        mb = tk.Menu(self._file)
        self._file['menu'] = mb
        mb.add_command(label="New", command=self.new_projectile)
        mb.add_command(label="Open", command=self.load_projectile)
        mb.add_command(label="Save", command=self.save_projectile)
        mb.add_command(label="Save As", command=self.save_projectile_as)
        mb.add_separator()
        mb.add_command(label="Quit", command=self.quit)
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

    def save_projectile(self):
        proj = self.pcntl.get_projectile()
        filename = proj.filename
        if self.last_savefile:
            filename = self.last_savefile
        filename = tkfd.asksaveasfilename(initialfile=filename,
                                          filetypes=[
                                              ("Projecile Config", "*.conf"),
                                              ("All Files", "*")
                                          ])
        if not filename:
            return
        self.last_savefile = filename
        proj.to_config(self.last_savefile)
        set_title(proj.name, filename)

    def save_projectile_as(self):
        proj = self.pcntl.get_projectile()
        filename = tkfd.asksaveasfilename(filetypes=[
                                            ("Projectile Config", "*.conf"),
                                            ("All Files", "*")
                                          ])
        if not filename:
            return
        self.last_savefile = filename
        proj.to_config(self.last_savefile)
        set_title(proj.name, filename)

    def load_projectile(self):
        filename = ""
        if self.last_savefile:
            filename = self.last_savefile
        filename = tkfd.askopenfilename(initialfile=filename,
                                        filetypes=[
                                            ("Projectile Config", "*.conf"),
                                            ("All Files", "*")
                                        ])
        if not filename:
            return
        try:
            proj = projectile.Projectile.from_file(filename)
            self.pcntl.set_projectile(proj)
            self.last_savefile = filename
            set_title(proj.name, filename)
        except projectile.MissingAttribute as e:
            tkmb.showerror("Invalid Config File",
                           message="Could not load file %s: %s" % (filename, e))

    def new_projectile(self):
        proj = projectile.Projectile.from_defaults()
        self.pcntl.set_projectile(proj)
        set_title(proj.name)

    def quit(self):
        global master_window
        master_window.destroy()


# this is broken out so that it can be reused in multiple contexts
class FFDisplay(object):
    def __init__(self, master):
        self.ffs = []
        self.ff_ids = {}

        # this is a bit klunky, but then so is everything here . . .
        #
        # We have a label frame wrapping everything, a treeview showing the
        # current form factors, then a pair of entry boxes to allow you to
        # specify new departure angle/form factor pairs and add them to the
        # list, and finally a couple of buttons that let you clear the current
        # form factors, or delete the entries in the list that are selected.
        t = tk.LabelFrame(master, text="Form Factor")
        t.pack(side=tk.TOP, anchor=tk.W)
        f = tk.Frame(t)
        f.pack(side=tk.TOP)
        s = tk.Scrollbar(f)
        s.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(f,
                columns=("FF"),
                height=10,
                yscrollcommand=s.set)
        self.tree.column("#0", width=80)
        self.tree.heading("#0", text="DA")
        self.tree.column("FF", width=80)
        self.tree.heading("FF", text="FF")
        self.tree.pack(side=tk.TOP, fill=tk.Y)
        s.config(command=self.tree.yview)
        # this is convoluted, but:
        #
        # we have a frame with three sub-frames, firstly the two labels, then
        # the entry boxes, then finally the Add button
        f = tk.Frame(t)
        f.pack(side=tk.TOP)
        labels = tk.Frame(f, width=20)
        labels.pack(side=tk.LEFT, anchor=tk.W)
        dal = tk.Label(labels, text="DA")
        dal.pack(side=tk.TOP)
        ffl = tk.Label(labels, text="FF")
        ffl.pack(side=tk.BOTTOM)
        entries = tk.Frame(f)
        entries.pack(side=tk.LEFT)
        self._da = tk.Entry(entries, width=10)
        self._da.insert(tk.INSERT, "0")
        self._da.pack(side=tk.TOP, anchor=tk.W)
        self._ff = tk.Entry(entries, width=10)
        self._ff.insert(tk.INSERT, "0")
        self._ff.pack(side=tk.TOP, anchor=tk.W)
        add = tk.Frame(f)
        add.pack(side=tk.RIGHT, anchor=tk.E)
        b = tk.Button(add, text="Add", command=self.add_ff)
        b.pack(side=tk.RIGHT, anchor=tk.E)

        f = tk.Frame(t)
        f.pack(side=tk.BOTTOM, anchor=tk.W)
        b = tk.Button(f, text="Clear All", command=self.clear_ffs)
        b.pack(side=tk.LEFT)
        b = tk.Button(f, text="Delete", command=self.delete_ff)
        b.pack(side=tk.RIGHT, anchor=tk.E)

    def set_ffs(self, ffs):
        self.ffs = ffs
        self.show_ffs()

    def get_ffs(self):
        return self.ffs

    def clear_ffs(self):
        self.ffs = []
        self.show_ffs()

    def show_ffs(self):
        for iid in self.ff_ids.keys():
            self.tree.delete(iid)
        self.ff_ids = {}
        for (da, ff) in self.ffs:
            t = self.tree.insert("", "end",
                    text="%.4f" % (math.degrees(da)),
                    values=("%.6f" %(ff)))
            self.ff_ids[t] = da

    def add_ff(self):
        da = float(self._da.get())
        self._da.delete(0, tk.END)
        self._da.insert(tk.INSERT, "0")
        ff = float(self._ff.get())
        self._ff.delete(0, tk.END)
        self._ff.insert(tk.INSERT, "0")
        self.ffs.append((math.radians(da), ff))
        self.show_ffs()

    def delete_ff(self):
        iid = self.tree.focus()
        if not iid:
            return
        tda = self.ff_ids[iid]
        t = []
        found = False
        for (da, ff) in self.ffs:
            # this is safe because tda and da come from the same source
            #
            # note that we only want to delete /one/ of these - the user may
            # have accidentally added multiple copies, and only wants to delete
            # one
            if tda == da and not found:
                found = True
                continue
            t.append((da, ff))
        self.ffs = t
        self.show_ffs()


# our master is the top level left panel frame
class ProjectileCntl(object):
    def __init__(self, master, proj):
        self.root = master
        self.projectile = proj
        self.extra_drag_functions = {}
        self.undo = []

        self._name = add_entry(master, "Name", default=proj.name)
        self._mass = add_entry(master, "Mass", default=proj.mass)
        self._caliber = add_entry(master, "Caliber", default=proj.caliber)
        self._mv = add_entry(master, "Muzzle Velocity", default=proj.mv)
        # more klunkiness . . .
        #
        # We have a label frame wrapping everything, then a spin box listing
        # the known drag function options, with the option of setting your own
        # filename (by editing the value directly).
        t = tk.LabelFrame(master, text="Drag Function")
        t.pack(side=tk.TOP, anchor=tk.W)

        # The drag function handling is a pain in the arse.
        #
        # The problem is that we want to have a single control that does two
        # things: select one of the existing drag functions, /and/ allow the
        # user to specify a file.
        #
        # The way we do this is by having a "magic" value in the combobox that
        # triggers us to pop up a filename dialogue. Once the user has selected
        # a file we need to add it to the dropdown box too, and retain the
        # magic value to allow the addition of new files.
        #
        # So that we're not putting stupidly long values in the combobox, we'll
        # put just the filename, and store the full path elsewhere.
        self.std_drag_functions = projectile.Projectile.get_drag_functions()
        values = []
        values.extend(self.std_drag_functions)
        values.append("Specify File")
        self._drag_function = ttk.Combobox(t, values=values, state='readonly')
        self._drag_function.delete(0, tk.END)
        if proj.drag_function_file:
            i = values.index("Specify File")
            self._drag_function.current(i)
        else:
            i = values.index(proj.drag_function)
            self._drag_function.current(i)
        self._drag_function.pack()
        self._drag_function.bind('<<ComboboxSelected>>', self._drag_function_handler)

        self._ff_display = FFDisplay(master)
        self._ff_display.set_ffs(proj.copy_form_factors())

        t = tk.LabelFrame(master, text="Density Function")
        t.pack(side=tk.TOP, anchor=tk.W)
        values = projectile.Projectile.get_density_functions()
        self._density_function = ttk.Combobox(t, values=values, state='readonly')
        self._density_function.delete(0, tk.END)
        if proj.density_function:
            i = values.index(proj.density_function)
            self._density_function.current(i)
        self._density_function.pack(side=tk.TOP)
        t = tk.LabelFrame(master, text="Air Density Factor")
        t.pack(side=tk.TOP, anchor=tk.W)
        self._adf = tk.Entry(t)
        if proj.air_density_factor:
            self._adf.insert(tk.INSERT, repr(proj.air_density_factor))
        else:
            self._adf.insert(tk.INSERT, "1.0")
        self._adf.pack()
        self.update()
        set_title(proj.name, proj.filename)

    def _drag_function_handler(self, event):
        value = event.widget.get()
        values = list(event.widget['values'])
        event.widget.select_clear()
        df = value
        if value == "Specify File":
            filename = tkfd.askopenfilename(filetypes=[("All Files", "*")])
            if filename:
                df = path.basename(filename)
                self.extra_drag_functions[df] = filename
                self.drag_function = filename
            else:
                return
        else:
            self.drag_function = df
        # update the stuff in the combobox
        self._update_drag_function_combobox(df)

    def _update_drag_function_combobox(self, value):
        values = []
        values.extend(self.std_drag_functions)
        values.extend(self.extra_drag_functions.keys())
        values.append("Specify File")
        if value not in values:
            raise ValueError("Invalid drag function %s" % (value))
        self._drag_function['values'] = tuple(values)
        i = values.index(value)
        self._drag_function.current(i)

    # map from the value in the combobox to the actual filename
    #
    # The combobox is read-only, so the only way we can return an invalid value
    # is if there's a bug elsewhere here
    def _get_drag_function(self):
        value = self._drag_function.get()
        if value in self.extra_drag_functions:
            return self.extra_drag_functions[value]
        return value

    def update_projectile(self, proj):
        self.undo.append(self.projectile)
        self.projectile = proj
        self.refresh()
        pass

    def replace_drag_function(self):
        df = self._drag_function.get()
        self.projectile.set_drag_function(df)

    # update the projectile with the current state of the GUI inputs
    def update(self):
        try:
            self.mass = float(self._mass.get())
            self.caliber = float(self._caliber.get())
            self.mv = float(self._mv.get())
            self.adf = float(self._adf.get())
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))
        self.ffs = self._ff_display.get_ffs()
        self.drag_function = self._get_drag_function()
        self.density_function = self._density_function.get()
        self.name = self._name.get()
        set_title(self.name, self.projectile.filename)

    # update the GUI with the current state of the projectile
    def refresh(self):
        self._name.delete(0, tk.END)
        if self.projectile.name:
            self._name.insert(tk.INSERT, self.projectile.name)
        self._mass.delete(0, tk.END)
        self._mass.insert(tk.INSERT, repr(self.projectile.mass))
        self._caliber.delete(0, tk.END)
        self._caliber.insert(tk.INSERT, repr(self.projectile.caliber))
        self._mv.delete(0, tk.END)
        self._mv.insert(tk.INSERT, repr(self.projectile.mv))
        self._ff_display.set_ffs(self.projectile.copy_form_factors())
        if self.projectile.drag_function_file:
            self._update_drag_function_combobox(self.projectile.drag_function_file)
        else:
            self._update_drag_function_combobox(self.projectile.drag_function)
        self._density_function.delete(0, tk.END)
        self._density_function.insert(tk.INSERT, self.projectile.density_function)
        self._adf.delete(0, tk.END)
        self._adf.insert(tk.INSERT, self.projectile.air_density_factor)
        set_title(self.projectile.name, self.projectile.filename)

    def get_projectile(self):
        try:
            self.update()
            p = copy.deepcopy(self.projectile)
            p.name = self.name
            p.mass = self.mass
            p.caliber = self.caliber
            p.mv = self.mv
            p.reset_form_factors(self.ffs)
            p.set_drag_function(self.drag_function)
            p.set_density_function(self.density_function)
            p.air_density_factor = self.adf
        except ValueError as e:
            tkmb.showwarning("Error loading projectile", "%s" % (e))
            return None
        self.push_undo(p)
        return p

    # compare the given projectile with the last one we already put on the undo
    # stack, and if it's meaningfully different push it on top
    def push_undo(self, proj):
        if len(self.undo) == 0:
            self.undo.append(proj)
        p1 = self.undo[-1]
        p2 = proj
        same = True
        if p1.name != p2.name:
            same = False
        if p1.mass != p2.mass:
            same = False
        if p1.caliber != p2.caliber:
            same = False
        if p1.mv != p2.mv:
            same = False
        if p1.drag_function != p2.drag_function:
            same = False
        if p1.drag_function_file != p2.drag_function_file:
            same = False
        if p1.density_function != p2.density_function:
            same = False
        if p1.air_density_factor != p2.air_density_factor:
            same = False
        ff1 = p1.copy_form_factors()
        ff2 = p2.copy_form_factors()
        if len(ff1) != len(ff2):
            same = False
        i = 0
        while i < len(ff1):
            (d1, f1) = ff1[i]
            (d2, f2) = ff2[i]
            if d1 != d2:
                same = False
                break
            if f1 != f2:
                same = False
                break
            i += 1
        if not same:
            self.undo.append(proj)

    def set_projectile(self, proj):
        self.projectile = proj
        self.refresh()


def make_output(master, reset=None, save=None):
    t = tk.LabelFrame(master, text="Output")
    t.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    s = tk.Scrollbar(t)
    s.pack(side=tk.RIGHT, fill=tk.Y)
    output = tk.Text(t, yscrollcommand=s.set)
    output.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    s.config(command=output.yview)
    if reset or save:
        t = tk.Frame(master)
        t.pack(side=tk.BOTTOM, fill=tk.X)
        if reset:
            r = tk.Button(t, text="Clear Output", command=reset)
            r.pack(side=tk.LEFT, anchor=tk.W)
        if save:
            s = tk.Button(t, text="Save Ouptut", command=save)
            s.pack(side=tk.RIGHT, anchor=tk.E)
    return output


# this needs to be changed to a two paned vertical display
class CommandCntl(object):
    def __init__(self, master, pcntl):
        self.root = master
        self.pcntl = pcntl

        # The tabs show up left to right in this order
        self._matchff = MatchFormFactorGUI(master, pcntl)
        master.add(self._matchff.setup_display(), text="Find Form Factor")
        self._rtr = RangeTableGUI(master, pcntl)
        master.add(self._rtr.setup_display(), text="Range Table")
        self._matchrange = MatchRangeGUI(master, pcntl)
        master.add(self._matchrange.setup_display(), text="Match Range")
        self._singlerun = SingleRunGUI(master, pcntl)
        master.add(self._singlerun.setup_display(), text="Single Run")
        self._maxrange = MaxRangeGUI(master, pcntl)
        master.add(self._maxrange.setup_display(), text="Max Range")


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
# Communication with the rest of the app will be a pull process - when the user
# clicks the button to run the analysis, the command object will update the
# projectile with anything necessary for the processing.
class GUIMixin(object):

    def __init__(self, master, pcntl):
        self.master = master
        self.pcntl = pcntl
        self.frame = None
        self.args = None
        self.projectile = None

    def setup_display(self):
        if self.frame:
            # start by tossing all the existing widgets (I think?)
            for child in self.frame.pack_slaves():
                child.pack_forget()
        else:
            self.frame = tk.Frame(self.master)
            self.frame.pack(side=tk.TOP)
        return self.frame

    def process_gui(self):
        raise NotImplemented

    def update_output(self):
        raise NotImplemented

    def save_output(self):
        filename = tkfd.asksaveasfilename(
            title="Save Output",
            filetypes=[('Text', '*.txt'), ('All Files', '*')],
        )
        with open(filename, "w") as f:
            f.write(self.output.get(1.0, tk.END))

    def reset_output(self):
        self.undo.append(self.output.get(1.0, tk.END))
        self.output.delete(1.0, tk.END)

    def reset_projectile(self):
        raise NotImplemented

    def run_analysis(self):
        try:
            super(GUIMixin, self).run_analysis()
            return True
        # this is a valid use case for a catch-all exception
        except Exception as e:
            tkmb.showwarning("Error running analysis", "%s" % (e.message))
            return False


class SingleRunGUI(GUIMixin, commands.SingleRun):

    # we need to take the departure angle, and a checkbox to determine whether
    # to print out the trajectory
    def setup_display(self):
        # we want a frame at the top with the two inputs, and a "run" button
        # which gets connected to the process_gui() method
        super(SingleRunGUI, self).setup_display()

        # we're resetting the whole display, so we need to clear the
        # config_printed flag
        self.config_printed = False
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
        self.output = make_output(self.frame,
                                  reset=self.reset_output,
                                  save=self.save_output)
        return self.frame

    def process_gui(self):
        projectile = self.pcntl.get_projectile()
        if not projectile:
            return
        self.projectile = projectile
        try:
            self.departure_angle = float(self._departure_angle.get())
            self.departure_angle = math.radians(self.departure_angle)
            self.projectile.set_departure_angle(self.departure_angle)
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))
            return
        self.projectile.show_trajectory = False
        if self._print_trajectory.get() != 0:
            self.projectile.show_trajectory = True
        if not self.run_analysis():
            return
        text = ""
        if not self.config_printed:
            text = self.format_configuration()
            self.config_printed = True
        text += "\n"
        text += self.format_conditions()
        text += self.format_output()
        self.output.insert(tk.INSERT, text)

    def reset_output(self):
        super(SingleRunGUI, self).reset_output()
        self.config_printed = False


class MaxRangeGUI(GUIMixin, commands.MaxRange):

    def setup_display(self):
        # this is the simplest possible command, since all the information is
        # in the projectile definition - we don't need to supply anything at
        # all
        super(MaxRangeGUI, self).setup_display()
        t = tk.Frame(self.frame)
        t.pack(side=tk.TOP)
        run = tk.Button(t, text="Run Calculation", command=self.process_gui)
        run.pack(side=tk.LEFT)
        self.output = make_output(self.frame,
                                  reset=self.reset_output,
                                  save=self.save_output)
        return self.frame

    def process_gui(self):
        projectile = self.pcntl.get_projectile()
        if not projectile:
            return
        self.projectile = projectile
        if not self.run_analysis():
            return
        text = self.format_configuration()
        text += "\n"
        text += self.format_output()
        text += "\n"
        self.output.insert(tk.INSERT, text)


class MatchRangeGUI(GUIMixin, commands.MatchRange):

    def setup_display(self):
        self.config_printed = False
        super(MatchRangeGUI, self).setup_display()
        # input in this case is simply the target range
        t = tk.Frame(self.frame)
        t.pack(side=tk.TOP)
        tr = tk.LabelFrame(t, text="Target Range")
        tr.pack(side=tk.LEFT)
        self._target_range = tk.Entry(tr)
        self._target_range.insert(tk.INSERT, "0")
        self._target_range.pack()
        run = tk.Button(t, text="Run Calculation", command=self.process_gui)
        run.pack(side=tk.LEFT)
        self.output = make_output(self.frame,
                                  reset=self.reset_output,
                                  save=self.save_output)
        return self.frame

    def process_gui(self):
        projectile = self.pcntl.get_projectile()
        if not projectile:
            return
        self.projectile = projectile

        self.args = self.projectile.make_args()
        try:
            tr = self._target_range.get()
            tr = float(tr)
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))
            return
        self.args.target_range = [tr]
        if not self.run_analysis():
            return
        text = ""
        if not self.config_printed:
            text = self.format_configuration()
            self.config_printed = True
        text += self.format_output()
        self.output.insert(tk.INSERT, text)

    def reset_output(self):
        self.config_printed = False
        super(MatchRangeGUI, self).reset_output()


class MatchFormFactorGUI(GUIMixin, commands.MatchFormFactor):

    def __init__(self, master, pcntl):
        self.ffs = []
        super(MatchFormFactorGUI, self).__init__(master, pcntl)

    def setup_display(self):
        self.config_printed = False
        super(MatchFormFactorGUI, self).setup_display()
        t = tk.LabelFrame(self.frame, text="Shot to Match")
        t.pack(side=tk.TOP)
        da = tk.LabelFrame(t, text="Departure Angle")
        da.pack(side=tk.LEFT)
        self._departure_angle = tk.Entry(da)
        self._departure_angle.insert(tk.INSERT, "0")
        self._departure_angle.pack()
        tr = tk.LabelFrame(t, text="Target Range")
        tr.pack(side=tk.LEFT)
        self._target_range = tk.Entry(tr)
        self._target_range.insert(tk.INSERT, "0")
        self._target_range.pack()
        rf = tk.LabelFrame(t, text="")
        rf.pack(side=tk.LEFT)
        run = tk.Button(rf, text="Run", command=self.process_gui)
        run.pack(side=tk.LEFT)
        t = tk.LabelFrame(self.frame, text="Projectile")
        t.pack(side=tk.TOP)
        copy = tk.Button(t, text="Copy FFs", command=self.copy_projectile_ffs)
        copy.pack(side=tk.LEFT)
        show = tk.Button(t, text="Show FFs", command=self.popup_ffs)
        show.pack(side=tk.LEFT)
        update = tk.Button(t, text="Update FFs", command=self.update_projectile_ffs)
        update.pack(side=tk.LEFT)
        self.output = make_output(self.frame,
                                  reset=self.reset_output,
                                  save=self.save_output)
        return self.frame

    def process_gui(self):
        projectile = self.pcntl.get_projectile()
        if not projectile:
            return
        self.projectile = projectile

        self.args = self.projectile.make_args()
        try:
            tr = self._target_range.get()
            tr = float(tr)
            da = self._departure_angle.get()
            da = float(da)
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))
            return
        self.args.shot = ["%f,%f" % (da, tr)]
        if not self.run_analysis():
            return
        self.ffs.extend(self.projectile.copy_form_factors())
        self.projectile.clear_form_factors()
        self.projectile.unset_departure_angle()
        text = ""
        if not self.config_printed:
            text += self.format_header()
            self.config_printed = True
        text += self.format_output()
        self.output.insert(tk.INSERT, text)

    def reset_output(self):
        self.config_printed = False
        super(MatchFormFactorGUI, self).reset_output()

    def copy_projectile_ffs(self):
        self.projectile = self.pcntl.get_projectile()
        self.ffs = self.projectile.copy_form_factors()

    def update_projectile_ffs(self):
        self.projectile = self.pcntl.get_projectile()
        self.projectile.clear_form_factors()
        self.projectile.unset_departure_angle()
        self.projectile.reset_form_factors(self.ffs)
        self.pcntl.update_projectile(self.projectile)

    def popup_ffs(self):
        self.toplevel = tk.Toplevel()
        self.toplevel.title("Form Factors")
        self.toplevel.transient()
        t = tk.Frame(self.toplevel)
        t.pack(side=tk.TOP)
        self._ffd = FFDisplay(t)
        self._ffd.set_ffs(self.ffs)
        t = tk.Frame(self.toplevel)
        t.pack(side=tk.TOP)
        cancel = tk.Button(t, text="Cancel", command=self.toplevel.destroy)
        cancel.pack(side=tk.LEFT, anchor=tk.W)
        save = tk.Button(t, text="Save", command=self.update_local_ffs)
        save.pack(side=tk.RIGHT, anchor=tk.E)

    def update_local_ffs(self):
        self.ffs = self._ffd.get_ffs()
        self.toplevel.destroy()

    def show_ffs(self):
        text = "\nCurrent Form Factors\n"
        for (da, ff) in self.ffs:
            text += "%f: %f\n" % (math.degrees(da), ff)
        text += "\n"
        self.output.insert(tk.INSERT, text)


class RangeTableGUI(GUIMixin, commands.RangeTable):

    def setup_display(self):
        self.config_printed = False
        super(RangeTableGUI, self).setup_display()
        t = tk.LabelFrame(self.frame, text="Settings")
        t.pack(side=tk.TOP)
        start = tk.LabelFrame(t, text="Start Range")
        start.pack(side=tk.LEFT)
        self._start = tk.Entry(start)
        self._start.insert(tk.INSERT, "0")
        self._start.pack()
        end = tk.LabelFrame(t, text="End Range")
        end.pack(side=tk.LEFT)
        self._end = tk.Entry(end)
        self._end.insert(tk.INSERT, "0")
        self._end.pack()
        inc = tk.LabelFrame(t, text="Increment")
        inc.pack(side=tk.LEFT)
        self._inc = tk.Entry(inc)
        self._inc.insert(tk.INSERT, "0")
        self._inc.pack()
        run = tk.Button(t, text="Run", command=self.process_gui)
        run.pack(side=tk.TOP)
        self.output = make_output(self.frame,
                                  reset=self.reset_output,
                                  save=self.save_output)
        return self.frame

    def process_gui(self):
        projectile = self.pcntl.get_projectile()
        if not projectile:
            return
        self.projectile = projectile

        self.args = self.projectile.make_args()
        try:
            start = self._start.get()
            start = float(start)
            end = self._end.get()
            end = float(end)
            inc = self._inc.get()
            inc = float(inc)
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))
            return
        self.args.start = start
        self.args.end = end
        self.args.increment = inc
        if not self.run_analysis():
            return
        text = self.format_header()
        text += "\n"
        text += self.format_output()
        self.output.insert(tk.INSERT, text)


def parse_args():
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    arguments.set_common_defaults(parser)
    arguments.add_common_args(parser)
    return parser.parse_args()


def main():
    root = tk.Tk()
    root.title("Master Exterior Ballistics")

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

