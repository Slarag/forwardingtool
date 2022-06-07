from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog
from tkinter import messagebox
import os
import os.path
import json
from functools import partialmethod
from traceback import format_exc
from copy import deepcopy
from typing import Optional, List, Tuple, Any, Callable, Union

import sshtunnel
from PIL import Image, ImageTk

from forwardingtool.widgets import ForwardTreeView, ConnectionSetupView, AddForwardView
from forwardingtool.config import Config, ForwardedPort, DEFAULTCONFIG
from forwardingtool.version import __version__ as VERSION

from . import widgets
from . import inputs
from . import utils
from . import connector
from . import config


class IconMixin:
    """
    Mixin to automatically set the icon and title for a tk.Tk or tk.Toplevel window
    """

    ICON: str = 'logo'
    TITLE: str = 'ForwaringTool'

    iconbitmap: Callable[[Union[str, bytes]], None]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title(self.TITLE)
        self.logo = None

        try:
            if os.name == 'nt':
                imagefile: str = utils.get_datafile(self.ICON + '.ico')
                self.iconbitmap(imagefile)
            else:
                imagefile: str = utils.get_datafile(self.ICON + '.gif')
                if isinstance(self, tk.Tk):
                    self.call('wm', 'iconphoto', self._w, tk.PhotoImage(file=imagefile))
            self.logo = ImageTk.PhotoImage(Image.open(imagefile))
        except (FileNotFoundError, tk.TclError):
            print('Could not load logo!')
            raise
            # No icon file found, just use the default icon
            pass


class MessageMixin:
    def showinfo(self, msg: str, parent=None, block: bool = True, typ: str = 'info'):
        if parent is None:
            parent = self
        func = messagebox.showinfo
        if typ == 'warning':
            func = messagebox.showwarning
        elif typ == 'error':
            func = messagebox.showerror
        call = lambda: func('Port Forwarding Tool', msg, parent=parent)
        if block:
            call()
        else:
            parent.after(0, call)

    showwarning = partialmethod(showinfo, typ='warning')
    showerror = partialmethod(showinfo, typ='error')

    def askyesno(self, msg: str, parent=None, **kwargs):
        if parent is None:
            parent = self
        return messagebox.askyesno('Margin Test', msg, parent=parent, **kwargs)

    def askyesnocancel(self, msg: str, parent=None, **kwargs):
        if parent is None:
            parent = self
        return messagebox.askyesnocancel('Margin Test', msg, parent=parent, **kwargs)


class AddDialogue(MessageMixin, IconMixin, tk.Toplevel):
    TITLE: str = 'Add Port'

    def __init__(self, master):
        super().__init__()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.canceled = False

        self.master = master
        self.frame = AddForwardView(self)
        self.okbutton = ttk.Button(self, text='OK', command=self.on_ok)

        self.frame.grid(row=0, column=0)
        self.okbutton.grid(row=1, column=0)

        self.bind('<Escape>', self.on_close)

    def get(self) -> ForwardedPort:
        return self.frame.get()

    def set(self, forwarding: ForwardedPort):
        return self.frame.set(forwarding)

    def on_close(self, event=None):
        self.canceled = True
        self.destroy()

    def on_ok(self, event=None):
        errors = self.frame.get_errors()
        if errors:
            errors[0][1].focus_set()
            self.showerror(errors[0][0])
        else:
            self.destroy()


class App(MessageMixin, IconMixin, tk.Tk):
    TITLE: str = 'ForwardingTool'

    def __init__(self):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.menubar = tk.Menu(self)
        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label='Load Config', accelerator='Ctrl+O', underline=0, command=self.on_load)
        self.filemenu.add_command(label='Save Config', accelerator='Ctrl+S', underline=0, command=self.on_save)
        self.filemenu.add_command(label='Export batch file', accelerator='Ctrl+E', underline=0, command=self.on_export)
        self.filemenu.add_command(label='Copy command string', accelerator='Ctrl+C', underline=0, command=self.on_copy)
        self.filemenu.add_command(label='Quit', accelerator='Alt+F4', underline=0, command=self.on_close)
        self.menubar.add_cascade(label='File', underline=0, menu=self.filemenu)
        self.menubar.add_command(label='About', underline=0, command=self.on_about)
        self.config(menu=self.menubar)

        self.cv = ConnectionSetupView(self)
        self.cv.grid(row=0, column=0, columnspan=2, sticky='news')

        self.fv = ForwardTreeView(self)
        self.fv.grid(row=1, column=0, columnspan=2, sticky='news')

        self.addbutton = ttk.Button(self, text='+', width=5, command=self.on_add)
        self.rembutton = ttk.Button(self, text='-', width=5, command=self.on_remove)
        self.startbutton = ttk.Button(self, text='Start (Ctrl+G)', command=self.on_start)

        widgets.ToolTip(self.addbutton, 'Add new item (Ctrl+[+])')
        widgets.ToolTip(self.rembutton, 'Remove selected item (Ctrl+[-])')

        self.addbutton.grid(row=2, column=0)
        self.rembutton.grid(row=2, column=1)
        self.startbutton.grid(row=3, column=0, columnspan=2, sticky='nesw')

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.bind('<Control-o>', self.on_load)
        self.bind('<Control-s>', self.on_save)
        self.bind('<Control-plus>', self.on_add)
        self.bind('<Control-minus>', self.on_remove)
        self.bind('<Control-g>', self.on_start)
        self.bind('<Control-c>', self.on_copy)
        self.bind('<Control-e>', self.on_export)

        self.load_default()

        self.connection: Optional[sshtunnel.SSHTunnelForwarder] = None

    def on_close(self, event=None):
        if self.connection is not None and self.connection.is_alive:
            if self.askyesno('Close currently active SSH connection?'):
                self.on_disconnect()
            else:
                return
        self.destroy()

    def save_default(self):
        try:
            cfg: Config = self.get()
            if cfg is None:
                return
            cfg.validate()
            cfg.save(DEFAULTCONFIG)
        except (PermissionError, IsADirectoryError):
            self.showerror('Could not write config file')
        except ValueError as exc:
            return
        except Exception:
            self.showerror(f'Unknown error while writing config file: {format_exc()}')

    def on_save(self, event=None):
        filetypes = [
            ('JSON File', '.json'),
            ('All Files', '*')
        ]

        try:
            cfg: Config = self.get()
            if cfg is None:
                return
            cfg.validate()
            filename = filedialog.asksaveasfilename(confirmoverwrite=True, filetypes=filetypes)
            if filename == '':
                return
            cfg.save(filename)
        except (PermissionError, IsADirectoryError):
            self.showerror('Could not write config file')
        except ValueError as exc:
            self.showerror(exc.args[0])
        except Exception:
            self.showerror(f'Unknown error while writing config file: {format_exc()}')

    def load_default(self):
        if not os.path.isfile(DEFAULTCONFIG):
            return
        try:
            cfg: Config = Config.load(DEFAULTCONFIG)
        except (FileNotFoundError, PermissionError):
            self.showerror(f'Could not open file {DEFAULTCONFIG!r}')
        except json.JSONDecodeError as exc:
            self.showerror(f'Error while parsing file (line {exc.lineno}): {exc.msg}')
        except ValueError as exc:
            self.showerror(exc.args[0])
        # pylint: disable=broad-except
        except Exception:
            self.showerror(f'Unknown error while loading config file: {format_exc()}')
        else:
            self.set(cfg)

    def on_load(self, event=None):
        filetypes = [
            ('JSON File', '.json'),
            ('All Files', '*')
        ]
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename == '':
            return
        if not os.path.isfile(filename):
            self.showerror('No file selected')
            return
        try:
            cfg: Config = Config.load(filename)
        except (FileNotFoundError, PermissionError):
            self.showerror(f'Could not open file {DEFAULTCONFIG!r}')
        except json.JSONDecodeError as exc:
            self.showerror(f'Error while parsing file (line {exc.lineno}): {exc.msg}')
        except ValueError as exc:
            self.showerror(exc.args[0])
        # pylint: disable=broad-except
        except Exception:
            self.showerror(f'Unknown error while loading config file: {format_exc()}')
        else:
            self.set(cfg)

    def on_about(self, event=None):
        AboutDialog(self).wait_window()

    def on_add(self, event=None):
        dialog = AddDialogue(self)
        default = deepcopy(self.fv.last_added)
        default.local_port += 1
        dialog.set(default)
        dialog.focus_set()
        dialog.grab_set()
        dialog.wait_window()
        if not dialog.canceled:
            self.fv.add(dialog.get())

    def on_remove(self, event=None):
        self.fv.remove_selected()

    def get(self) -> Optional[Config]:
        errors: List[Tuple[str, Any]] = self.cv.get_errors()
        if errors:
            errors[0][1].focus_set()
            self.showerror(errors[0][0])
            return
        cfg: Config = self.cv.get()
        cfg.forwardings = self.fv.get()
        cfg.validate()
        return cfg

    def set(self, cfg: Config):
        self.cv.set(cfg)
        self.fv.set(cfg.forwardings)

    def on_start(self, event=None):
        try:
            if self.connection is not None:
                return

            try:
                cfg = self.get()
                if cfg is None:
                    return
                cfg.validate()
            except ValueError as exc:
                self.showerror(exc.args[0])
            else:
                # creationflags = 0
                # if sys.platform == 'win32':
                #     creationflags = 16
                # #     creationflags = CREATE_NEW_CONSOLE
                # print(cfg.as_args())
                # Popen(cfg.as_args(), creationflags=creationflags)

                key = connector.load_key(self, config.expandpath(cfg.pubkey))
                if key is None:
                    self.showerror('Could not load private key!')
                    return

                try:
                    self.connection = connector.connect(cfg, key)
                except sshtunnel.BaseSSHTunnelForwarderError as exc:
                    self.showerror(exc.value)
                else:
                    self.save_default()
                    self.startbutton.config(text='Disconnect', command=self.on_disconnect)
                    self.after(100, self.check_connection)
                    self.showinfo('Successfully connected to SSH server!')
        except Exception as exc:
            self.showerror(format_exc())

    def check_connection(self):
        if self.connection is None:
            return
        if self.connection.is_alive:
            self.after(100, self.check_connection)
        else:
            self.on_disconnect()

    def on_disconnect(self):
        if self.connection is not None:
            self.connection.stop()
            self.connection = None
        self.startbutton.config(text='Start (Ctrl+G)', command=self.on_start)

    def on_copy(self, event=None):
        try:
            cfg = self.get()
            if cfg is None:
                return
            cfg.validate()
        except ValueError as exc:
            self.showerror(exc.args[0])
        else:
            self.clipboard_clear()
            self.clipboard_append(str(cfg))
            self.showinfo('Command copied to clipboard')

    def on_export(self, event=None):
        filetypes = [
            ('Batch File', '.bat'),
            ('All Files', '*')
        ]
        try:
            cfg: Config = self.get()
            if cfg is None:
                return
            cfg.validate()
            filename = filedialog.asksaveasfilename(confirmoverwrite=True, filetypes=filetypes)
            if filename == '':
                return
            if not filename.endswith('.bat'):
                filename += '.bat'
            with open(filename, mode='w') as file:
                file.write(str(cfg))
        except (PermissionError, IsADirectoryError):
            self.showerror('Could not write batch file')
        except ValueError as exc:
            self.showerror(exc.args[0])
        except Exception:
            self.showerror(f'Unknown error while writing config file: {format_exc()}')


class PasswordDialog(IconMixin, tk.Toplevel):
    TITLE: str = ''

    def __init__(self, master):
        super().__init__()
        self.aborted: bool = True

        label = ttk.Label(self, text='Password:')
        self.pwentry = inputs.PwEntry(self)
        self.buttonbox = widgets.ButtonBox(self, ['Ok', 'Cancel'])

        label.grid(row=0, column=0, sticky='w')
        self.pwentry.grid(row=0, column=1, sticky='ew')
        self.buttonbox.grid(row=1, column=0, columnspan=2, sticky='ew')
        self.grid_columnconfigure(0, weight=1)

        self.pwentry.focus_set()

        self.pwentry.bind('<Return>', self.on_ok)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_ok(self, *args):
        self.aborted = False
        self.destroy()

    def on_cancel(self, *args):
        self.aborted = True
        self.destroy()

    def ask(self) -> Optional[str]:
        self.wait_window()
        if self.aborted:
            return None
        else:
            return self.pwentry.get()


class AboutDialog(IconMixin, tk.Toplevel):
    TITLE: str = 'About - ForwardingTool'

    def __init__(self, master):
        super().__init__(master)
        self.resizable(False, False)
        self.geometry('500x250')
        logolabel = ttk.Label(self, image=self.logo)
        text = widgets.HyperlinkText(self)
        button = ttk.Button(self, text='OK', command=self.on_ok)
        text.insert('1.0', 'ForwardingTool is a simple GUI tool for easy setup of multiple SSH tunnels using the same jump server\n'
                         'It is licensed under the MIT license. Soucre code is available on ')
        text.insert_link('GitHub', 'https://github.com/Slarag/forwardingtool')
        text.insert('end', '\n\nIt heavily depends on the ')
        text.insert_link('sshtunnel', 'https://pypi.org/project/sshtunnel/')
        text.insert('end', ' module.\n\n')
        text.insert_link('Tunnel icons created by Freepik - Flaticon', 'https://www.flaticon.com/free-icons/tunnel')

        text.configure(state='disabled')

        logolabel.grid(row=0, column=0)
        text.grid(row=0, column=1, sticky='nesw')
        button.grid(row=1, column=0, columnspan=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.protocol("WM_DELETE_WINDOW", self.on_ok)

    def on_ok(self):
        self.destroy()

# https://stackoverflow.com/questions/20399243/display-message-when-hovering-over-something-with-mouse-cursor-in-python

# self.showinfo('Port Forwarding Tool to ease setup of SSH port forwarding. Written by Michael Fiederer. '\
        #               f'Version {VERSION}')