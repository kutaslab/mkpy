#!/usr/bin/env python

__version__ = "0.0.0"

import tkinter as tk
import tkinter.font as tk_font
import tkinter.ttk as ttk
import tkinter.filedialog as tkfd

import sys
import re

import logging
import tempfile

import numpy as np
import pandas as pd
from collections import OrderedDict as odict
from mkpy import mkh5
import pprint as pp

import pdb
import warnings

# import dpath, dpath.util
from . import dpath
from mkpy import pygarv as pg

from . import current_function, indent, log_exceptions

## appearance
## Initial panel dims
VIEW_WIDTH = 1200
VIEW_HEIGHT = 800

# global styles
def set_styles():

    # Poached from tango

    # Butter       fce94f edd400 c4a000
    # Orange       fcaf3e f57900 ce5c00
    # Chocolate    e9b96e c17d11 8f5902
    # Chameleon    8ae234 73d216 4e9a06
    # Sky Blue     729fcf 3465a4 204a87
    # Plum         ad7fa8 75507b 5c3566
    # Scarlet Red  ef2929 cc0000 a40000
    # Aluminium    eeeeec d3d7cf babdb6
    #              888a85  555753  2e3436

    # Note: frame styles don't have 'active' do have <Enter> bindings
    style = ttk.Style()

    # generic_bgc = '#eeeeec' # 'white'
    generic_bgc = "white"  # '#fafafa' # 'white'

    # 'helvetica' # 'TkDefaultFont' # 'helvetica'
    fnt_family = "TkDefaultFont"
    fnt_size = 14
    # fnt_family = 'fixed'
    # fnt_size = 16
    label_pad = 2

    # Aluminium	    eeeeec  d3d7cf  babdb6  (lighter gray)
    #               888a85  555753  2e3436  (darker gray)
    generic_frame_bgc = "#d3d7cf"  # '#babdb6' # '#d3d7cf' # '#eeeeec',
    generic_frame_fgc = "#555753"

    style.configure(
        "TFrame", background=generic_frame_bgc, foreground=generic_frame_bgc
    )

    style.configure(
        "TLabelframe",
        # background = generic_frame_bgc,
        background=generic_frame_bgc,
        foreground=generic_frame_fgc,
        relief="none",
        font=(fnt_family, fnt_size),
    )

    style.configure(
        "TLabelframe.Label",
        padding=label_pad,
        background=generic_frame_bgc,
        foreground=generic_frame_fgc,
        font=(fnt_family, fnt_size),
    )

    # Tabs
    style.configure(
        "h5nav_style.TNotebook",
        background=generic_frame_bgc,
        foreground=generic_frame_fgc,
        font=(fnt_family, fnt_size),
    )

    style.configure(
        "h5nav_style.TNotebook.Tab",
        padding=label_pad,
        background=generic_frame_bgc,
        foreground=generic_frame_fgc,
        font=(fnt_family, fnt_size),
    )

    # Data block text view ----------------------------------------
    style.configure(
        "dblock_table_style.Treeview.Heading",
        foreground="black",
        font=(fnt_family, fnt_size, "bold"),
    )

    font_size = 11
    style.configure(
        "dblock_table_style.Treeview",
        background="black",
        foreground="green",
        font=(fnt_family, fnt_size - 2),
    )

    # PyGarv Treeview --------------------------------------------------
    # Scarlet Red	ef2929	cc0000	a40000
    style.configure(
        "pygarv_style.TLabelframe",
        bgc=generic_frame_bgc,
        font=(fnt_family, fnt_size),
    )

    style.configure(
        "pygarv_style.TLabelframe.Label",
        background="#babdb6",
        foreground="#555753",
        font=(fnt_family, fnt_size),
    )

    pygarv_view_fgc = "#ef2929"  # '#cc0000' '#a40000'
    style.configure(
        "pygarv_style.Treeview",
        background=generic_bgc,
        foreground=pygarv_view_fgc,
        font=(fnt_family, fnt_size, "bold"),
    )
    # style.map('pygarv_style.Treeview',
    #           background=[('focus', pygarv_view_fgc),
    #                       ('!focus', generic_bgc)] )

    style.configure(
        "pygarv_style.Treeview.Heading",
        background=pygarv_view_fgc,
        foreground="white",
        font=(fnt_family, fnt_size, "bold"),
    )

    # Header Treeview ---------------------------------------------------
    # Sky Blue	729fcf	3465a4	204a87
    header_view_fgc = "#3465a4"  # '#204a87'
    style.configure(
        "headerview_style.Treeview",
        background=generic_bgc,
        foreground=header_view_fgc,
        font=(fnt_family, fnt_size),
    )

    header_view_fgc = "#3465a4"  # '#204a87'
    style.configure(
        "headerview_style.Treeview.Heading",
        anchor=tk.W,
        background=header_view_fgc,
        foreground="white",
        font=(fnt_family, fnt_size, "bold"),
    )

    # H5 Navigator Tab Treeview ------------------------------------
    # Plum	        ad7fa8	75507b	5c3566
    h5_view_fgc = "#75507b"
    style.configure(
        "h5view_style.Treeview",
        anchor=tk.W,
        background=generic_bgc,
        foreground=h5_view_fgc,
        font=(fnt_family, fnt_size),
    )

    style.configure(
        "h5view_style.Treeview.Heading",
        anchor=tk.W,
        background="#ad7fa8",
        foreground="white",
        font=(fnt_family, fnt_size, "bold"),
    )


# ------------------------------------------------------------
class PyGarvView(ttk.LabelFrame):
    """thin wrapper around PyGarvEditor model-view for selecting, editing, deleting pygarv tests 

    Fun facts 

    - the mkh5 data file is *not* modified 

    - View.model.pg maintains the local PyGarv() data model that tracks test results 

    - pygarv tests are tracked and run "what if"

    - test results are are overlayed for viewing in the scope traces and table
      scope

    - test doc may be exported as yaml \*.yarf

        - open an editor for new/existing tests and hands them off to Model.pygarv to dry run


    Outline

    - on init ...

        - pygarv (comes with a built in catalog of implemented tests)

        - walk the dblocks and scrape data for pygarv data stream and
          headers for any pygarv tests

        - user edits create, delete, update the in-memory test specs

        - when input validated for type, self.model.pg attemps to run the test

        - success on running updates the self.pg.pg.tr_docs w/ the test and triggers
          a view._update() cascade 

        - failure returns the exception for handling by the viewer
    
        - Export button dumps the .yarf YAML (= yarf_docs) for the tr_docs

        - mini-console shows activity and messages

    """

    def __init__(self, parent, *args, **kwargs):
        """a label frame wrapping PyGarvTestView ttk.TreeView which does the work """

        self.model = parent.model
        super().__init__(parent, *args, **kwargs)
        self.pack(expand=1, fill="both")
        self.pg_editor = PyGarvEditorView(self, orient="vertical")

    @log_exceptions(0)
    def _update(self):
        # only update editor, catalog is static
        self.pg_editor.editor._update()


class PyGarvEditorView(tk.PanedWindow):
    def __init__(self, parent, *args, **kwargs):
        """pygarv test editor UI

        layout:

        - dashboard w/ File I/O, progress bar, mini-console

        - pygarv catalog (ttk.Treeview)

        - tests for current datablock (ttk.Treeview)

        - the catalog and dblock test trees are subclassed from
          PyGarvTestView in a label frame wrapper

        Test parameter type validation triggers custom event <<IsValidTestTree>>

        """
        super().__init__(parent, *args, **kwargs)

        # self.config(text='Catalog')

        self.model = parent.model

        # dashboard for .Yarf Load, Save, Progress bar
        dash_height = 100
        self.dashboard = PyGarvEditorDashboard(self)
        self.add(self.dashboard, minsize=dash_height)

        # pygarv catalog
        self.catalog = PyGarvCatalogView(self)
        self.add(self.catalog)

        # current dblock test editor
        self.editor = PyGarvTestView(self)
        self.add(self.editor, minsize=200)

        # initial panel layout
        self.sash_place(0, 0, dash_height)
        self.sash_place(1, 0, dash_height + 120)
        self.pack(fill="both", expand=1)

        # request new editor pull new test from catalog
        # self.event_add('<<NewTestFromCatalog>>', '<Triple-Button>')


class PyGarvEditorDashboard(ttk.Frame):
    """wrapper for Editor UI controls """

    def __init__(self, parent):
        self.parent = parent
        self.model = parent.model

        super().__init__(parent, height=120)
        self.pack(fill="x", expand=1)

        # yarf reader/writer
        self.file_io = ttk.LabelFrame(self, text="File (.yarf)")
        self.file_io.pack(side="top", fill="x", expand=0)

        import_yarf = ttk.Button(
            self.file_io, text="Import", command=self._on_import
        )
        import_yarf.pack(side="left", expand=0)

        export_yarf = ttk.Button(
            self.file_io, text="Export", command=self._on_export
        )
        export_yarf.pack(side="left", expand=0)

        # stub to track test running
        self.progress = ttk.Progressbar(self.file_io)
        self.progress.pack(side="left", fill="both", expand=1)

        # mini-console
        self.console = tk.Text(self, height=4)
        self.console.pack(side="top", fill="both", expand=0)

    def _console_log(self, item, text=""):
        """report stuff back to the user
        
        Parameters
        ----------
        item : object
           anything with a sensible __repr__
        text : str
           anything else to include in the message

        """
        if not isinstance(item, str):
            item = repr(item)
        console_idx = int(float(self.console.index(tk.INSERT)))
        msg = "[{0}] {1} {2}\n".format(console_idx, item, text)
        self.console.see(tk.INSERT)
        idx = self.console.insert(tk.INSERT, msg)

    def _on_import(self):
        """launch tkinter file viewer to prompt for filename and location"""
        yarf_f = tkfd.askopenfilename(
            title="Import .yarf YAML file tests",
            parent=self,
            defaultextension=".yarf",
            filetypes=[("yarf", "*.yarf")],
        )

        if yarf_f != "":
            msg = "importing {0} ... ".format(yarf_f)
            self._console_log(msg)
            self.update_idletasks()

            try:
                self.model.pg._update_tr_docs_from_yaml_f(yarf_f)
            except Exception as err:
                msg = "failed"
                self.parent.dashboard._console_log(err, msg)
                raise

            self.model.pg.yarf_f = yarf_f
            self.model.update_model
            self.nametowidget(".!view")._update()
            msg = "import OK: {0}".format(yarf_f)
            self._console_log(msg)

    def _on_export(self):
        """launch tkinter file viewer to prompt for filename and location"""
        from tkinter import filedialog as tkfd

        yarf_f = tkfd.asksaveasfilename(
            title="Export tests as .yarf YAML file",
            parent=self,
            defaultextension=".yarf",
            filetypes=[("yarf", "*.yarf")],
        )

        if yarf_f != "":
            try:
                self.model.export_yarf_docs(
                    yarf_f
                )  # write *all* yarf docs, not just this dblock
            except Exception as err:
                msg = "Export .yarf failed: {0}".format(yarf_f)
                self._console_log(err, msg)

            msg = "Export .yarf OK: {0}".format(yarf_f)
            self._console_log(msg)


class PyGarvCatalogView(ttk.LabelFrame):
    """viewer/chooser for available PyGarvTest tests """

    def __init__(self, parent, *args, **kwargs):
        """
        Parameters
        ----------
        parent: widget
        top_view : Pygarv
           provides op_view.model, top_view.pg
        """

        super().__init__(parent, *args, **kwargs, height=200)
        self.config(text="Catalog")

        self.parent = parent
        self.model = parent.model
        self.catalog_tree = PyGarvTreeView(
            self,
            columns=["test", "parameter", "data type"],
            style="pygarv_style.Treeview",
            *args,
            **kwargs
        )
        self.catalog_tree.pack(expand=1, fill="both")

        # populate the tree w/ PyGarv test catalog .. one time, no need to update
        for k, v in self.model.pg.get_catalog().items():
            child = self.catalog_tree.insert("", "end", text=k, open=False)

            for p in v.params:
                # make <class 'str'> and such friendlier
                if p != "test":
                    pt = v.param_types[p]
                    if pt == str:
                        pts = "character"
                    elif pt == float or pt == int:
                        pts = "numeric"
                    else:
                        pts = str(pt)
                        # add the item
                    self.catalog_tree.insert(child, "end", values=(p, pts))

        self.pack(fill="both", expand=1)

        # self.catalog_tree.bind('<B1-Motion>', self.parent.dragging_test)
        self.catalog_tree.bind("<<TreeviewSelect>>", self._describe_selection)
        self.catalog_tree.bind("<Return>", self._add_selected_test)

    def _add_selected_test(self, e):
        """ request sibling test editor to pull a test form from the catalog """

        # maybe better done with a virtual event
        # print('catalog is requesting new test from catalog')
        self.parent.editor._pg_catalog_to_tree(e)
        # self.parent.editor.event_generate('<<NewTestFromCatalog>>')
        # root.event_generate('<<NewTestFromCatalog>>')

    def _describe_selection(self, e):
        """ Catalog selection tracks docstring from PyGarvTest.run """
        selections = self.catalog_tree.selection()
        assert len(selections) == 1
        test_iid = selections[0]

        # parameter row children describe their parent row test name
        if test_iid not in self.catalog_tree.get_children():
            test_iid = self.catalog_tree.parent(test_iid)

        # lookup the pygarv docstring
        test_name = self.catalog_tree.item(test_iid)["text"]
        pg_test = getattr(self.model.pg, test_name)
        description = pg_test.run.__doc__.split("\n")[
            0
        ]  # first line of docstring
        # self.test_doc.config(text=description)
        self.config(text="Catalog: {0}".format(description))


class PyGarvTestView(ttk.LabelFrame):
    """ viewer + parameter value editor for PyGarvTest datablock test params """

    def __init__(self, parent, *args, **kwargs):
        """
        Parameters
        ----------
        see PyGarvTreeView
        """
        super().__init__(parent, *args, **kwargs)

        self.config(text="Edit")
        self.parent = parent
        self.model = parent.model

        # always False unless _validate() succeeds
        self.is_valid = False
        self.test_tree = PyGarvTreeView(
            self,
            columns=["test", "parameter", "value"],
            style="pygarv_style.Treeview",
            *args,
            **kwargs
        )
        self.test_tree.pack(fill="both", expand=1)

        # self.bind('<<NewTestFromCatalog>>', self._pg_catalog_to_tree)

        # self.test_tree.bind('<<TreeviewSelect>>', self._select_test)
        self.test_tree.bind("<Double-Button-1>", self._dbl_click)
        self.test_tree.bind("<Delete>", self._tree_delete_test)
        self.test_tree.bind("<BackSpace>", self._tree_delete_test)

        self.event_add("<<ValidateTestTree>>", "<v>")  # FIX ME -> 'None'
        self.event_add("<<IsValidTestTree>>", "<Triple-Button>")

        self.test_tree.bind(
            "<<ValidateTestTree>>", self._validate
        )  # starts test_tree validation cycle
        self.test_tree.bind(
            "<<IsValidTestTree>>", self._on_valid_tree
        )  # ends test_tree validation cycle

        # get open Entry widgets to track Treeview window/view changes ... complete mess
        self.test_tree.bind("<Configure>", self._entry_widget_position_handler)
        self.test_tree.bind("<Motion>", self._entry_widget_position_handler)
        self.test_tree.bind("<Button-4>", self._entry_widget_position_handler)
        self.test_tree.bind("<Button-5>", self._entry_widget_position_handler)
        self.test_tree.bind(
            "<Shift-Button-4>", self._entry_widget_position_handler
        )
        self.test_tree.bind(
            "<Shift-Button-5>", self._entry_widget_position_handler
        )

        # populate with model.yarf_doc tests
        self._test_tree_from_tr_doc()
        self.pack(fill="both", expand=1)

    def _pg_catalog_to_tree(self, e):
        """key in catalog view pulls a test from pygarv catalog and
        appends to current test tree
        """

        # print('new_test_from_catalog', e)
        selection = e.widget.selection()
        assert len(selection) <= 1  # adds must be one at a time
        if len(selection) == 0:
            pass
        else:
            catalog_tree_iid = selection[0]
            test_name = e.widget.item(catalog_tree_iid)["text"]
            test_specs = getattr(self.model.pg, test_name)

            test_iid = self.test_tree.insert(
                "", "end", text=test_name, open=True
            )
            # children col 1 2 are user editable param, value
            for k, v in test_specs.items():
                if k != "test":  # in ['dblock_path', 'test']:
                    iid = self.test_tree.insert(
                        test_iid, "end", values=[k, v], open=True
                    )
            self._validate(test_iid)

        return "break"  # block event propogation

    def _tree_to_yarf_doc_test_list(self):
        """ scrapes the current test tree and returns a
        yarf_doc['tests'] format list 
        """

        # bail out if in process of patching up the form
        if not self.is_valid:
            return

        # current dblock path index
        dbp_idx = self.model.dbp_idx

        # the tree root iids, e.g., ('I001', 'I006') are the individual
        # tests this dblock
        test_tree_iids = self.test_tree.get_children()

        test_list = []
        for tt_iid in test_tree_iids:

            tt_idx = self.test_tree.index(
                tt_iid
            )  # ith root index == ith yarf_doc['tests'] test
            tt_item = self.test_tree.item(
                tt_iid
            )  # data values from the tree item
            tt_test_name = tt_item[
                "text"
            ]  # should correspond to PyGarvTest['test']

            # lookup the test
            pg_test = getattr(self.model.pg, tt_test_name)
            pg_test.reset()

            # update dblock path
            pg_test["dblock_path"] = self.model.dblock_paths[
                self.model.dbp_idx
            ]

            # scrape user settable parameter values from the test_tree
            for param_iid in self.test_tree.get_children(tt_iid):
                p, v = None, None
                (p, v) = self.test_tree.item(param_iid)["values"]

                # test tree string value to -> parameter type OK for validated data
                pg_test[p] = pg_test.param_types[p](v)

            # build the yarf_doc format ordered list of {k:v} pairs
            test_specs = [{k: pg_test[k]} for k in pg_test.params]
            test_list.append(test_specs)

            # awful
            pg_test.reset()
        return test_list

    def _on_valid_tree(self, e):
        """ actions to take when test tree values are valid"""
        # print('on_valid_tree', e)
        self.update_idletasks()  # cleanup windows
        self.nametowidget(".!view")._update()  # update everything

    def _update(self):
        """ for view._update() cascade """
        self.config(text="Edit {0}".format(self.model.dblock_path))
        self.model.update_model(self.model.dblock_path)
        self._test_tree_from_tr_doc()

    def _test_tree_from_tr_doc(self):
        """ refresh the pygarv test tree from the current yarf_docs """
        # print('test_tree._test_tree_from_tr_doc()')

        test_list = self.model.get_pg_test_list()
        # load the tree or clear if no tests
        self.test_tree.delete(*self.test_tree.get_children())
        if test_list is None or test_list == []:
            # print('no tests ... returning')
            return
        for t in test_list:
            test_params = odict()
            for kv in t:
                test_params.update(kv)
            child = self.test_tree.insert(
                "", "end", text=test_params["test"], open=True
            )
            for k, v in test_params.items():
                if k != "test":  #  ['test', 'dblock_path']:
                    # tagged read write
                    iid = self.test_tree.insert(
                        child, "end", values=(k, v), open=True, tags="rw"
                    )

    # UI ------------------------------------------------------------
    # Entry widget event handlers: note calls back to _validate()

    def _dbl_click(self, e):
        """ if pointer is double clicked on a parameter value run the value editor """

        tt_iid = self.test_tree.identify_row(e.y)  # table row has unique iid
        column = self.test_tree.identify_column(e.x)  # param #1 value #2
        # only edit read-write param values
        if column == "#2" and self.test_tree.tag_has("rw", tt_iid):
            self._edit_tt_iid_value(tt_iid)
        return "break"

    # pop up an Entry widget over the value being edited
    def _edit_tt_iid_value(self, tt_iid):
        """ pop up a ttk.Entry overlay for parameter value at tt_iid"""

        # allow only one Entry widget at a time
        ewdgts = []
        for n, wdgt in self.children.items():
            if hasattr(wdgt, "x_y_tt_iid"):
                ewdgts.append(wdgt)
        for w in ewdgts:
            warnings.warn("closing widget ...{0}".format(w))
            w.destroy()

        self.test_tree.see(tt_iid)
        test_iid = self.test_tree.parent(tt_iid)  # parent of this param

        # widgets scrolled out of view don't have a bbox, so count
        # rows and scroll test_tree to ensure test and params are
        # visible

        nrows = 0
        for root_iid in self.test_tree.get_children():
            if root_iid == test_iid:
                test_iid_row = nrows
            nrows += 1
            for child_iid in self.test_tree.get_children(root_iid):
                nrows += 1
        move_to = test_iid_row / nrows  # scroll range is 0 - 1
        self.test_tree.yview_moveto(move_to)

        self.update_idletasks()  # or else the bbox may not yet be known
        p, v = self.test_tree.item(tt_iid)["values"]
        x, y, w, h = self.test_tree.bbox(
            tt_iid, column="value"
        )  # relative to widget

        # overlay a ttk.Entry on the value being edited
        entry = ttk.Entry(self)
        entry.x_y_tt_iid = tt_iid  # Entry knows its tt_iid

        entry.place(x=x, y=y)

        # fill with existing for editing
        entry.insert(0, str(v))
        entry.select_range(0, len(str(v)))
        entry.focus()

        # wrap tree iid (= row id), e.g., 'I003B' in custom handlers
        def _data_entry_handler(e):
            # self._enter_data_iid(e, payload=payload)
            self._enter_data_iid(e, tt_iid)

        entry.bind("<Return>", _data_entry_handler)
        entry.bind("<Tab>", _data_entry_handler)
        entry.bind("<Escape>", self._abort_edit)
        entry.bind("<FocusOut>", self._abort_edit)
        self.update_idletasks()  # force display of the entry

    def _enter_data_iid(self, e, tt_iid):
        """ move contents of the Entry into the test tree, request form validation"""
        new_value = e.widget.get()
        (param, old_value) = self.test_tree.item(tt_iid)["values"]
        self.test_tree.set(tt_iid, column="value", value=new_value)
        self.update_idletasks()  # or else the tree values may not be set in time
        e.widget.destroy()

        test_iid = self.test_tree.parent(tt_iid)
        self._validate(test_iid)  # go back and check ...
        return "break"  # block event propagation

    def _abort_edit(self, e):
        """ bail of with no change to the test parameters or yarf_doc """
        e.widget.destroy()
        self.update_idletasks()
        self._test_tree_from_tr_doc()
        # self._validate()
        return "break"

    def _entry_widget_position_handler(self, e):
        """ on test tree window changes look up and relocate entry widgets """
        for n, wdgt in self.children.items():
            if hasattr(wdgt, "x_y_tt_iid"):
                self.update_idletasks()  # or else the bbox may not yet be known
                x, y, w, h = self.test_tree.bbox(
                    wdgt.x_y_tt_iid, column="value"
                )
                wdgt.place(x=x, y=y)
        self.update_idletasks()  # lest the display lags ... ??
        return "break"

    # Backspace/Del delete test handler
    def _tree_delete_test(self, e):
        """ delete the selected test from the current yarf_doc tests """
        iids = e.widget.selection()

        # tests are root children so widget.index(iid) == index in current test list
        if len(iids) == 1 and iids[0] in e.widget.get_children():
            test_name = e.widget.item(iids[0])["text"]
            test_idx = e.widget.index(iids[0])
            self.model.pg._delete_tr_docs(self.model.dbp_idx, test_idx)
            self.model.update_model(self.model.dblock_path)
            self._test_tree_from_tr_doc()
            self.test_tree.event_generate("<<IsValidTestTree>>")
            msg = "Deleted {0}".format(test_name)
            self.parent.dashboard._console_log(msg)

        return "break"

    # test tree CRUD utils ------------------------------------------------------------
    def _validate(self, test_iid):
        """check parameter values are of the correct type *AND* dry run test(s) 
        
        Parameters
        ----------
        test_iid : str
          tk.Treeview root iid of the test item to validate.


        test_tree.index(test_iid) == test_idx of updating tr_doc
        """
        # print('validating ...')

        # cleanup stray Entry widgets
        self.update_idletasks()

        # form validation False on the way in, set True on the way out if nothing
        self.is_valid = False

        # from the Model
        # current dblock path index
        dbp_idx = self.model.dbp_idx

        # current tr_doc
        tr_doc = self.model.pg.tr_docs[dbp_idx]

        # from the Treeview
        # fetch tree root ids, e.g., ('I001', 'I006')
        tt_item = self.test_tree.item(
            test_iid
        )  # data values from the tree item
        tt_test_name = tt_item[
            "text"
        ]  # should correspond to PyGarvTest['test']

        # for dblock dbp_idx, ith tree root index == ith tr_doc['tests'] test
        test_idx = self.test_tree.index(test_iid)

        # FIX ME this should not be in the validator
        # fetch a copy test_specs for to dry run. If updating fetch from tr_docs,
        # if appending start fresh w/ None from pygarv
        if test_idx < len(tr_doc["tests"]):
            # update existing specs
            test_specs = [pv for pv in tr_doc["tests"][test_idx]]
        elif test_idx == len(tr_doc["tests"]):
            # test tree has one more entry than tr_docs so we are appending
            # a new test. init test_specs w/ None's and let form validation prompt
            # for values
            test_specs = []
            for k, v in getattr(self.model.pg, tt_test_name).items():
                if k == "test":
                    test_specs.append({k: tt_test_name})
                else:
                    test_specs.append({k: v})
        else:
            # can only update existing or append one more test ...
            raise ValueError("test tree test index > len(tr_doc[" "tests" "]")

        # ------------------------------------------------------------
        # test tree form validation
        #

        # ------------------------------------------------------------
        # tt_idx = self.test_tree.index(test_iid)

        # lookup the PyGarv test and specs
        pg_test = getattr(self.model.pg, tt_test_name)  # test object

        # loop thru the param-value types and verify
        tt_param_ids = self.test_tree.get_children(
            test_iid
        )  # child ids, e.g., ('I002', 'I003')

        for tt_pid in tt_param_ids:

            # ttk.Treeview values are text fields so *strings*
            tt_p, tt_v = self.test_tree.item(tt_pid)[
                "values"
            ]  # e.g., ['stream', 'MiPa']

            pg_param_type = pg_test.param_types[
                tt_p
            ]  # e.g., <class 'str'> or <class 'float'>

            # if string cannot be coerced to correct type or 'None' force an edit Entry
            try:
                pg_param_type(tt_v)
                if tt_v == "None":
                    raise ValueError
            except Exception as err:
                # don't report errors for routine parameter entry
                if tt_v != "None":
                    self.parent.dashboard._console_log(err)
                self.is_valid = False  # block test runs until problem is fixed
                self._edit_tt_iid_value(tt_pid)
                return

            # tree value is right type so scrape it into the dry run test specs
            for i, pv in enumerate(test_specs):
                if tt_p == [*pv][0]:
                    test_specs[i] = {tt_p: pg_param_type(tt_v)}

        # ------------------------------------------------------------
        # model update ... does the test actually run?
        #
        # typos in stream labels and such can throw exceptions
        #
        # so hand off to pygarv to dry run the test and manage its
        # the tr_docs.
        #
        # the tr_doc is only updated if dry run goes thru.
        # ------------------------------------------------------------
        exception = self.model.pg._update_tr_docs(
            self.model.dbp_idx, test_idx, test_specs
        )

        if exception is not None:
            # report exception ... tr_doc manager leaves tr_doc unchanged
            msg = "_update_tr_docs failed: {0}".format(tt_test_name)
            self.parent.dashboard._console_log(exception, msg)
        else:
            msg = "update_tr_docs OK: {0}".format(tt_test_name)
            self.parent.dashboard._console_log(msg)

        # tr_docs are changed or not, either way the tree view must be current.
        self._test_tree_from_tr_doc()

        self.is_valid = True
        self.test_tree.event_generate("<<IsValidTestTree>>")
        return None

    def _update_yarf_doc(self):
        """scrapes test tree and hands the list off to Model for safe keeping"""
        test_list = self._tree_to_yarf_doc_test_list()
        self.model.set_pg_test_list(test_list)


class PyGarvTreeView(ttk.Treeview):
    """common container and styling wrapper for PyGarv catalog and dblock test views"""

    def __init__(self, parent, columns=None, *args, **kwargs):
        """
        Parameters
        ----------
        parent : tk[k].Widget
            container for this treee
        model : reference to a Model class instance
           provides current dblock_idx, dblock_path, and actual data
        pg : PyGarv class instance
           has current yarf_docs
        columns : list of str
           column headings, e.g., ['test', 'parameter', 'value'] 

        """

        # in yarf_doc ...
        # test_dict.keys() == dict_keys(['name', 'dblock_path', 'tests'])

        this_style = "pygarv_style.Treeview"
        font_name = ttk.Style().lookup(this_style, "font")
        super().__init__(
            parent, *args, **kwargs, selectmode="browse"
        )  # one selection at at time
        self.pack(fill="both")

        self.model = parent.model
        if columns is None:
            columns = ["STUB"]  # insist on a column
        self.config(columns=columns[1 : len(columns)])  # start after #0
        self.heading("#0", text=columns[0])
        self.column(
            "#0", width=tk_font.Font().measure(columns[0])
        )  # doesn't work that well
        for h in columns[1 : len(columns)]:
            self.heading(h, text=h)
            self.column(h, width=tk_font.Font().measure(h.title()))


# data I/O class interface to mkh5
class Model:
    """data model for the views 
    
    This is the Model in the mkh5viewer Model-View architecture

    `dblock_paths` and `epoch_tables` are set once upon init when the 
    `mkh5` file is read.

    The rest track datablock and index pointers, updated in response
    to UI events.

    Parameters
    ----------
    mkh5_f : string
       file path to current mkpy.mkh5 hdf5 format data file

    Attributes
    ----------
    `~mkh5.mkh5.mkh5` : object
      :py:class:`~mkpy.mkh5.mkh5` instance that exposes the hdf5 data and methods
    dblock_paths : list of str
      catalogue of all hdf5 slashpaths to mkh5 dblocks
    epoch_tables : list of str
      each string is a slash path '_epoch_tables/\*' to an mkh5 epoch table dataset

    dbp_idx : uint
       index of model's current dblock_path 

    dblock_path : string 
       slash path to the active mkpy.mkh5 data set, e.g.,
       `sub01/dblock_0` or `exp1/S07/dblock_7`.

    dblock : np.ndarray
       current dblock data streams

    header : dict
       current dblock header

    pg : PyGarv()

    pg.yarf_docs : list
       item at pg.yarf_docs[idx] is a list of tests to run on dblock at dblock_paths[idx]

    """

    def __init__(self, mkh5_f=None, tmp_yarf_f=None):

        try:
            self.mkh5_f = mkh5_f
            self.mkh5 = mkh5.mkh5(self.mkh5_f)

            self.pg = pg.PyGarv(self.mkh5_f)  # general pg init
            try:
                # FIX ME ... pg.tr_docs are already computed on pg.__init__
                # why don't they show up in the viewer without another update?
                self.pg._update_tr_docs_from_mkh5()
            except:
                msg = "uh oh ... could not read stored pygarv tests"
                raise RuntimeError(msg)

            # default list of h5 slashpaths is all dblock datasets in mkh5_f
            self.dblock_paths = self.mkh5.data_blocks

            # list (possibly empty) of h5 slashpaths to epoch table
            # datasets in mkh5_f
            self.epoch_tables = self.mkh5.get_epochs_table_names()

            self.yarf_io = pg.PyYarf()

        except Exception as fail:
            print(fail, fail.args)
            exit(-1)

        # current lookup pointers ... init to first dblock path
        if len(self.dblock_paths) == 0:
            raise ValueError(
                (
                    "found no mkh5.dblocks in "
                    "{0} ... not mkh5 format or empty?"
                    ""
                ).format(self.mkh5_f)
            )

        self.dbp_idx = 0
        self.dblock_path = self.dblock_paths[self.dbp_idx]
        self.header, self.dblock = self.mkh5.get_dblock(self.dblock_path)

        # from tempfile.NamedTemporaryFile().name
        self.tmp_yarf_f = tmp_yarf_f

        assert isinstance(self.dbp_idx, int) and self.dbp_idx >= 0
        assert isinstance(self.header, dict)
        assert isinstance(self.dblock, np.ndarray)

    def update_model(self, dblock_path):
        """ refresh index, path, and header, dblock data, and pygarv results

        Parameters
        ----------
        dbp : str
            slashpath to dblock dataset

        """
        # FIX ME sanity check the input
        assert "dblock_" in dblock_path

        # refresh the data if needed
        if self.dblock_path == dblock_path:
            # debugging
            # print('shortcut dblock update')
            pass
        else:
            # otherwise update indices and reload the buffer
            try:
                # print('updating Model.dblock_path', dblock_path)
                self.dblock_path = dblock_path
                self.dbp_idx = self.dblock_paths.index(self.dblock_path)
                self.header, self.dblock = self.mkh5.get_dblock(
                    self.dblock_path
                )
            except Exception as err:
                msg = "{0} failed on {1}".format(*err.args(), dblock_path)
                err.args = (msg,)
                raise err

        # repaint the Model dblock['pygarv'] with the current test result pygarv
        # print('repainting volatile dblock[''pygarv'']')
        self.dblock["pygarv"] = self.pg.tr_docs[self.dbp_idx]["pygarv"]

        # update the tmp
        self.export_yarf_docs(self.tmp_yarf_f)

    def export_yarf_docs(self, filename):
        """ scrape yarf doc test info from tr_docs and dump to YAML .yarf file"""

        # refresh tmp.yarf
        yarf_docs = self.pg._get_yarf_docs_from_tr_docs()
        as_yaml = self.yarf_io.to_yaml(yarf_docs)
        try:
            with open(filename, "w") as yfid:
                yfid.write(as_yaml)
        except Exception as err:
            # elaborate on the failure a bit ...
            status_msg = "{0}".format(*err.args)
            status_msg += "yarf export failed: {0}".format(status_msg)
            raise err(status_msg)

    def get_pg_test_list(self):
        """ return this dblock's tr_doc test list, e.g., for populating a UI test tree """
        return self.pg.tr_docs[self.dbp_idx]["tests"]

    def next_event(
        self, from_idx, direction, pygarv_type=None, event_col="log_evcodes"
    ):
        """return index of next or previous event in current 
            dblock model w/ pygarv type

        Parameters
        ----------
        from_idx : unint
           index in current data block to start from
        direction : int
           1 looks right, -1 looks left
        pygarv_type : str (None, 'good'  'bad')
           None (default) ignores pygarv column, 'good' searches for
           pygarv == 0, bad searches pygarv > 0
        event_col : str ('log_evcodes')
           name dblock column to search for events. usually default, 
           perhaps 'crw_evcodes'

        Returns
        -------
           index of next event satisfying the criteria or from_idx if None are found
        """
        if not (direction == 1 or direction == -1):
            raise ValueError("bad next_event direction: " + direction)

        if not pygarv_type in [None, "events", "good", "bad"]:
            raise ValueError("bad pygarv_type " + pygarv_type)

        idx = from_idx + direction
        # print('Model.next_event scanning at', idx, 'pygarv_type', pygarv_type)
        while 0 <= idx and idx < len(self.dblock):
            if self.dblock[event_col][idx] != 0:
                if pygarv_type == "good" and self.dblock["pygarv"][idx] == 0:
                    # print('found good event')
                    return idx
                elif pygarv_type == "bad" and self.dblock["pygarv"][idx] != 0:
                    # print('found bad event')
                    return idx
                elif pygarv_type == "events" or pygarv_type == None:
                    # print('found any event')
                    return idx
                else:
                    pass
            idx += direction

        # print('nothing found')
        return from_idx


# ------------------------------------------------------------
# View classes
# ------------------------------------------------------------
# class View(ttk.PanedWindow):
class View(tk.PanedWindow):
    """top_level view/controller, horizontal paned window with DataView, DashboardView

    Parameters
    ----------
    parent : tk.object
    model : mkh5viewer.Model instance  
      see Model for details

    """

    def __init__(self, parent, model, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.pack(fill="both", expand=1)
        self.model = model

        # load the views w/ data

        # DataView ... header, traces, dblock text
        self.add(DataView(self, orient="horizontal"))  # ,
        #                          model=self.model))

        # Dashboard
        self.add(Dashboard(self, orient="horizontal", heigh=200))  # ,
        #                           model=self.model))

        # position sash
        self.sash_place(0, 0, 700)

        # master call to refresh the subview
        self._update()

    def _update(self):
        """ triggers children to consult Model for possible changes with their own _update().
        This is *not* tk.update()
        """
        # print('View._update()')
        for k, v in self.children.items():
            try:
                # print('Begin View _update() child {0}: {1}'.format(k, v))
                v._update()
                # print('End View _update() child {0}: {1}'.format(k, v))
            except Exception as fail:
                warnings.warn(fail.args)


class DataView(tk.PanedWindow):
    """wrapper around pygarv editor, traces and dblock datatable """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.pack(expand=1, fill="both")
        self.model = parent.model
        self.layout_DV_widgets()

    def layout_DV_widgets(self):
        """ note: dims controlled in appearance spec globals """

        # PyGarv Frame on the left
        pygarv_frame = PyGarvView(self, text="Artifact Tests", name="pygarv")
        pygarv_frame.pack(expand=1, fill="both")

        # limit shrinkage
        self.add(pygarv_frame, minsize=50)

        # Data streams ... shows status dashboard,
        # traces canvas and dblock data table
        streams_panel = tk.PanedWindow(self, orient="vertical", name="streams")
        streams_panel.pack(expand=1, fill="both")

        streams_panel.add(TraceView(self, self.model, name="traces"))
        streams_panel.add(
            DBlockView(self, self.model, height=50, name="dblock_table")
        )
        streams_panel.sash_place(0, 0, 450)

        # bound shrinkage and set sash position
        self.add(streams_panel, minsize=150)
        self.sash_place(0, 300, 0)

        # self._update()

    def _update_streams(self):
        for k in ["traces", "dblock_table"]:
            v = self.children[k]
            v._update()

    def _update_pygarv(self):
        """ refresh pygarv test edit tree """
        self.children["pygarv"]._update()

    def _update(self):
        """ refresh traces and dblock streams """
        self._update_pygarv()
        self._update_streams()


# class Dashboard(ttk.PanedWindow): # LabelFrame):
class Dashboard(tk.PanedWindow):  # LabelFrame):
    """wrapper around HeaderView, H5Nav  """

    def __init__(self, parent, *args, **kwargs):

        self.model = parent.model
        super().__init__(parent, *args, **kwargs)
        self.pack(expand=1, fill="both")
        self.layout_dashboard_widgets()
        # self._update()

    def layout_dashboard_widgets(self):
        """ note: dims controlled in appearance spec globals """

        # headinfo in left panel
        header_view = HeaderView(self, self.model)  # , height=20)
        self.add(header_view)

        # h5 navigator w/ tabs for Data Blocks and Epochs (if any )
        h5_nav = H5Nav(self, width=300)
        h5_nav.pack(expand=1, fill="both")

        self.add(h5_nav)
        self.sash_place(0, 300, 0)

    def _update(self):
        for k, v in self.children.items():
            # print('Dashboard calling child {0}: {1}._update()'.format(k, v), end=' ')
            try:
                v._update()
            except AttributeError as fail:
                warnings.warn(fail.args)


class H5Nav(ttk.Notebook):
    """ Tab 1 (default) is dblocks, other tabs are epochs """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(
            parent, *args, style="h5nav_style.TNotebook", **kwargs
        )
        self.model = parent.model

        # always have default dblock tab
        h5_view = H5View(self, self.model, layer="dblock")
        h5_view.pack(expand=1, fill="both")
        self.add(h5_view, text="Data Blocks")

        # load up epochs tables if any
        for epoch_table in self.model.epoch_tables:
            h5_view = H5View(self, self.model, layer=epoch_table)
            h5_view.pack(expand=1, fill="both")
            self.add(h5_view, text=epoch_table)

        self.bind("<<NotebookTabChanged>>", self.update_model_dblock_paths)

    def update_model_dblock_paths(self, e):

        # h5_view = root.nametowidget(self.select())

        # fire an update cascade and set viewport to first row
        self.nametowidget(".!view")._update()
        trace_view = self.nametowidget(".!view.!dataview.traces")
        # trace_view.set_vp_from_idx(0)
        trace_view._update_vp(vp_idx=0)

    def _update(self):
        # warnings.warn('Not Implemented H5Nav._update() ')
        pass


class EventView(ttk.Frame):

    """ lightweight wrapper for regular expression event finding, same
    search mechanism as mkh5.event_table()
    """

    def __init__(self, model, *args, **kwargs):

        # layout the text entry widget
        self.model
        self.scope = "dblock"  # dataset, h5file
        self.regexp = ""
        pass

    def _find(self, dblock_path, column_name, reg_exp):
        """ wrapper around mkh5._find_evcodes() ... works per dblock"""
        pass


class H5View(ttk.Treeview):
    """ unified tabular viewer for data block (= a long epoch), events
    (a single sample epoch) and epoch tables """

    def __init__(self, parent, model, layer=None, *args, **kwargs):

        self.model = model
        self.parent = parent
        # switch on the type of data to initialize w/
        self.h5view_df = None

        if layer is "dblock":
            # for the data block view
            self.h5view_df = pd.DataFrame(
                self.model.mkh5.data_blocks, columns=["dblock_path"]
            )
            # default = single row == first sample of the datablock
            # self.h5view_df['dblock_ticks'] = 0
        else:
            # epochs table already has db_idx == match_code tick
            self.h5view_df = self.model.mkh5.get_epochs_table(layer)

        # fill the tree
        self._update_tree(self.h5view_df)

        # UI bindings
        self.bind("<<TreeviewSelect>>", self.update_model_view)
        self.pack(expand=1, fill="both")

    def _update_tree(self, df):
        """ wrapper to refresh widget with new data """

        self.h5view_df = df

        # pull the columns out of whatever table we have
        db_columns = list(self.h5view_df.columns)
        ttk.Treeview.__init__(
            self, style="h5view_style.Treeview", columns=db_columns
        )

        self.column("#0", width=0, stretch=False)
        for c in db_columns:
            self.heading(c, text=c)

        # load the tree view w/ table data
        for i, row in self.h5view_df.iterrows():
            self.insert("", "end", values=list(row))

    def update_model_view(self, e):
        """ handles clicks on H5view row.

        Each row of self.h5view_df has a dblock_path and match_ticks column.

        Selecting by mouse click or arrowing

          * update the main model to use the dblock at dblock_path 
          * move the viewport to the relevant tick
          * switch the dashboard into event scroll mode and notify
            of the new event data 
        """

        # the selected table row
        h5view_df_row = self.item(self.focus())

        # dblock paths may change arbitrarily when clicking around in
        # a tree, sofetch the selected dblock path and refresh the Model

        # slice the dblock path string and dblock tick integer the selected table row

        this_dblock_path = h5view_df_row["values"][
            self["columns"].index("dblock_path")
        ]
        self.model.update_model(this_dblock_path)

        try:
            this_dblock_idx = int(
                h5view_df_row["values"][self["columns"].index("match_tick")]
            )
        except:
            this_dblock_idx = 0

        # inform dashboard of the new anchor event
        trace_view = self.nametowidget(".!view.!dataview.traces")
        trace_view.dashboard.set_scroll_by("events")
        trace_view.dashboard.set_anchor(this_dblock_idx)

        # update the viewport and refresh
        idx_offset = trace_view.dashboard.anchor_vp_offset
        trace_view._update_vp(this_dblock_idx - idx_offset)
        self.nametowidget(".!view")._update()
        self.update_idletasks()


# class HeaderView(ttk.Treeview):
class HeaderView(ttk.LabelFrame):
    def __init__(self, parent, model, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        # for label frame
        self.config(text="Header")
        self.model = model
        self.frame_label = "Header"

        # not working?
        # self.frame_label = tk.StringVar()
        # self.frame_label.set(self.model.dblock_path)

        # actual tree view
        self.header_tree = ttk.Treeview(
            self, style="headerview_style.Treeview", *args, **kwargs
        )

        self.header_tree.heading("#0", text=self.model.dblock_path, anchor="w")
        self.header_tree.pack(expand=1, fill="both")
        self.pack(expand=1, fill="both")

    def dict_to_tree(self, d, tree_item):
        # coerce lists to dict
        if isinstance(d, list):
            d = dict([("[{0}]".format(i), v) for i, v in enumerate(d)])

        # recurse or bottom out
        for k, v in d.items():
            if isinstance(v, dict) or isinstance(v, list):
                # print('recursing on', k)
                new_item = self.header_tree.insert(
                    tree_item, "end", open=False, text=k, values=k
                )
                self.dict_to_tree(v, new_item)
            else:
                if v is None:
                    v = "None"
                item = self.header_tree.insert(
                    tree_item, "end", open=True, text="{0}:{1}".format(k, v)
                )

    def _update(self):
        # print('updating header view')
        # self.config(text=self.model.dblock_path)
        self.header_tree.heading("#0", text=self.model.dblock_path, anchor="w")

        children = self.header_tree.get_children()
        if len(children) > 0:
            for i in children:
                self.header_tree.delete(i)
        self.dict_to_tree(self.model.header, "")


class DBlockView(ttk.Treeview):
    def __init__(self, parent, model, *args, **kwargs):
        """ populate with model and info from the trace view"""
        self.parent = parent
        self.model = model
        self.traces = self.parent.children["traces"]

        self._set_vp_info()
        cols = [c for c in self.vp_ys.dtype.names]
        super().__init__(
            parent,
            columns=cols,
            selectmode="browse",
            style="dblock_table_style.Treeview",
            *args,
            **kwargs
        )

        self.column("#0", width=0, stretch=False)
        #        self.column('#0', width=tk_font.Font().measure('#0'.title()))
        for h in cols:
            self.heading(h, text=h)
            # print(h.title(), round(2.0* tk_font.Font().measure(h.title())))
            minwidth = int(2 * tk_font.Font().measure("-0000.000"))
            self.column(h, minwidth=minwidth, width=minwidth)
        self.pack(expand=1, fill="both")

        # self.bind('<ButtonRelease-1>', self.set_vp_cursor)
        self.bind("<<TreeviewSelect>>", self.set_vp_cursor)
        self.cursor_id = ""  # track cursor/selection row

    def set_vp_cursor(self, e):
        """vp cursor tracks dblock focus item, i.e., dblock row 

        Responds to DblockView cursor selection virtual events, also
        called by TraceView cursor mouse dragging

        """
        # this_selection = self.focus()
        selections = self.selection()  # should be unique in 'browse' mode
        assert len(selections) <= 1
        if len(selections) == 1:
            this_selection = selections[0]
        else:
            this_selection = ""
        # print('vp_cursor_selection', self.selection())
        if e.type.name == "VirtualEvent" and e.type.value == "35":
            # handle keyboard browsing
            if self.cursor_id == "":
                # print('turning cursor on')
                self.cursor_id = this_selection  # turn it on
            elif self.cursor_id != this_selection:
                # print('moving cursor')
                self.cursor_id = this_selection  # turn it on
                self.focus(this_selection)
            elif self.cursor_id == this_selection:
                # print('turning cursor off')
                self.selection_toggle(this_selection)
                self.focus("")
                self.cursor_id = ""
            else:
                raise ValueError(
                    (
                        "uh oh ... TreeViewSelect trouble in "
                        "DBlockView.set_vp_cursor"
                    )
                )

        # set viewport cursor sample index or None from cursor_id
        if self.cursor_id == "":
            vp_cursor_idx = None
        else:
            # first value is dblock_tick which == row index in dblock
            vp_cursor_idx = self.item(self.cursor_id)["values"][0]

        # print('vp_cursor_idx', vp_cursor_idx)
        # render the cursor on trace view
        self.parent.children["traces"].render_vp_cursor(vp_cursor_idx)

        # return 'break'

    def _set_vp_info(self):
        """ go up a frame and fetch the traces viewport """
        # viewport data from the traceview
        self.parent.children["traces"]._update_vp()
        self.vp_idx = self.parent.children["traces"].vp_idx
        self.vp_len = self.parent.children["traces"].vp_len
        self.vp_xs = self.parent.children["traces"].vp_xs
        self.vp_ys = self.parent.children["traces"].vp_ys

    def _update(self):
        """ refill tree view with dblock columns """
        # print('DBlockView._update()')

        if self.traces.dashboard.is_event_view:
            if self.traces.dashboard.anchor_event_data is not None:
                self.yview_moveto(0)
                self.yview_scroll(
                    self.traces.dashboard.anchor_vp_offset, "units"
                )

        self._set_vp_info()
        data = self.vp_ys
        if len(self.get_children()) > 0:
            self.delete(*self.get_children())
        for i in range(len(data)):
            # use row index for iid
            values = []
            for x in data[i]:
                if hasattr(x, "__index__"):
                    fmt = "{:>6d}"
                else:
                    fmt = "{:>6.1f}"
                values.append(fmt.format(x))
            # self.insert('', i, iid=str(i), values = [fmt.format(x) for x in data[i]])
            self.insert("", i, iid=str(i), values=values)
        self.update_idletasks()


# class TraceView(ttk.LabelFrame):
class TraceView(ttk.Frame):
    """trace view of data drawn on tk.Canvas wrapped in a tk.Label frame"""

    class TraceDashboard(tk.Frame):
        """ Status and UI controls for continuous vs. event/epoch scrolling

        Parameters
        ----------
        parent : 
        model : 
        """

        def __init__(self, parent, model, *args, **kwargs):
            super().__init__(parent, *args, **kwargs)

            self.parent = parent
            self.model = model

            # state variables set/reset by UI events ----------------
            self.display_units = "samples"  # vs. 0.000 seconds

            self.scroll_by_var = tk.StringVar()
            self.scroll_by_var.set("samples")  # default

            # epoch info in dblock and vp index units
            self._data = {
                "anchor": {
                    "dblock_idx": None,
                    "vp_offset": None,
                    "event_data": None,
                },
                "prestim": {"dblock_idx": None, "vp_offset": None},
                "poststim": {"dblock_idx": None, "vp_offset": None},
            }

            # ------------------------------------------------------------
            # Widgets
            # ------------------------------------------------------------

            # dblock and viewport info
            self.dash_status_label = ttk.Label(self)

            # scroll by radio button group
            self.scroll_by_label = ttk.Label(self, text="Scroll by")
            self.by_samps_rb = ttk.Radiobutton(
                self,
                text="samples",
                command=self._rb_select,
                value="samples",
                variable=self.scroll_by_var,
            )
            self.by_events_rb = ttk.Radiobutton(
                self,
                text="events",
                command=self._rb_select,
                value="events",
                variable=self.scroll_by_var,
            )
            self.by_good_rb = ttk.Radiobutton(
                self,
                text="good",
                command=self._rb_select,
                value="good",
                variable=self.scroll_by_var,
            )
            self.by_bad_rb = ttk.Radiobutton(
                self,
                text="bad",
                command=self._rb_select,
                value="bad",
                variable=self.scroll_by_var,
            )

            # epoch widgets

            # ms text labels
            self.prestim_label = ttk.Label(self, name="prestim_label")
            #            self.anchor_label = ttk.Label(self, name='anchor_label')
            self.poststim_label = ttk.Label(self, name="poststim_label")

            # epoch scale controls
            self.prestim_sc = tk.Scale(self, name="prestim")
            self.anchor_sc = tk.Scale(self, name="anchor")
            self.poststim_sc = tk.Scale(self, name="poststim")

            for sc in [self.prestim_sc, self.anchor_sc, self.poststim_sc]:
                # sc.config(command=self._update_from_scale)
                sc.config(orient="horizontal")
                sc.bind("<ButtonRelease>", self._on_release_scale)

            # init epoch to centered anchor, no pre or post stim
            # these are *durations*
            half_vp = int(self.parent.vp_len / 2)

            # self.prestim_sc.config(from_ = 0, to=half_vp)
            self.prestim_val = tk.IntVar
            self.prestim_sc.config(from_=half_vp, to=0)

            self.poststim_sc.config(from_=0, to=half_vp - 1)
            self.anchor_sc.config(from_=0, to=self.parent.vp_len - 1)

            self.anchor_sc.set(half_vp)
            self.prestim_sc.set(half_vp)
            self.poststim_sc.set(half_vp)

            # fit epoch to window
            # self._is_epoch_view = tk.IntVar()
            # self.epoch_view_cbt = ttk.Checkbutton(self, text='Fit to window',
            #                                       command = self._epoch_view,
            #                                       variable=self._is_epoch_view)

            # layout
            self.dash_status_label.grid(
                row=0, column=0, columnspan=5, sticky=tk.E + tk.W
            )
            self.scroll_by_label.grid(row=1, column=0, sticky=tk.E + tk.W)

            rb_objs = [
                self.by_samps_rb,
                self.by_events_rb,
                self.by_good_rb,
                self.by_bad_rb,
            ]
            for c, rb in enumerate(rb_objs):
                rb.grid(row=1, column=c + 1, sticky=tk.E + tk.W)

            self.prestim_label.grid(row=3, column=0, sticky=tk.N + tk.W + tk.E)
            #            self.anchor_label.grid(row=3, column=1,  sticky=tk.N+tk.W+tk.E)
            self.poststim_label.grid(
                row=3, column=2, sticky=tk.N + tk.W + tk.E
            )

            self.prestim_sc.grid(row=4, column=0, sticky=tk.N + tk.W + tk.E)
            self.anchor_sc.grid(row=4, column=1, sticky=tk.N + tk.W + tk.E)
            self.poststim_sc.grid(row=4, column=2, sticky=tk.N + tk.W + tk.E)
            # self.epoch_view_cbt.grid(row=3, column=4, sticky=tk.N+tk.W+tk.E)

        # Callbacks ----------------------------------------

        # def _epoch_view(self):
        #     ''' toggle to rescales viewport so prestim and post stim boundaries
        #     are at the edge of visible window and lock or release epoch scale widget'''

        #     if not self.is_event_view:
        #         return

        #     if self.is_epoch_view:
        #         # toggle on -> off re-enables the scale sliders
        #         self._enable_epoch_scales()
        #     else:
        #         self._disable_epoch_scales()
        #         self.parent._on_configure(None)
        #         epoch_len = (self.poststim['dblock_idx'] - self.prestim['dblock_idx']) + 1
        #         x_scale = self.parent.vp_winfo_width / epoch_len
        #         self.parent.x_scale = x_scale
        #         self.parent._update_vp(self.prestim['dblock_idx'])
        #         self.parent._update()

        # def _enable_epoch_scales(self):
        #     for scale in [self.prestim_sc, self.anchor_sc, self.poststim_sc]:
        #         scale.config(state=tk.NORMAL)

        # def _disable_epoch_scales(self):
        #     for scale in [self.prestim_sc, self.anchor_sc, self.poststim_sc]:
        #         scale.config(state=tk.DISABLED)

        # radio button group
        def _rb_select(self):
            """ reset event data and refresh """

            # FIX ME LOGIC? changing event types may or may not invalidate
            self._clear_anchor_event_data()
            self.set_anchor(self.parent.vp_idx + int(self.parent.vp_len / 2))
            self.parent._update_vp()
            self.parent._update()

        def _on_release_scale(self, e):
            """ update controls, minimodel, and traceview when a scale slider is dropped """
            name = e.widget._name
            val = e.widget.get()

            self._config_scale_limits_on_change(name, val)
            self._set_data_from_scale(name, val)
            self.parent._update()

        def _config_scale_limits_on_change(self, name, val):
            """adjust pre and poststim epoch boundary scale limits for anchor
            moves and anchor scale limits for epoch boundary scale
            moves
            """

            if name in ["prestim", "poststim"]:
                # moving a boundary so reconfigure anchor scale limits between
                # the current prestim and poststim
                self.anchor_sc.config(
                    from_=self.prestim_sc.get(),
                    to=self.parent.vp_len - self.poststim_sc.get(),
                )

            elif name in ["anchor"]:
                # moving the anchor so reconfigure boundary scale limits
                # self.prestim_sc.config(from_ = 0, to = val)
                self.prestim_sc.config(from_=val, to=0)
                self.poststim_sc.config(
                    from_=0, to=self.parent.vp_len - val - 1
                )

            else:
                raise ValueError("unknown scale label")

        def _set_data_from_scale(self, name, val):
            """update the dashboard._data{} dblock_idx and vp_offset for the scale

            Parameters
            ----------
            name : str {'anchor', 'prestim', 'poststim')
               name of the epoch scale to set
            val : uint
               viewport index


            The ._data['name'][`vp_offset`] is set from the `val`, the
            `dblock_idx` is calculated from val and the current `vp_idx`

            """
            # print('set_data_from_scale({0},{1})'.format(name, val))

            # moving a boundary scale changes the marker but not the anchor/view port
            if name == "prestim" or name == "poststim":
                self.set_anchor(self.anchor_dblock_idx)
                self.parent._update_vp()

            # moving the anchor changes the viewport but not the boundary markers
            elif name == "anchor":

                self.anchor["vp_offset"] = val  # this is read from scale
                if self.anchor_event_data is None:
                    # print('no anchor event ... not moving the viewport')
                    pass
                else:
                    # print('moving anchor event ... old vp_idx', self.parent.vp_idx, ' ', end='')
                    # move the viewport with anchor
                    event_idx = self.anchor_event_data["dblock_ticks"]
                    new_vp_idx = event_idx - self.anchor_vp_offset
                    self.parent._update_vp(vp_idx=new_vp_idx)
                    self.set_anchor(event_idx)
                    # self.anchor['dblock_idx'] = self.parent.vp_idx + val
                    # print('new vp_idx', self.parent.vp_idx)

        # backend --------------------------------------------
        def _get_dblock_idx(self, name):
            """  returns dblock_idx for named epoch param """
            return getattr(self, name)["dblock_idx"]

        def _dash_scale_to_vp_offset(self, dash_scale):
            """read the dash_scale, return *index/position* in vp samples"""
            if dash_scale == "anchor":
                # anchor scale gives *position* = vp_offset
                vp_offset = self.anchor_sc.get()
            elif dash_scale == "prestim":
                # prestim scale gives *duration*, convert to offset
                vp_offset = self.anchor_sc.get() - self.prestim_sc.get()
            elif dash_scale == "poststim":
                # prestim gives *duration*, convert to offset
                vp_offset = self.anchor_sc.get() + self.poststim_sc.get()
            else:
                raise NotImplementedError
            return vp_offset

        # public-ish API
        @property
        def is_event_view(self):
            """ boolean True if scrolling by one of the event modes"""
            if self.scroll_by_var.get() == "samples":
                return False
            else:
                return True

        # @property
        # def is_epoch_view(self):
        #     ''' boolean True if epoch view checkbutton is set '''
        #     return self._is_epoch_view.get()

        #  prestim --------------------------------------------------
        @property
        def prestim(self):
            return self._data["prestim"]

        @property
        def prestim_vp_offset(self):
            return self._data["prestim"]["vp_offset"]

        @property
        def prestim_dblock_idx(self):
            return self._get_dblock_idx("prestim")

        # poststim --------------------------------------------------
        @property
        def poststim(self):
            return self._data["poststim"]

        @property
        def poststim_vp_offset(self):
            return self._data["poststim"]["vp_offset"]

        @property
        def poststim_dblock_idx(self):
            return self._get_dblock_idx("poststim")

        # anchor ------------------------------------------------------------
        @property
        def anchor(self):
            return self._data["anchor"]  # expose as read only

        # dblock_idx for current vp data for Trace.x in TraceView
        @property
        def anchor_dblock_idx(self):
            return self._get_dblock_idx("anchor")  # self.anchor['dblock_idx']

        @property
        def anchor_vp_offset(self):
            return self.anchor["vp_offset"]

        @property
        def anchor_event_data(self):
            return self.anchor["event_data"]

        def set_anchor(self, dblock_idx):
            """ anchor at dblock index idx, update prestim and poststim from scales """
            # print('set_anchor({0})'.format(dblock_idx))
            self.anchor["dblock_idx"] = dblock_idx
            self.anchor["vp_offset"] = self.anchor_sc.get()
            self.anchor["event_data"] = self.model.dblock[dblock_idx]

            # refresh the epoch boundaries
            self.prestim["vp_offset"] = self.prestim_sc.get()
            self.prestim["dblock_idx"] = (
                self.anchor_dblock_idx - self.prestim["vp_offset"]
            )

            self.poststim["vp_offset"] = self.poststim_sc.get()
            self.poststim["dblock_idx"] = (
                self.anchor_dblock_idx + self.poststim["vp_offset"]
            )
            # print('leaving set_anchor with self_data:', self._data)

        def _clear_anchor_event_data(self):
            self.anchor["event_data"] = None

        # event finder for event and artifact browsing -----------------------
        def find_next_anchor(self, direction):
            """look left or right for next event of current pygarv type

            This calls Model.next_event() according to the dashboard
            settings.

            Parameters
            ----------
            direction: int
               -1 searches left, 1 searches right
            
            Returns
            -------
            new_vp_idx : uint
                viewport left-edge index to view the found event after
                taking the anchor offset into account.

            """

            # start search at the anchor index
            if self.anchor_dblock_idx is not None:
                idx = self.anchor_dblock_idx
            else:
                idx = self.parent.vp_idx

            scroll_by = self.get_scroll_by()

            # model.next_event returns idx if nothing found
            next_idx = self.model.next_event(
                idx, direction, pygarv_type=scroll_by
            )

            if next_idx != idx:
                # found something new, update the dash data
                self.set_anchor(next_idx)

            new_vp_idx = next_idx - self.anchor_vp_offset
            return new_vp_idx

        # scroll mode ----------------------------------------------------
        def get_scroll_by(self):
            return self.scroll_by_var.get()

        def set_scroll_by(self, scroll_by):
            if scroll_by not in ["samples", "events", "good", "bad"]:
                raise ValueError
            self.scroll_by_var.set(scroll_by)
            self._update()

        # status bar --------------------------------------------------
        def set_dash_status_text(self, units="seconds"):
            """ refresh the status report text

            Parameters
            ----------
            units : str ('samples', 'seconds')
            """

            vp_idx0, vp_len = self.parent.viewport
            vp_idx1 = vp_idx0 + vp_len - 1
            db_len = len(self.model.dblock)

            # status bar
            status_specs = []
            srate = self.model.header["samplerate"]
            for n in [vp_idx0, vp_idx1, db_len]:
                if units == "seconds":
                    val = "{0:>10.3f}".format(
                        mkh5.mkh5._samp2ms(n, srate) / 1000.0
                    )
                else:
                    val = n
                status_specs.append(val)

            text = "{0}: {1:10s} - {2:10s} of {3:10s} {4}:10s".format(
                self.model.dblock_path, *status_specs, units
            )
            text += "event:"
            if self.anchor_event_data is None:
                text += " None"
            else:
                for k in ["dblock_ticks", "crw_ticks", "log_evcodes"]:
                    text += " {0}".format(self.anchor_event_data[k])
            self.dash_status_label.config(text=text)

        def set_epoch_labels_text(self):
            """ synch epoch text labels w/ scale settings"""

            srate = self.model.header["samplerate"]
            try:
                prestim = "prestim: {0}".format(
                    mkh5.mkh5._samp2ms(self.prestim_vp_offset, srate)
                )
                #                anchor = '{0}'.format(mkh5.mkh5._samp2ms(self.anchor_vp_offset, srate))
                poststim = "poststim: {0}".format(
                    mkh5.mkh5._samp2ms(self.poststim_vp_offset, srate)
                )
            except:
                prestim = ""
                anchor = ""
                poststim = ""

            self.prestim_label.config(text=prestim)
            #            self.anchor_label.config(text=anchor)
            self.poststim_label.config(text=poststim)

        # sync dashboard view and its data for a TraceView reset and render
        def _update(self):
            """update dashboard for trace view"""
            self.set_dash_status_text()
            self.set_epoch_labels_text()

    class Trace(object):
        """ scalable x,y tk.Canvas grobs

        The x and y are the 1-1 unscaled data, stretched into canvas_pts according
        to parent.x_scale, parent.x_scale

        Parameters
        ----------
           parent : TraceView object
              Assumed to have parent.x_scale, parent.y_scale, parent.canvas

        Attributes
        ----------
           canvas_id : int (None)
              canvas item index if Trace is currently rendered, else None. 


        * Construct:

            my_line = Trace(parent_trace_view) # container only 
            my_line = Trace(parent_trace_view, x=x_data, y=ydata) # ready to render
            my_rect = Trace(parent_trace_view, x=(x0,x1), y=(y0,y1)) # ready to render
        
        * Update, optionally with new x,y data

            my_line.update() # rescale only
            my_line.update(x=x_data, y=y_data) # set x,y data and rescale

        * To render a Trace grob on a tk.canvas

            my_line.canvas_id = canvas.create_line(my_trace.canvas_pts, ...)
            my_rect.canvas_id = canvas.create_rectangle(my_trace.canvas_pts, ...)

        * To delete a Trace grob from a tk.canvas

            canvas.delete(my_trace.canvas_id)
            my_trace.canvas_id = None
        
        """

        _allowed_attrs = [
            "parent",
            "x",
            "y",
            "x_offset",
            "y_offset",
            "canvas_id",
            "label",
            "width",
            "fill",
        ]

        _trace_label_font = ("TkDefaultFont", 14, "bold")

        def __init__(
            self,
            parent,
            x=None,
            y=None,
            x_offset=0,
            y_offset=0,
            label=None,
            canvas_id=None,
            width=None,
            fill=None,
        ):

            self.parent = parent

            # print('init trace ', label)
            self.label = label
            self.width = (width,)
            self.fill = (fill,)
            self.x_offset = x_offset
            self.y_offset = y_offset

            # None or canvas item index if rendered
            self.canvas_id = canvas_id
            self.canvas_pts = [(0, 0), (0, 0)]
            self.x_scale = parent.x_scale
            self.y_scale = parent.y_scale
            self.y_border_pad = 2 * int(parent.y_offset)
            self.set_x_y(x, y)

        def set_x_y(self, x, y):
            """ store data sample x, y and convert to canvas coords """
            if x is not None and y is not None:
                self.x = x
                self.y = y
                self.x_scale = self.parent.x_scale
                self.y_scale = self.parent.y_scale

                # this version paints in an x_scaled dblock length x scrollregion
                # where the visible region tracks vp_idx * x_scale
                # canvas_x = [ int(i * self.x_scale) for i in x ]

                # this version paints in 0 to vp_len * x_scale
                # canvas_x = [ int( i * self.x_scale) for i in range(self.parent.vp_len) ]
                canvas_x = [
                    int(i * self.x_scale)
                    for i in [ii - self.parent.vp_idx for ii in x]
                ]

                # nudge all traces up by y border pad to avoid clipping first
                canvas_y = [
                    int((self.y_border_pad + self.y_offset + i) * self.y_scale)
                    for i in y
                ]
                self.canvas_pts = [pt for pt in zip(canvas_x, canvas_y)]

    class TraceHScrollbar(ttk.Scrollbar):
        """ derived scrollbar to update xview from model on set """

        def __init__(self, parent, *args, **kwargs):
            super().__init__(parent, *args, **kwargs)
            self.parent = parent

            # self.bind('<Motion>', self._on_motion)
            self.bind("<Button>", self._on_button)
            self.set()

        @property
        def position(self):
            # convert viewport indices to normalized values for slider
            dblock_len = len(self.parent.model.dblock)
            start = self.parent.vp_idx / dblock_len
            stop = start + (self.parent.vp_len / dblock_len)
            return start, stop

        def _on_motion(self, e):
            # print('X scroll bar motion', e)
            self.set()
            return "break"

        def _on_button(self, e):
            # print('X scroll bar click', e)
            click_x = self.winfo_pointerx()
            root_x = self.winfo_rootx()
            slider_x = click_x - root_x
            vp_idx = int(
                (len(self.parent.model.dblock) * self.fraction(slider_x, 0))
                - (self.parent.vp_len / 2)
            )
            # print('slider calling _update_vp(vp_idx = {0})'.format(vp_idx))
            self.parent._update_vp(vp_idx=vp_idx)
            self.parent.parent._update_streams()  # update traces and dblock
            return "break"

        def set(self):
            ttk.Scrollbar.set(self, self.position[0], self.position[1])

    def __init__(self, parent, model, *args, **kwargs):
        super().__init__(
            parent, *args, style="TraceView.TLabelframe", **kwargs
        )
        self.parent = parent
        self.model = model
        self.canvas = tk.Canvas(self, background="black")

        # ------------------------------------------------------------
        # sensible viewport defaults
        # ------------------------------------------------------------
        # these track current state of the viewport, subject to change
        # from UI events, unify w/ dashboard mini-model some day

        self.update_idletasks()
        self.vp_idx = 0
        self.vp_len = 100  # varies w/ window resizing and dblock changes
        self.vp_dblock_len = len(self.model.dblock)  # varies w/ Model.dblock
        self.vp_winfo_width = 0  # varies with window resizing and x_scale

        # self.vp_cursor_idx = None

        self.x_scale = 1.5
        self.y_scale = 0.4
        self.y_offset = 50  # to spread traces

        self.reset_vp(self.vp_idx)  # FIX ME

        # ------------------------------------------------------------
        # UI trace view controls
        # ------------------------------------------------------------
        # display state toggles
        self.event_marks_on = True

        # bind mouse actions to canvas/trace controls
        self.bind_mouse()  # all the pointer bindings
        self.bind_keys()  # all the key bindings

        dash_height = 25
        self.dashboard = self.TraceDashboard(
            self, self.model, name="traces_dash", height=dash_height
        )

        # viewport location (where in datablock)
        self.x_sb = self.TraceHScrollbar(self, orient="horizontal")
        self.x_sb.config(command=self.canvas.xview)

        # zoom time scale (x)
        self.x_scale_sc = tk.Scale(self, orient="horizontal")
        self.x_scale_sc.config(
            command=self.update_x_scale,
            showvalue=0,
            from_=0.2,
            to=10.0,
            width=10,
            bd=1,
            resolution=0.1,
        )
        self.x_scale_sc.set(self.x_scale)

        # zoom uV scale (y)
        self.y_scale_sc = tk.Scale(self, orient="vertical")
        self.y_scale_sc.config(
            command=self.update_y_scale,
            showvalue=0,
            from_=0.05,
            to=2.5,
            width=10,
            bd=1,
            resolution=0.025,
        )
        self.y_scale_sc.set(self.y_scale)

        # y spacing
        self.y_offset_sc = tk.Scale(self, orient="vertical")
        self.y_offset_sc.config(
            command=self.update_y_offset,
            showvalue=0,
            from_=20,
            to=200.0,
            width=10,
            bd=1,
            resolution=1,
        )
        self.y_offset_sc.set(self.y_offset)

        # vertical view (y = chan)
        self.y_sb = tk.Scrollbar(self, orient="vertical")
        self.y_sb.config(command=self.canvas.yview)

        # native vertical scrolling only ... x_sb bindings
        # drive horizontal scrolling through _update_vp()
        self.canvas.config(yscrollcommand=self.y_sb.set)

        # ------------------------------------------------------------
        # layout
        # ------------------------------------------------------------
        self.dashboard.pack(fill="x", side="top")

        self.x_scale_sc.pack(fill="x", side="bottom")
        self.x_sb.pack(fill="x", side="bottom")

        self.y_offset_sc.pack(fill="y", side="left")
        self.y_scale_sc.pack(fill="y", side="left")
        self.y_sb.pack(fill="y", side="right")

        # trace view canvas
        self.canvas.pack(fill="both", expand=1, side="top")
        self.pack(expand=1, fill="both", side="top")

        # update scrollregion on window resize
        # <CONFIGURE> useful event ... triggered on window resizing
        # self.bind('<Configure>', self.reset_scrollregion )
        self.bind("<Configure>", self._on_configure)

        # initialze viewed data
        self.init_vp_cursor()  # FIX ME ... inits should be separate from reset

    def _on_configure(self, e):
        # update viewport on window resize
        if self.vp_winfo_width != self.winfo_width():
            self._update_vp()
            self.parent._update_streams()

    def _update_vp(self, vp_idx=None, x_scale=None):
        """sets the TraceView viewport data 

        The viewport length in samples is derived from the canvas
        visible fraction of the total scrollable canvas width:
        len(dblock) * x_scale

        """

        # check for any change of state that requires a new vp_len calculation
        vp_len_is_stale = False  # assume we're OK

        # Model dblock changed
        if self.vp_dblock_len != len(self.model.dblock):
            self.vp_dblock_len = len(self.model.dblock)
            vp_len_is_stale = True

        # TraceView x_scale changed
        if x_scale is not None and x_scale != self.x_scale:
            self.x_scale = x_scale
            # print('update_vp new x_scale: ', self.x_scale)
            vp_len_is_stale = True

        # Parent frame resized
        if self.vp_winfo_width != self.winfo_width():
            # print('update_vp new vp_winfo_width {0}'.format(self.winfo_width()))
            self.vp_winfo_width = self.winfo_width()
            vp_len_is_stale = True

        # update the vp_len if needed
        if vp_len_is_stale:
            scrollregion_width, scrollregion_height = self.reset_scrollregion()

            # calc visible portion of the canvas as width minus the 3 y scrollbars ... ugh
            y_ctrls_width = 0
            for y_ctrl in [
                self.y_sb,
                self.y_scale_sc,
                self.y_offset_sc,
            ]:  # hard coded hack
                y_ctrls_width += y_ctrl.winfo_width() + 2 * int(
                    y_ctrl.cget("borderwidth")
                )  # 2 borders

            # pixels between the scroll bars
            visible_canvas_px = self.vp_winfo_width - y_ctrls_width

            # new vp_len
            # new_vp_len = max(0,int( (visible_canvas_px / scrollregion_width) * (len(self.model.dblock))) - 1)
            new_vp_len = max(0, int(visible_canvas_px / self.x_scale))
            # print('update_vp ... stale vp_len {0}, recalculating {1}'.format(self.vp_len, new_vp_len))
            self.vp_len = new_vp_len

        # with current vp_len in hand, handle vp_idx

        # update self.vp_idx if one is passed in, else to current vp_idx
        if vp_idx is None:
            # use current vp_idx
            vp_idx = self.vp_idx
        else:
            # prevent scrolling past the data
            # print('new vp_idx {0}'.format(self.vp_idx))
            self.vp_idx = max(
                0, min(vp_idx, len(self.model.dblock) - self.vp_len)
            )

        # set xs all the way to end of vp
        self.vp_xs = [self.vp_idx + ii for ii in range(self.vp_len)]
        self.vp_ys = self.model.dblock[self.vp_xs]

    def _update(self):

        """rebuild and render traces and data block table according to current viewport

        reset_X() instructs view X to consult the data, rebuild the
        (abstract) grobs, and render them.

        """
        # print('Begin TraceView._update()')
        # self.canvas.xview_moveto(self.vp_idx / (len(self.model.dblock)-1) )
        self.x_sb.set()  # trace view scrollbar position via vp_idx, vp_len

        self.reset_traces()  # always reset and render traces
        self.render_vp_cursor()  #

        self.reset_trace_dashboard()  #
        self.reset_event_marks()
        self.reset_pygarv()  # always reset and render artifacts

        # self.parent.children['dblock_table']._update()
        self.reset_vernier()
        # print('End TraceView._update()')
        self.update_idletasks()

    def update_x_scale(self, e):
        """ handle time zoom """
        self._update_vp(vp_idx=self.vp_idx, x_scale=float(e))
        self.parent._update_streams()

    def update_y_scale(self, e):
        """ handle uV zoom """
        self.y_scale = float(e)
        self.reset_scrollregion()
        self._update()

    def update_y_offset(self, e):
        """ handle trace vertical spacing """
        self.y_offset = float(e)
        self.reset_scrollregion()
        self._update()

    def bind_keys(self):
        """ bindings"""
        self.canvas.bind("<e>", self.toggle_event_marks)  # on/off

        self.canvas.bind("<Left>", self._trace_xview_scroll)
        self.canvas.bind("<Right>", self._trace_xview_scroll)
        self.canvas.bind("<Shift-Left>", self._trace_xview_scroll)
        self.canvas.bind("<Shift-Right>", self._trace_xview_scroll)

        self.canvas.bind(
            "<Up>", lambda e: self.canvas.yview_scroll(-1, "units")
        )
        self.canvas.bind(
            "<Down>", lambda e: self.canvas.yview_scroll(1, "units")
        )
        self.canvas.bind(
            "<Shift-Up>", lambda e: self.canvas.yview_scroll(-1, "page")
        )
        self.canvas.bind(
            "<Shift-Down>", lambda e: self.canvas.yview_scroll(1, "page")
        )

    def _trace_xview_scroll(self, e):

        event = dict(re.findall("(\w+)=(\w+)", str(e)))
        direction, step = 1, 0

        if "keysym" in event.keys():
            # fixed direction and step each key press
            if event["keysym"] == "Right":
                direction = 1
            elif event["keysym"] == "Left":
                direction = -1
            else:
                # debugging
                # print(repr(e) + 'unknown keysym' + event['keysym'])
                pass

            # scrolling by samples
            if "state" not in event.keys():
                step = int(0.1 * self.vp_len)
            elif event["state"] == "Shift":
                step = int(0.4 * self.vp_len)
            else:
                # debugging
                # print(repr(e) + 'unknown keysym' + event['keysym'])
                pass

        elif "num" in event.keys():
            # disable mousewheel FIX ME
            return "break"

            # fixed direction variable step on mousewheel
            # print(e, event)
            num = int(event["num"])
            if num == 5:
                direction = 1
            elif num == 4:
                direction = -1
            else:
                # debugging
                # print(repr(e) + 'unknown num ' + num)
                pass
            step = int(np.round(self.vp_winfo_width / self.vp_len))
        else:
            # debugging
            # print('_trace_xview_scroll unknown event', event)
            pass

        # work out vp_idx
        is_event_view = self.dashboard.is_event_view
        if is_event_view:
            # print('trace_xview_scroll epoch event_view')
            vp_idx = self.dashboard.find_next_anchor(direction)
        else:
            vp_idx = self.vp_idx + (direction * step)
        self._update_vp(vp_idx=vp_idx)
        self.parent._update_streams()  # parent in order to propagate to dblock view
        return "break"

    # move me ------------------------------------------------------------
    def toggle_event_marks(self, e):
        assert self.event_marks_on is not None
        if self.event_marks_on is False:
            # print('event marks on')
            self.event_marks_on = True
        else:
            # print('event marks off')
            self.event_marks_on = False
        self._update()

    def canvas_get_focus(self, e):
        self.canvas.focus_set()

    def render_vernier(self, e):
        self.render_vernier()

    # move me ------------------------------------------------------------

    def bind_mouse(self):
        """ mouse bindings"""

        self.canvas.bind("<Enter>", self.canvas_get_focus)

        # self.canvas.bind('<Leave>', canvas_release_focus)
        # if needed ...
        # self.canvas.bind('<B1-Motion>', self.b1_drag)
        # self.canvas.bind('<B2-Motion>', self.b2_drag)
        # self.canvas.bind('<B3-Motion>', self.b3_drag)

        # these move cursor ...
        self.canvas.bind("<Shift-Motion>", self.drag_vp_cursor)
        self.canvas.bind("<Shift-Button-1>", self.drag_vp_cursor)

        self.canvas.bind("<Button-1>", self.render_vernier)
        self.canvas.bind("<ButtonRelease-1>", self.render_vernier)
        self.canvas.bind("<B1-Motion>", self.render_vernier)

        # these linux mousewheel trigger x-scroll arrow clicks to move
        # Windows has different mousewheel events
        # self.canvas.bind('<Shift-Button-4>', self.x_scroll_arrow)
        # self.canvas.bind('<Shift-Button-5>', self.x_scroll_arrow)
        # self.canvas.bind('<Button-4>', self.y_scroll_arrow) #
        # self.canvas.bind('<Button-5>', self.y_scroll_arrow) #

        # scroll canvas left-right
        # self.canvas.bind('<Shift-Button-4>', self.canvas_mouse_wheel)
        # self.canvas.bind('<Shift-Button-5>', self.canvas_mouse_wheel)
        self.canvas.bind("<Shift-Button-4>", self._trace_xview_scroll)
        self.canvas.bind("<Shift-Button-5>", self._trace_xview_scroll)

        # scroll canvas up-down
        self.canvas.bind("<Button-4>", self.canvas_mouse_wheel)
        self.canvas.bind("<Button-5>", self.canvas_mouse_wheel)

    # ------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------
    def canvas_mouse_wheel(self, e):

        # mousewheel
        if e.state == 0:
            if e.num == 4:
                self.canvas.yview("scroll", -1, "units")  # up
            elif e.num == 5:
                self.canvas.yview("scroll", 1, "units")  # down

        # shift-mousewheel
        elif e.state == 1:
            if e.num == 4:
                self.canvas.xview("scroll", -1, "units")  # right
            elif e.num == 5:
                self.canvas.xview("scroll", 1, "units")  # left

    def drag_vp_cursor(self, e):
        """dragging mouse over moves viewport cursor and dblock selection

        This modifies dblock view selection to drive the cursor,
        indirect but synchronizes dblock selection and cursor
        """
        x = min(max(0, e.x), self.vp_len * self.x_scale)
        vp_cursor_idx = max(0, int(np.floor(x / self.x_scale)))

        # this sets selection in dblock view which highlights
        # selected row and triggers trace view cursor rendering
        dblock_view = self.master.children["dblock_table"]
        dblock_view.cursor_id = ""
        dblock_view.focus(str(vp_cursor_idx))
        dblock_view.selection_set(str(vp_cursor_idx))

        # place cursor row at top of dblock window, ... 0.5
        # adjusts for rounding
        y_view = min(1.0, (vp_cursor_idx - 0.5) / (self.vp_len))
        # print('dragging:', 'x:', x, 'vp_cursor_idx:', vp_cursor_idx, 'dblock yview:', y_view)
        dblock_view.yview_moveto(y_view)
        self.vp_cursor_idx = vp_cursor_idx

    def b1_drag(self, e):
        """ stub """
        # print('b1 dragging', e)
        pass

    def b2_drag(self, e):
        """ stub """
        # print('b2 dragging', e)
        pass

    def b3_drag(self, e):
        """ stub """
        # print('b3 dragging', e)
        pass

    def mouse_wheel(self, e):
        """ handle mouse wheel """
        # print('mouse wheeling', e)
        x_start = e.x
        y_start = e.y

    def reset_vp(self, vp_idx):  # , vp_len):
        """set the TraceView viewport index and data slices of the current model.dblock

        Parameters
        ----------
        vp_idx : int
           dblock index (samples) of left edge of TraceView viewport 

        viewport start index values may come from keyboard/mouse TraceView navigation or 
        be derived from epoch data lookup during table navigation 

        The viewport length in samples is derived from the canvas
        scrollregion fraction of the canvas width (== len(dblock) \* x_scale)
        """

        # print('resetting_vp() vp_idx={0}'.format(vp_idx))
        self.vp_idx = vp_idx

        # set xs all the way to end of vp
        self.vp_xs = [self.vp_idx + ii for ii in range(self.vp_len + 1)]
        self.vp_ys = self.model.dblock[self.vp_xs]

    def reset_scrollregion(self, *args):
        """ change the canvas scrollregion on zoom params or window changes
        y scrollregion always needs to include all traces. 
        x scrollregion is canvas width ... _update_vp() sets vp_len data points
        """

        # scrollregion_width = int( self.x_scale * (len(self.model.dblock)-1) )

        # FIX ME ... see y_border_pad
        # add + 2 for first and last trace head room
        if hasattr(self, "traces"):
            traces_height = (
                (len(self.traces) + 2) * self.y_offset * self.y_scale
            )
        else:
            traces_height = 0

        # don't shrink y scroll region smaller than trace view height
        if hasattr(self, "y_sb"):
            y_sb_height = self.y_sb.winfo_height()
        else:
            y_sb_height = 0

        scrollregion_width = self.canvas.winfo_width()
        # print('reset_scrollregion()', scrollregion_width)

        scrollregion_height = int(max(y_sb_height, traces_height))
        self.canvas.config(
            scrollregion=(0, 0, scrollregion_width, scrollregion_height)
        )
        return (scrollregion_width, scrollregion_height)

    @property
    def viewport(self):
        return self.vp_idx, self.vp_len

    # ------------------------------------------------------------
    # grob object layers: traces, garv, cursor
    #
    # reset_X:   refresh grob data for rendering
    # render_X : paint the glyph on self.canvas
    #
    # ------------------------------------------------------------
    def reset_trace_dashboard(self):
        """ pull info from the trace dashboard view controls and render


        - anchor marker
        """
        self.dashboard._update()  # sync trace dashboard widgets/data

        # build grobs ...
        # x,y,w,h = [int(px) for px in self.canvas.cget('scrollregion').split()]

        y_min = 0
        assert hasattr(self, "traces")
        y_max = len(self.traces) * self.y_offset

        self.trace_dashboard_grobs = []

        anchor_idx = self.dashboard.anchor_dblock_idx
        if anchor_idx is not None:
            self.trace_dashboard_grobs.append(
                self.Trace(
                    self,
                    x=[anchor_idx] * 2,
                    y=[y_min, y_max],
                    label="anchor",
                    fill="cyan",
                    width=2.0,
                )
            )

        prestim_idx = self.dashboard.prestim_dblock_idx
        # print('vp_idx', self.vp_idx)
        # print('dashboard._data', self.dashboard._data)
        # print('rendering prestim grob at', prestim_idx)
        if prestim_idx is not None:
            self.trace_dashboard_grobs.append(
                self.Trace(
                    self,
                    x=[prestim_idx] * 2,
                    y=[y_min, y_max],
                    label="prestim",
                    fill="yellow",
                    width=4.0,
                )
            )

        poststim_idx = self.dashboard.poststim_dblock_idx
        # print('rendering poststim grob at', poststim_idx)
        if poststim_idx is not None:
            self.trace_dashboard_grobs.append(
                self.Trace(
                    self,
                    x=[poststim_idx] * 2,
                    y=[y_min, y_max],
                    label="poststim",
                    fill="orange",
                    width=4.0,
                )
            )

        self.render_trace_dashboard()

    def render_trace_dashboard(self):
        """ render or hide the trace dashboard view grobs"""

        # clean up previous if any ...
        if (
            hasattr(self.canvas, "dash_grob_ids")
            and self.canvas.dash_grob_ids is not None
        ):
            for dgid in self.canvas.dash_grob_ids:
                self.canvas.delete(dgid)
            self.canvas.dash_grob_ids is None

        # render new if scrolling by events
        if self.dashboard.is_event_view:
            self.canvas.dash_grob_ids = []
            for grob in self.trace_dashboard_grobs:
                # print('canvas.create dash grob', repr(grob), grob.canvas_pts)
                grob_id = self.canvas.create_line(
                    grob.canvas_pts, fill=grob.fill, width=grob.width
                )
                self.canvas.dash_grob_ids.append(grob_id)

    # EEG trace grobs
    def reset_traces(self):
        # combination init + reset ... slow but simple
        # build minimal Trace containers for current model dblock
        trace_stream_labels = [
            s["name"]
            for s in self.model.header["streams"].values()
            if "dig_chan" in s["source"]
        ]

        self.traces = np.ndarray(shape=(len(trace_stream_labels),), dtype="O")

        colors = ["magenta", "yellow"]

        at, n_samples, = self.viewport
        # print('setting traces', at, n_samples)
        for i, t in enumerate(trace_stream_labels):
            self.traces[i] = self.Trace(
                self,
                x=self.vp_xs,
                y=self.vp_ys[t],
                label=t,
                y_offset=i * self.y_offset,
                fill=colors[i % 2],
                width=1.0,
            )
        self.render_traces()

    def render_traces(self):
        """ fetch viewport info from model and render """

        # clear traces in view port and redraw
        at, n_samples, = self.viewport
        self.canvas.delete("all")
        if n_samples == 0:
            return
        for i, t in enumerate(self.traces):
            try:
                t.canvas_id = self.canvas.create_line(t.canvas_pts)
            except Exception as err:
                pass

            # configure trace attributes
            self.canvas.itemconfig(
                t.canvas_id,
                tag=t.label,
                fill=t.fill,
                width=t.width,
                activewidth=2,
            )

            label_nudge = 10  # pts
            if len(t.canvas_pts) > label_nudge:
                self.canvas.create_text(
                    t.canvas_pts[10][0] + 10,
                    t.canvas_pts[10][1],
                    text=t.label,
                    fill=t.fill,
                    anchor="sw",
                    font=t._trace_label_font,
                )

            # bind individual trace call backs here if any
            # self.canvas.tag_bind(t.canvas_id, ... )
        self.update_idletasks()  # makes display a bit more responsive

    # vernier grob
    def reset_vernier(self):
        # note: vp_idx build in during Trace.__init__
        x_ticks = [x * 100 for x in range(-5, 6)]
        y_cal = 10

        self.vernier = self.Trace(
            self,
            x=(5, 0, 0, 0, 0, 50),
            y=(-y_cal, -y_cal, -y_cal, 0, 0, 0),
            fill="white",
            width=1.0,
        )

    def render_vernier(self, e):
        # Note ... tried state='normal' vs 'hidden', no bbox?
        # self.vernier.set_x_y(self.vernier.x, self.vernier.y)
        vernier_x = min(max(0, e.x), self.vp_len * self.x_scale)
        vernier_pts = [
            (
                pt[0] + (self.vp_idx * self.x_scale) + vernier_x,
                pt[1]
                + self.canvas.canvasy(e.y)
                - (self.y_scale * self.vernier.y_border_pad),
            )
            for pt in self.vernier.canvas_pts
        ]

        # print('vernier_pts', vernier_pts)

        if str(e.type) == "ButtonPress":
            self.vernier_item = self.canvas.create_line(
                vernier_pts,
                fill=self.vernier.fill,
                width=self.vernier.width,
                state="normal",
            )
        elif str(e.type) == "Motion":
            self.canvas.delete(self.vernier_item)
            self.vernier_item = self.canvas.create_line(
                vernier_pts,
                fill=self.vernier.fill,
                width=self.vernier.width,
                state="normal",
            )
        elif str(e.type) == "ButtonRelease":
            # print('vernier off')
            self.canvas.delete(self.vernier_item)
        else:
            warnings.warn("uh oh ... trouble with vernier", str(e.type))

    # Event grobs
    def reset_event_marks(self):

        """ called when viewport changes """
        ev_idxs = np.where(self.model.dblock["log_evcodes"] > 0)[
            0
        ]  # event , this dblock
        ev_idxs = [
            ev_idx
            for ev_idx in ev_idxs
            if self.vp_idx <= ev_idx and ev_idx < (self.vp_idx + self.vp_len)
        ]
        self.event_marks = []
        for ev_idx in ev_idxs:
            ev_mark_trace = self.Trace(
                self,
                label=str(self.model.dblock["log_evcodes"][ev_idx]),
                x=((ev_idx),) * 2,
                y=(0, len(self.traces) * self.y_offset),
            )  # span the traces
            # ev_mark_trace.set_x_y(x=ev_mark_trace.x, y=ev_mark_trace.y)
            self.event_marks.append(ev_mark_trace)
        self.render_event_marks()

    def render_event_marks(self):

        # skip if not viewing events
        if not self.event_marks_on:
            return

        at, n_samples, = self.viewport
        for ev_mark in self.event_marks:
            ev_mark.canvas_id = self.canvas.create_line(ev_mark.canvas_pts)
            self.canvas.itemconfig(
                ev_mark.canvas_id, tag=ev_mark.label, fill="gray", width=1.0
            )

            self.canvas.create_text(
                ev_mark.canvas_pts[0][0],
                ev_mark.canvas_pts[0][1],
                text=ev_mark.label,
                fill="gray",
                anchor="s",
            )

    # pygarv artifact grobs
    def reset_pygarv(self):
        """ called when dblock or PyGarv.tr_docs test changes """

        # for readability ... a better way?
        # pg = self.nametowidget('.!view.!dataview.pygarv').pg
        # pg = self.master.model.pg
        pg = self.model.pg

        # nothing to see
        if (
            pg.tr_docs[self.model.dbp_idx] == []
            or pg.tr_docs[self.model.dbp_idx] is None
        ):
            raise ValueError(
                "pygarv bug: no tr_docs for {0}".format(self.model.dblock_path)
            )

        assert self.vp_len >= 0
        assert self.traces is not None

        # for readability
        dbp_idx = self.model.dbp_idx
        tr_doc = self.model.pg.tr_docs[dbp_idx]

        # spot check tr_doc dblocks and fails==pygarv > 0
        assert tr_doc["dblock_path"] == self.model.dblock_paths[dbp_idx]

        if (
            all(tr_doc["pygarv"] == 0)
            and any(len(fail) > 0 for fail in tr_doc["fails"])
        ) or (
            any(tr_doc["pygarv"] != 0)
            and all(len(fail) == 0 for fail in tr_doc["fails"])
        ):
            msg = "tr_docs[{0}] fails and pygarv do not agree".format(dbp_idx)
            raise ValueError(msg)

        # no fails to render, go home
        if len(tr_doc["fails"]) == 0:
            return

        self.pygarvs = []  # container for pygarv traces, if any
        fails = []  # accumulate info on fails in this viewport
        for i, test_fails in enumerate(tr_doc["fails"]):
            # test_fails may be empty ...
            for (x0, x1) in test_fails:
                # collect fail intervals that intersect this viewport
                if x1 < self.vp_idx or x0 > self.vp_idx + self.vp_len - 1:
                    continue
                # truncate fail to this viewport
                x0 = max(self.vp_idx, x0)
                x1 = min(x1, self.vp_idx + self.vp_len - 1)
                this_fail = dict(x0=x0, x1=x1, test_idx=i)
                # print(this_fail)
                fails.append(this_fail)
                # print(len(fails))
        # print('n fails: ', len(fails))

        # reverse index the stream labels
        trace_idxs = odict([(t.label, i) for i, t in enumerate(self.traces)])

        # unnpack the fail tests and regions
        # self.pygarvs = np.ndarray(shape=(len(fails),), dtype='O')
        for i, fail in enumerate(fails):

            # fetch the test params
            this_test = odict()
            for i in tr_doc["tests"][fail["test_idx"]]:
                this_test.update(i)

            # look up the streams to mark as bad, if None mark all
            streams = [v for k, v in this_test.items() if "stream" in k]

            # regex patterns, literals 'MiPa' or with wildcards 'Mi..' or '..Pf'
            stream_patts = [v for k, v in this_test.items() if "stream" in k]

            # list of trace labels that match test stream regexp
            streams = [
                s.label
                for stream_patt in stream_patts
                for s in self.traces
                if re.match(stream_patt, s.label)
            ]

            # fall back to all channels
            # if len(streams) == 0:
            #    streams = [s.label for s in self.traces]
            if len(streams) == 0:
                msg = "no streams found in this pygarv test, yell at urbach: "
                msg += "{0}".format(this_test)
                raise ValueError(msg)

            # calculate artifact boundaries and build
            # pygarv trace snippets to overplot the traces
            for ii, s in enumerate(streams):

                # x slicer
                vp_slice = slice(
                    fail["x0"] - self.vp_idx, fail["x1"] - self.vp_idx + 1
                )

                # y index into traces by stream label ... scary
                trace_idx = trace_idxs[s]

                xs = self.traces[ii].x[vp_slice]
                ys = self.traces[trace_idx].y[vp_slice]  # brittle

                # debugging
                if len(xs) == 0:
                    warnings.warn("pygarv xs len == 0")

                # turn single point artifacts into short vertical line segments
                # line segments
                if len(xs) == 1:
                    xs = (xs[0], xs[0])

                    # scale segment w/ y
                    seg_prop = 0.5
                    ys = (
                        ys[0] + (self.y_offset * seg_prop),
                        ys[0] - (self.y_offset * seg_prop),
                    )

                this_garv = self.Trace(
                    self,
                    label="pygarv",
                    x=xs,
                    y=ys,
                    y_offset=trace_idx * self.y_offset,
                    fill="red",
                    width=1.0,
                )
                this_garv.set_x_y(xs, ys)
                self.pygarvs.append(this_garv)
        self.render_pygarv()

    def render_pygarv(self):
        at, n_samples = self.viewport

        # clean up previous
        # clear_these = [garv_trace for garv_trace in self.pygarvs \
        #                if garv_trace.canvas_id is not None]
        # for garv_trace in clear_these:
        #     self.canvas.delete(garv_trace.canvas_id)

        # left edge of garv trace is self.vp_idx
        # right edge of garv trace is self.vp_idx + self.vp_len
        for i, p in enumerate(self.pygarvs):
            # if len(p.x) == 1:
            #     msg = ('Fixing single sample artifacts: self.vp_idx: '
            #            '{0} self.vp_len {1}').format(self.vp_idx,
            #                                         self.vp_len)
            #     warnings.warn(msg)
            # else:
            #     try:
            #         p.canvas_id = self.canvas.create_line(p.canvas_pts)
            #     except:
            #         pdb.set_trace()

            p.canvas_id = self.canvas.create_line(p.canvas_pts)
            self.canvas.itemconfig(
                p.canvas_id, tag=p.label, fill="red", width=3
            )

    # cursor grob
    def init_vp_cursor(self):
        self.vp_cursor = self.Trace(self, label="cursor")

    def render_vp_cursor(self, vp_cursor_idx=None):

        self.vp_cursor_idx = vp_cursor_idx

        # clear cursor grob, if any
        if self.vp_cursor.canvas_id is not None:
            self.canvas.delete(self.vp_cursor.canvas_id)

        # redraw if new or moved
        if vp_cursor_idx is not None:
            # clear current if rendered
            xs = ((self.vp_cursor_idx),) * 2
            # atrocious hack to compensate for Trace auto yscale
            ys = (0, len(self.traces) * self.y_offset)  # span the traces
            self.vp_cursor.set_x_y(xs, ys)
            self.vp_cursor.canvas_id = self.canvas.create_line(
                self.vp_cursor.canvas_pts, fill="white"
            )


class Application(ttk.Frame):
    """top level viewer frame"""

    def __init__(self, parent=None, mkh5_f=None, tmp_yarf_f=None):
        super().__init__(parent)
        self.pack(expand=1, side="top", fill="both")
        self.model = Model(mkh5_f=mkh5_f, tmp_yarf_f=tmp_yarf_f)

        # FIX ME ...
        self.view = View(parent, self.model, orient="vertical", width=1000)
        parent.title(self.view.model.mkh5_f)


def launch_app(mkh5_f):
    root = tk.Tk()
    tmp_yarf = tempfile.NamedTemporaryFile(prefix=mkh5_f + ".yarf.")
    app = Application(parent=root, mkh5_f=mkh5_f, tmp_yarf_f=tmp_yarf.name)
    set_styles()
    app.mainloop()
    tmp_yarf.close()


if __name__ == "__main__":
    launch_app(sys.argv[1])
