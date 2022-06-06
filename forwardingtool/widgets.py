"""Widgets for the forwarding tool"""

from __future__ import annotations

import dataclasses
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
from typing import List, Tuple, Any, Dict, Generic, TypeVar, Optional
from dataclasses import asdict
from functools import partial
from itertools import count
import webbrowser

from forwardingtool.config import Config, ForwardedPort
from forwardingtool import inputs
from forwardingtool import views


class ButtonBox(ttk.Frame):
    @staticmethod
    def slugify(value: str) -> str:
        return '_'.join(value.lower().split())

    def __init__(self, master, labels: List[str], buttonargs: Dict[str, Any] = None):
        super().__init__(master)
        buttonargs = buttonargs or {}
        self.buttons = {
            self.slugify(label): ttk.Button(self, text=label,
                                            command=getattr(self.master, 'on_' + self.slugify(label), None),
                                            **buttonargs) for label in labels}
        for column, (label, button) in enumerate(self.buttons.items(), start=1):
            button.grid(row=0, column=column)
        self.grid_columnconfigure(0, weight=1)

    def grid(self, sticky='ew', *args, **kwargs):
        super().grid(sticky=sticky, *args, **kwargs)


DC = TypeVar('DC')


class BaseView(ttk.Frame, Generic[DC]):
    """Base implementation for an input view based on a dataclass model"""
    MODEL: dataclasses.dataclass
    FIELDSPEC: Dict[str, Tuple[str, Any]] = {}

    def __init__(self, master):
        super().__init__(master)

        self.widgets: Dict[str, Any] = {}
        for row, (name, (label, wtype)) in enumerate(self.FIELDSPEC.items()):
            ttk.Label(self, text=label + ':').grid(row=row, column=0, sticky='e')
            widget = wtype(self)
            widget.grid(row=row, column=1, sticky='nesw')
            self.widgets[name] = widget
        list(self.widgets.values())[0].focus_set()

    def get_errors(self) -> List[Tuple[str, Any]]:
        errors: List[Tuple[str, Any]] = []
        for widget in self.widgets.values():
            widget.trigger_focusout_validation()
            if widget.error.get():
                errors.append((widget.error.get(), widget))
        return errors

    def get(self) -> DC:
        return self.MODEL(**{k: w.get() for k, w in self.widgets.items()})

    def set(self, value: DC):
        data: Dict[str, Any] = asdict(value)
        for name, widget in self.widgets.items():
            widget.set(data[name])


class AddForwardView(BaseView[ForwardedPort]):
    """View for SSH settings"""

    MODEL: dataclasses.dataclass = ForwardedPort
    FIELDSPEC: Dict[str, Tuple[str, Any]] = {
        'label': ('Label', inputs.StringInput),
        'local_port': ('Local Port', inputs.PortInput),
        'hostname': ('Hostname', inputs.HostnameInput),
        'remote_port': ('Remote Port', inputs.PortSelectorInput),
    }


class ConnectionSetupView(BaseView[Config]):
    """View for SSH settings"""

    MODEL: dataclasses.dataclass = Config
    FIELDSPEC: Dict[str, Tuple[str, Any]] = {
        'jump_host': ('Jump Host', inputs.HostnameInput),
        'username': ('Username', inputs.UsernameInput),
        'jump_port': ('Port', inputs.PortInput),
        'pubkey': ('Public Key File', inputs.FileInput),
    }

    def __init__(self, master):
        super().__init__(master)
        self.browsebutton = ttk.Button(self, text='Browse...', command=self.on_browse)
        self.browsebutton.grid(row=len(self.widgets) - 1, column=2)
        self.grid_columnconfigure(1, weight=1)

    def on_browse(self):
        """Browse Public Key File"""
        filename = filedialog.askopenfilename()
        if filename == '':
            return
        else:
            self.widgets['pubkey'].set(filename)


class ForwardTreeView(ttk.LabelFrame):
    """Treeview for all forwardings"""

    def __init__(self, master):
        super().__init__(master, text='Forwarded Ports')
        columns = {
            'label': 'Label',
            'local_port': 'Local Port',
            'hostname': 'Hostname',
            'remote_port': 'Remote Port',
        }
        yscroll = ttk.Scrollbar(self)
        yscroll.pack(side='right', fill='y')
        xscroll = ttk.Scrollbar(self, orient='horizontal')
        xscroll.pack(side='bottom', fill='x')
        self.treeview = ttk.Treeview(self, columns=list(columns.keys()),
                                     yscrollcommand=yscroll.set,
                                     xscrollcommand=xscroll.set)
        self.treeview.column("#0", width=0, stretch=False)
        # self.treeview.heading("#0",text="",anchor='center')
        for name, title in columns.items():
            self.treeview.heading(name, text=title)
            # , anchor='center', width=80)

        self.treeview.column('label', width=120, anchor='e', minwidth=80)
        self.treeview.column('local_port', width=80, anchor='e', minwidth=80)
        self.treeview.column('hostname', width=80, anchor='e', minwidth=80)
        self.treeview.column('remote_port', width=80, anchor='e', minwidth=80)
        self.treeview.pack(fill='both', expand=True)

        yscroll.config(command=self.treeview.yview)
        xscroll.config(command=self.treeview.xview)

        self.last_added: ForwardedPort = ForwardedPort(8000, '', 22)
        self.treeview.bind('<Double-Button-1>', self.edit)

    def get(self):
        values: List[ForwardedPort] = []
        for name in self.treeview.get_children():
            label, local_port, hostname, remote_port = self.treeview.item(name)['values']
            values.append(ForwardedPort(local_port, hostname, remote_port, label))
        return values

    def set(self, forwardings: List[ForwardedPort]):
        self.clear()
        for forwarding in forwardings:
            self.treeview.insert('', 'end', str(id(forwarding)), values=(forwarding.label, forwarding.local_port,
                                                                         forwarding.hostname, forwarding.remote_port))
            self.last_added = forwarding

    def add(self, forwarding: ForwardedPort):
        """Add new Forwarding"""
        if str(id(forwarding)) not in self.treeview.get_children():
            self.treeview.insert('', 'end', str(id(forwarding)), values=(forwarding.label, forwarding.local_port,
                                                                         forwarding.hostname, forwarding.remote_port))
            self.last_added = forwarding

    def get_selected(self) -> List[ForwardedPort]:
        """Get treeview items selected by user"""
        selected: List[ForwardedPort] = []
        for name in self.treeview.selection():
            label, local_port, hostname, remote_port = self.treeview.item(name)['values']
            selected.append(ForwardedPort(local_port, hostname, remote_port, label))
        return selected

    def remove_selected(self):
        """Remove selected items"""
        for item in self.treeview.selection():
            self.treeview.delete(item)

    def clear(self):
        """Remove all items from treeview"""
        self.treeview.delete(*self.treeview.get_children())

    def edit(self, event=None):
        name = self.treeview.selection()[0]
        label, local_port, hostname, remote_port = self.treeview.item(name)['values']
        # Ignore if multiple elemtents were selected
        dialog = views.AddDialogue(self)
        dialog.set(ForwardedPort(local_port, hostname, remote_port, label))
        dialog.focus_set()
        dialog.grab_set()
        dialog.wait_window()
        if not dialog.canceled:
            edited = dialog.get()
            self.treeview.item(name, values=(edited.label, edited.local_port, edited.hostname, edited.remote_port))


class ToolTip:
    """
    create a tooltip for a given widget
    """
    def __init__(self, widget, text: str, tagname: Optional[str] = None):
        self.waittime = 500     #miliseconds
        self.wraplength = 180   #pixels
        self.widget = widget
        self.text = text
        if tagname:
            self.widget.tag_bind(tagname, "<Enter>", self.enter, add='+')
            self.widget.tag_bind(tagname, "<Leave>", self.leave, add='+')
            self.widget.tag_bind(tagname, "<ButtonPress>", self.leave, add='+')
        else:
            self.widget.bind("<Enter>", self.enter, add='+')
            self.widget.bind("<Leave>", self.leave, add='+')
            self.widget.bind("<ButtonPress>", self.leave, add='+')
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background="#ffffff", relief='solid', borderwidth=1,
                         wraplength=self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()


class HyperlinkText(tk.Text):
    def __init__(self, master, *args, cursor='arrow', **kwargs):
        super().__init__(master, *args, cursor=cursor, **kwargs)
        self.cursor = cursor
        self._counter = count()

    def insert_link(self, text, url):
        tagname: str = f'hyperlink-{next(self._counter)}'
        self.tag_configure(tagname, foreground='blue', font='TkFixedFont', underline=True)
        self.tag_bind(tagname, '<Button-1>', lambda e: webbrowser.open(url))
        self.tag_bind(tagname, '<Enter>', lambda e: self.configure(cursor='hand2'))
        self.tag_bind(tagname, '<Leave>', lambda e: self.configure(cursor=self.cursor))
        self.insert('end', text, tagname)
        ToolTip(self, url, tagname)
