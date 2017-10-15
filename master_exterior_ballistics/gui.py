#!/usr/bin/env python2

import argparse
import copy
import math
from os import path
import time
import Tkinter as tk
import ttk
import tkFileDialog as tkfd
import tkMessageBox as tkmb

from master_exterior_ballistics import projectile
from master_exterior_ballistics.projectile import cmp_projectiles
from master_exterior_ballistics import commands
from master_exterior_ballistics import config
from master_exterior_ballistics import arguments

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


CONFIG = None
STATUS = None


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
        mb.add_command(label="Open Recent", command=self.recent_files)
        mb.add_command(label="Save", command=self.save_projectile)
        mb.add_command(label="Save As", command=self.save_projectile_as)
        mb.add_separator()
        mb.add_command(label="Quit", command=self.quit)
        self._edit = tk.Menubutton(self.menu, text="Edit")
        self._edit.pack(side=tk.LEFT)
        mb = tk.Menu(self._edit)
        self._edit['menu'] = mb
        mb.add_command(label="Undo", command=self.undo_projectile)
        mb.add_command(label="Undo History", command=self.undo_history)
        self.panes = tk.PanedWindow(master,
                                    orient=tk.HORIZONTAL,
                                    showhandle=False)
        self.panes.pack(fill=tk.BOTH, expand=1)
        self.pframe = tk.LabelFrame(self.panes,
                                    text="Projectile Details",
                                    bd=0)
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
        STATUS.push_recent_file(filename)
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
        STATUS.push_recent_file(filename)
        proj.to_config(self.last_savefile)
        set_title(proj.name, filename)

    def load_projectile(self):
        filename = ""
        ts, filename = STATUS.get_last_file()
        initialdir = STATUS.get_last_dir()
        if self.last_savefile:
            filename = self.last_savefile
        filename = tkfd.askopenfilename(initialfile=filename,
                                        initialdir=initialdir,
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
            STATUS.push_recent_file(filename)
            set_title(proj.name, filename)
        except projectile.MissingAttribute as e:
            tkmb.showerror("Invalid Config File",
                           message=(
                               "Could not load file %s: %s" % (filename, e)
                           ))

    def new_projectile(self):
        proj = projectile.Projectile.from_defaults()
        self.pcntl.set_projectile(proj)
        set_title(proj.name)

    def quit(self):
        global master_window
        master_window.destroy()

    def undo_projectile(self):
        self.pcntl.pop_history()

    def undo_history(self):
        self.pcntl.popup_history()

    def recent_files(self):
        filename = self.pcntl.popup_recent_files()
        if filename:
            try:
                proj = projectile.Projectile.from_file(filename)
                self.pcntl.set_projectile(proj)
                self.last_savefile = filename
                STATUS.push_recent_file(filename)
                set_title(proj.name, filename)
            except projectile.MissingAttribute as e:
                tkmb.showerror("Invalid Config File",
                               message=(
                                   "Could not load file "
                                   "%s: %s" % (filename, e)
                                ))


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
                                 values=("%.6f" % (ff)))
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


class ShotDisplay(object):
    def __init__(self, master):
        self.shots = []
        self.shots_ids = {}

        # Unfortunately, I can't really see a way to make this less klunky -
        # it's literally cut and pasted with only the labels and a few other
        # details changed, but . . .
        t = tk.LabelFrame(master, text="Shots")
        t.pack(side=tk.TOP, anchor=tk.W)
        f = tk.Frame(t)
        f.pack(side=tk.TOP)
        s = tk.Scrollbar(f)
        s.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(f,
                                 columns=("TR"),
                                 height=10,
                                 yscrollcommand=s.set)
        self.tree.column("#0", width=80)
        self.tree.heading("#0", text="DA")
        self.tree.column("TR", width=120)
        self.tree.heading("TR", text="Target Range")
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
        ffl = tk.Label(labels, text="Target Range")
        ffl.pack(side=tk.BOTTOM)
        entries = tk.Frame(f)
        entries.pack(side=tk.LEFT)
        self._da = tk.Entry(entries, width=10)
        self._da.insert(tk.INSERT, "0")
        self._da.pack(side=tk.TOP, anchor=tk.W)
        self._tr = tk.Entry(entries, width=10)
        self._tr.insert(tk.INSERT, "0")
        self._tr.pack(side=tk.TOP, anchor=tk.W)
        add = tk.Frame(f)
        add.pack(side=tk.RIGHT, anchor=tk.E)
        b = tk.Button(add, text="Add", command=self.add_shot)
        b.pack(side=tk.RIGHT, anchor=tk.E)

        f = tk.Frame(t)
        f.pack(side=tk.BOTTOM, anchor=tk.W)
        b = tk.Button(f, text="Clear All", command=self.clear_shots)
        b.pack(side=tk.LEFT)
        b = tk.Button(f, text="Delete", command=self.delete_shot)
        b.pack(side=tk.RIGHT, anchor=tk.E)

    def set_shots(self, shots):
        self.shots = shots
        self.show_shots()

    def get_shots(self):
        return self.shots

    def clear_shots(self):
        self.shots = []
        self.show_shots()

    def show_shots(self):
        for iid in self.shots_ids.keys():
            self.tree.delete(iid)
        self.shots_ids = {}
        for (da, tr) in self.shots:
            t = self.tree.insert("", "end",
                                 text="%.4f" % (da),
                                 values=("%.1f" % (tr)))
            self.shots_ids[t] = da

    def add_shot(self):
        da = float(self._da.get())
        self._da.delete(0, tk.END)
        self._da.insert(tk.INSERT, "0")
        tr = float(self._tr.get())
        self._tr.delete(0, tk.END)
        self._tr.insert(tk.INSERT, "0")
        self.shots.append((da, tr))
        self.show_shots()

    def delete_shot(self):
        iid = self.tree.focus()
        if not iid:
            return
        tda = self.shots_ids[iid]
        t = []
        found = False
        for (da, tr) in self.shots:
            # this is safe because tda and da come from the same source
            #
            # note that we only want to delete /one/ of these . . .
            if tda == da and not found:
                found = True
                continue
            t.append((da, tr))
        self.shots = t
        self.show_shots()


# This is an attempt to make the undo support more powerful and usable.
#
# The idea of an undo stack is pretty obvious and in theory quite nice, but
# I've seen better ways of managing it. The one that I like is to allow the
# user to browse the stack and pick a point to return to - this is far more
# powerful than simply popping the top off the stack until you get back to the
# point you want. It shouldn't be too hard to implement, either - all you need
# is a way to visualise/display the undo stack.
#
# I'd like to support /redo/ as well as undo, but the detailed logic of that is
# harder to think through. The simplest approach is to say that redo just moves
# forward on the undo list, the same way that undo moves backwards on it, so
# that you have something like this:
#
# start . . . . undo now redo . . . end
#
# In the undo-as-stack-pop model, when you pop something off the undo stack the
# current state needs to be pushed onto the redo stack; in the
# undo-as-list-traversal redo would mean looking through the undo list again.
# In both cases you have the question of what happens after the /next/
# push/append onto the undo list. At that point you have more than one future
# (redo) path, both of which are only meaningful in the context of the branch
# point.
#
# In the stack model it makes perfect sense to just toss the redo stack
# whenever you push a new state onto the undo stack - you can't peek at either
# of the stacks, you just have a choice of moving to the state behind you, or
# the one in front, and once you've started moving forward there /is/ no
# meaningful state in front, and hence no meaningful 'redo' operation.
#
# In the list model, though, each element in the list isn't defined by its
# relationship with the previous and next elements - each element is simply a
# point in time with a certain set of state information. Going back to a
# previous point just means bringing that state information to the front of the
# list, so that any future undo information will be based on /that/ state
# rather than whatever it was before. But there's no reason to toss all the
# elements on the list ahead of that point - they can stick around, so that
# next time the user wants to go back in time they're still there as options.
#
# I guess that's really a history browser, rather than undo/redo.
class HistoryBrowser(object):
    def __init__(self, master, history):
        self.history = history
        self.history_ids = {}
        self.selected = None
        self.toplevel = tk.Toplevel()
        self.toplevel.title = "History Browser"
        self.toplevel.transient()

        # As with everything else here this is klunky. It's modeled on the form
        # factor display, but with a bit more information.
        #
        # We start with a label frame, a treeview showing the history data, a
        # button to pick the history entry (and close the dialog box), and a
        # button to cancel the history selection process.
        t = tk.LabelFrame(self.toplevel, text="History Browser")
        t.pack(side=tk.TOP, anchor=tk.W, fill=tk.BOTH, expand=1)
        f = tk.Frame(t)
        f.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        s = tk.Scrollbar(f)
        s.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(f,
                                 columns=("History"),
                                 height=10,
                                 yscrollcommand=s.set)
        self.tree.column("#0", minwidth=200)
        self.tree.heading("#0", text="History")
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        s.config(command=self.tree.yview)
        f = tk.Frame(t)
        f.pack(side=tk.TOP)
        buttons = tk.Frame(f, width=80)
        buttons.pack(side=tk.TOP)
        self.cancel = tk.Button(buttons,
                                text="Cancel",
                                command=self.cancel_selection)
        self.cancel.pack(side=tk.LEFT)
        self.select = tk.Button(buttons,
                                text="Select",
                                command=self.select)
        self.select.pack(side=tk.RIGHT, anchor=tk.E)

        for entry in self.history:
            self._add_entry(entry)

    def _add_entry(self, entry):
        if type(entry) != HistoryEntry:
            print entry
            raise TypeError("Needs a HistoryEntry")
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.ts))
        t = self.tree.insert("", "end",
                             text=ts,
                             values=())
        self.history_ids[t] = entry
        self.tree.insert(t, "end",
                         text="Name",
                         values=(entry.proj.name))
        self.tree.insert(t, "end",
                         text="Mass",
                         values=("%.2f" % (entry.proj.mass)))
        self.tree.insert(t, "end",
                         text="Caliber",
                         values=("%.2f" % (entry.proj.caliber)))
        self.tree.insert(t, "end",
                         text="Muzzle Velocity",
                         values=("%.2f" % (entry.proj.mv)))
        if entry.proj.drag_function_file:
            self.tree.insert(t, "end",
                             text="Drag Function File",
                             values=(entry.proj.drag_function_file))
        else:
            self.tree.insert(t, "end",
                             text="Drag Function",
                             values=(entry.proj.drag_function))
        self.tree.insert(t, "end",
                         text="Density Function",
                         values=(entry.proj.density_function))
        ffs = entry.proj.copy_form_factors()
        ff = self.tree.insert(t, "end",
                              text="Form Factors",
                              values=())
        for (d, f) in ffs:
            self.tree.insert(ff, "end",
                             text="%.4f" % (math.degrees(d)),
                             values=("%.4f" % (f)))

    def cancel_selection(self):
        self.selected = None
        self.toplevel.destroy()

    def select(self):
        iid = self.tree.focus()
        if not iid:
            return
        self.selected = self.history_ids[iid]
        self.toplevel.destroy()


class HistoryEntry(object):
    def __init__(self, proj):
        self.ts = time.time()
        self.proj = proj


class RecentFileBrowser(object):
    def __init__(self, master, recent_files):
        self.recent_files = recent_files
        self.recent_files_ids = {}
        self.selected = None
        self.toplevel = tk.Toplevel()
        self.toplevel.title = "Recent Files"
        self.toplevel.transient()

        # this stuff needs to be broken out, but for now I'll keep cutting and
        # pasting . . .
        t = tk.LabelFrame(self.toplevel, text="Recent Files")
        t.pack(side=tk.TOP, anchor=tk.W, fill=tk.BOTH, expand=1)
        f = tk.Frame(t)
        f.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        s = tk.Scrollbar(f)
        s.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(f,
                                 columns=("Date", "Directory"),
                                 height=10,
                                 yscrollcommand=s.set)
        self.tree.column("#0", minwidth=200)
        self.tree.heading("#0", text="Filename")
        self.tree.column("Date", minwidth=100)
        self.tree.heading("Date", text="Date")
        self.tree.column("Directory", minwidth=100)
        self.tree.heading("Directory", text="Directory")
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        s.config(command=self.tree.yview)
        f = tk.Frame(t)
        f.pack(side=tk.TOP)
        buttons = tk.Frame(f, width=80)
        buttons.pack(side=tk.TOP)
        self.cancel = tk.Button(buttons,
                                text="Cancel",
                                command=self.cancel_selection)
        self.cancel.pack(side=tk.LEFT)
        self.select = tk.Button(buttons,
                                text="Select",
                                command=self.select)
        self.select.pack(side=tk.RIGHT, anchor=tk.E)

        for entry in self.recent_files:
            self._add_entry(entry)

    def _add_entry(self, entry):
        (timestamp, filename) = entry
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(timestamp)))
        basename = path.basename(filename)
        dirname = path.dirname(filename)
        if len(dirname) > 32:
            dirname = dirname[-30:]
            if dirname[0] == path.sep:
                dirname = dirname[1:]
            dirname = ".." + dirname
        t = self.tree.insert("", "end",
                             text=basename,
                             values=(ts, dirname))
        self.recent_files_ids[t] = filename

    def cancel_selection(self):
        self.selected = None
        self.toplevel.destroy()

    def select(self):
        iid = self.tree.focus()
        if not iid:
            return
        self.selected = self.recent_files_ids[iid]
        self.toplevel.destroy()


# our master is the top level left panel frame
class ProjectileCntl(object):
    def __init__(self, master, proj):
        self.root = master
        self.projectile = proj
        self.extra_drag_functions = {}
        self.history = []
        self.last_projectile = None

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
        self._drag_function.bind('<<ComboboxSelected>>',
                                 self._drag_function_handler)

        self._ff_display = FFDisplay(master)
        self._ff_display.set_ffs(proj.copy_form_factors())

        t = tk.LabelFrame(master, text="Density Function")
        t.pack(side=tk.TOP, anchor=tk.W)
        values = projectile.Projectile.get_density_functions()
        self._density_function = ttk.Combobox(t,
                                              values=values,
                                              state='readonly')
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
        self.refresh()
        set_title(proj.name, proj.filename)

    def _drag_function_handler(self, event):
        value = event.widget.get()
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

    def _update_density_function_combobox(self, value):
        values = list(self._density_function['values'])
        if value not in values:
            raise ValueError("Invalid density function %s" % (value))
        i = values.index(value)
        self._density_function.current(i)

    def update_projectile(self, proj):
        self.push_history(self.projectile)
        self._update_projectile(proj)

    def _update_projectile(self, proj):
        self.projectile = proj
        self.refresh()

    def replace_drag_function(self):
        df = self._drag_function.get()
        self.projectile.set_drag_function(df)

    # update the local state with the current state of the GUI inputs
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
        self._update_density_function_combobox(self.projectile.density_function)
        self._adf.delete(0, tk.END)
        self._adf.insert(tk.INSERT, self.projectile.air_density_factor)
        set_title(self.projectile.name, self.projectile.filename)

    # copy the local state into a copy of the current projectile
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
        self.push_history(self.projectile)
        self.projectile = p
        return p

    # compare the given projectile with the last one we already put on the undo
    # stack, and if it's meaningfully different push it on top
    def push_history(self, proj):
        hentry = HistoryEntry(proj)
        if len(self.history) == 0:
            self.history.append(hentry)
            return

        if not cmp_projectiles(self.history[-1].proj, proj):
            self.history.append(hentry)

    # pop the last history entry off the stack
    def pop_history(self):
        if len(self.history) > 0:
            hentry = self.history.pop()
            self._update_projectile(hentry.proj)
            self.refresh()
            return
        tkmb.showwarning("No More History",
                         "Already at end of the undo history")

    # popup the history browser
    def popup_history(self):
        hbrowser = HistoryBrowser(self.root, self.history)
        self.root.wait_window(hbrowser.toplevel)
        if hbrowser.selected:
            self._update_projectile(hbrowser.selected.proj)
            self.refresh()
            return

    # popup the recent files browser
    def popup_recent_files(self):
        recent_files = STATUS.get_recent_files()
        rfbrowser = RecentFileBrowser(self.root, recent_files)
        self.root.wait_window(rfbrowser.toplevel)
        if rfbrowser.selected:
            return rfbrowser.selected

    def set_projectile(self, proj):
        self.push_history(self.projectile)
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
        self.history = []

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
        self.history.append(self.output.get(1.0, tk.END))
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
        c = tk.Checkbutton(t, text="Print Trajectory",
                           variable=self._print_trajectory)
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
        if not cmp_projectiles(self.projectile, projectile):
            self.config_printed = False
            self.output.insert(tk.INSERT, "\n")
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
        self.output.yview_moveto(1.0)

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
        self.output.yview_moveto(1.0)


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
        if not cmp_projectiles(self.projectile, projectile):
            self.config_printed = False
            self.output.insert(tk.INSERT, "\n")
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
        self.output.yview_moveto(1.0)

    def reset_output(self):
        self.config_printed = False
        super(MatchRangeGUI, self).reset_output()


class MatchFormFactorGUI(GUIMixin, commands.MatchFormFactor):

    def __init__(self, master, pcntl):
        self.ffs = []
        self.inputs = []
        super(MatchFormFactorGUI, self).__init__(master, pcntl)

    def setup_display(self):
        self.config_printed = False
        super(MatchFormFactorGUI, self).setup_display()
        t = tk.LabelFrame(self.frame, text="Shots")
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
        run_one = tk.Button(t, text="Add", command=self.process_gui)
        run_one.pack(side=tk.LEFT)
        run_all = tk.Button(t, text="Run", command=self.repeat_shots)
        run_all.pack(side=tk.LEFT)
        show = tk.Button(t, text="Edit", command=self.popup_shots)
        show.pack(side=tk.LEFT)
        tf = tk.Frame(self.frame)
        tf.pack(side=tk.TOP)
        t = tk.LabelFrame(tf, text="Projectile")
        t.pack(side=tk.RIGHT)
        copy = tk.Button(t, text="Copy FFs", command=self.copy_projectile_ffs)
        copy.pack(side=tk.LEFT)
        show = tk.Button(t, text="Show FFs", command=self.popup_ffs)
        show.pack(side=tk.LEFT)
        update = tk.Button(t, text="Update FFs",
                           command=self.update_projectile_ffs)
        update.pack(side=tk.LEFT)
        self.output = make_output(self.frame,
                                  reset=self.reset_output,
                                  save=self.save_output)
        return self.frame

    def add_shot(self):
        try:
            tr = self._target_range.get()
            tr = float(tr)
            da = self._departure_angle.get()
            da = float(da)
        except ValueError as e:
            tkmb.showwarning("Conversion Error", "%s" % (e))
            return
        self.inputs.append((da, tr))
        return (da, tr)

    def process_gui(self):
        shot = self.add_shot()
        self._process_shots([shot])

    def _process_shots(self, shots):
        projectile = self.pcntl.get_projectile()
        if not projectile:
            return
        if self.projectile:
            self.projectile.clear_form_factors()
        projectile.clear_form_factors()
        if not cmp_projectiles(self.projectile, projectile):
            self.reset_ffs()
            self.config_printed = False
            self.output.insert(tk.INSERT, "\n")
        self.projectile = projectile

        self.args = self.projectile.make_args()
        self.args.shot = ["%f,%f" % (d, t) for (d, t) in shots]
        if not self.run_analysis():
            return
        new_ffs = [(l, ff) for (ff, l, rg, c) in self.shots]
        self.ffs.extend(new_ffs)
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

    def reset_ffs(self):
        self.ffs = []

    def reset_shots(self):
        self.inputs = []

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
        self.ff_toplevel = tk.Toplevel()
        self.ff_toplevel.title("Form Factors")
        self.ff_toplevel.transient()
        t = tk.Frame(self.ff_toplevel)
        t.pack(side=tk.TOP)
        self._ffd = FFDisplay(t)
        self._ffd.set_ffs(self.ffs)
        t = tk.Frame(self.ff_toplevel)
        t.pack(side=tk.TOP)
        cancel = tk.Button(t, text="Cancel", command=self.ff_toplevel.destroy)
        cancel.pack(side=tk.LEFT, anchor=tk.W)
        save = tk.Button(t, text="Save", command=self.update_local_ffs)
        save.pack(side=tk.RIGHT, anchor=tk.E)

    def update_local_ffs(self):
        self.ffs = self._ffd.get_ffs()
        self.ff_toplevel.destroy()

    def show_ffs(self):
        text = "\nCurrent Form Factors\n"
        for (da, ff) in self.ffs:
            text += "%f: %f\n" % (math.degrees(da), ff)
        text += "\n"
        self.output.insert(tk.INSERT, text)

    def popup_shots(self):
        self.sh_toplevel = tk.Toplevel()
        self.sh_toplevel.title("Shot History")
        self.sh_toplevel.transient()
        t = tk.Frame(self.sh_toplevel)
        t.pack(side=tk.TOP)
        self._shd = ShotDisplay(t)
        self._shd.set_shots(self.inputs)
        t = tk.Frame(self.sh_toplevel)
        t.pack(side=tk.TOP)
        cancel = tk.Button(t, text="Cancel", command=self.sh_toplevel.destroy)
        cancel.pack(side=tk.LEFT, anchor=tk.W)
        save = tk.Button(t, text="Save", command=self.update_shots)
        save.pack(side=tk.RIGHT, anchor=tk.E)

    def update_shots(self):
        self.inputs = self._shd.get_shots()
        self.sh_toplevel.destroy()

    def repeat_shots(self):
        self._process_shots(self.inputs)


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
        self.output.yview_moveto(1.0)


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

    # set up the global status
    global CONFIG
    CONFIG = config.Config()
    global STATUS
    STATUS = config.Status()

    App(root, p)

    root.mainloop()


if __name__ == '__main__':
    main()
