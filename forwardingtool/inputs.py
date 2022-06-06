"""Input widgets for the GUI"""

import os.path
import re
import tkinter as tk
import tkinter.ttk as ttk
from typing import Optional, List, Union, Tuple, Any, Dict, Generic, TypeVar

from forwardingtool.config import is_hostname


DEFAULTPORTS: List[Tuple[int, str]] = [
    (22, '22 (SSH)'),
    (80, '80 (HTTP)'),
    # (123, '123 (NTP)'),
    (443, '443 (HTTPS)'),
    # (3306, '3306 (MariaDB/MySQL)'),
    (1883, '1883 (MQTT)'),
    (3389, '3389 (Windows Remote Desktop)'),
    (4880, '4880 (HiSLIP)'),
    (5800, '5800 (UVNC Java Viewer)'),
    (5900, '5900 (VNC)'),
    # (5672, '5672 (RabittMQ)'),
    # (6379, '6379 (Redis)'),
    (8883, '8883 (MQTT)'),
]


class GetSetMixin:
    """Mixin for convenient get/set"""
    variable: tk.Variable

    def get(self):
        """Get value"""
        return self.variable.get()

    def set(self, value):
        """Set value"""
        return self.variable.set(value)


class SwitchableMixin:
    """
    Mixin that allows enabling/disabling the widget
    """

    def __init__(self, *args, enablevar: tk.BooleanVar = None, readonly: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.enablevar = enablevar or tk.BooleanVar(value=True)
        self._is_readonly = readonly
        # self._encb: str = self.enablevar.trace_add('write', self.update_state)
        self.update_state()

    def update_state(self, *args):
        """Enable/disable the widget"""

        if self.enablevar.get():
            if self._is_readonly:
                self.configure(state='readonly')
            else:
                self.configure(state='normal')
        else:
            self.configure(state='disabled')

    def remove_trace(self) -> None:
        self.enablevar.trace_remove('write', self._encb)

    def enable(self):
        self.enablevar.set(True)

    def disable(self):
        self.enablevar.set(False)

    # def remove_trace(self) -> None:
    #     if hasattr(self, 'enablevar') and self.enable is not None:
    #         self.enable.trace_remove('write', self._encb)


class ValidatorMixin:
    """Mixin for basic input validation functionalities"""

    def __init__(self, *args, error_var=None, **kwargs):
        self.error = error_var or tk.StringVar()
        super().__init__(*args, **kwargs)

        vcmd = self.register(self._validate)
        invcmd = self.register(self._invalid)

        self.config(
            validate='all',
            validatecommand=(vcmd, '%P', '%s', '%S', '%V', '%i', '%d'),
            invalidcommand=(invcmd, '%P', '%s', '%S', '%V', '%i', '%d'),
        )

    def _toggle_error(self, on=False):
        """Mark/Unmark input as incorrect"""

        self.configure(foreground=('red' if on else 'black'))

    def _validate(self, proposed, current, char, event, index, action):
        self._toggle_error(False)
        self.error.set('')
        valid: bool = False
        if event == 'focusout':
            valid = self._focusout_validate(event=event)
        elif event == 'key':
            valid = self._key_validate(proposed=proposed, current=current,
                                       char=char, event=event, index=index,
                                       action=action)
        return valid

    def _focusout_validate(self, **kwargs):
        return True

    def _key_validate(self, **kwargs):
        return True

    def _invalid(self, proposed, current, char, event, index, action):
        if event == 'focusout':
            self._focusout_invalid(event=event)
        elif event == 'key':
            self._key_invalid(proposed=proposed, current=current,
                              har=char, event=event, index=index,
                              action=action)

    def _focusout_invalid(self, **kwargs):
        self._toggle_error(True)

    def _key_invalid(self, **kwargs):
        pass

    def trigger_focusout_validation(self):
        """Manually trigger validation of the input"""

        valid: bool = self._validate('', '', '', 'focusout', '', '')
        if not valid:
            self._focusout_invalid(event='focusout')
        return valid


class CombinedMixin(SwitchableMixin, GetSetMixin, ValidatorMixin):
    """Mixing which combines SwitchableMixin, GetSetMixin, ValidatorMixin. For convenience only."""


class CheckButton(CombinedMixin, tk.Checkbutton):
    """Enhanced Checkbutton widget"""

    def __init__(self, *args, **kwargs):

        self.variable: tk.BooleanVar = kwargs.pop('variable', tk.BooleanVar())
        super().__init__(*args, variable=self.variable, **kwargs)


class NumericInput(CombinedMixin, ttk.Spinbox):
    """Enhanced Spinbox widget with validation"""

    MIN = float('-inf')
    MAX = float('inf')
    INCREMENT = 1.
    VARTYPE = tk.DoubleVar

    def __init__(self, *args, enablevar: Optional[tk.BooleanVar] = None, **kwargs):

        self.variable: tk.Variable = kwargs.pop('textvariable', self.VARTYPE())
        super().__init__(*args, textvariable=self.variable, from_=self.MIN,
                         to=self.MAX, increment=self.INCREMENT,
                         enablevar=enablevar, **kwargs)

    def _key_validate(self, proposed, action, **kwargs):
        valid = True
        if action == '0':
            valid = True
        else:
            try:
                int(proposed)
            except ValueError:
                valid = False
        return valid

    def _focusout_validate(self, **kwargs):
        valid = True
        try:
            value = int(self.get())
            if value < self.MIN or value > self.MAX:
                valid = False
                self.error.set(f'Value must be within {self.MIN} to {self.MAX}')
        except ValueError:
            self.error.set('Not an integer')
        except tk.TclError:
            valid = False
            self.error.set('A value is required')
        return valid


class StringInput(CombinedMixin, ttk.Entry):
    """Enhanced Entry widget with validation"""

    VALID_CHARS: Optional[Union[str, List[str]]] = None
    INVALID_CHARS: Optional[Union[str, List[str]]] = None
    MAX_LEN: int = 0
    MIN_LEN: int = 0
    RE: Optional[Union[re.Pattern, str]] = None
    MSG_NOMATCH = 'Value does not match regular expression'

    def __init__(self, *args, enablevar: Optional[tk.BooleanVar] = None,
                 **kwargs):

        self.variable: tk.StringVar = kwargs.pop('textvariable', tk.StringVar())
        super().__init__(*args, textvariable=self.variable,
                         enablevar=enablevar, **kwargs)

    def _key_validate(self, proposed, action, **kwargs):
        if action == '0':
            return True
        if self.MAX_LEN and len(proposed) > self.MAX_LEN:
            return False
        if self.VALID_CHARS is not None:
            for char in proposed:
                if char not in self.VALID_CHARS:
                    return False
        if self.INVALID_CHARS is not None:
            for char in proposed:
                if char in self.INVALID_CHARS:
                    return False

    def _focusout_validate(self, **kwargs):
        value: str = self.get()
        if not value:
            self.error.set('A value is required')
            return False

        if self.MIN_LEN and len(value) < self.MIN_LEN:
            self.error.set(f'At least {self.MIN_LEN} characters are required')
            return False
        if self.MAX_LEN and len(value) > self.MAX_LEN:
            self.error.set(f'At most {self.MAX_LEN} characters are allowed')
            return False
        if self.VALID_CHARS is not None:
            for char in value:
                if char not in self.VALID_CHARS:
                    self.error.set(f'Illegal character: {char!r}')
                    return False
        if self.INVALID_CHARS is not None:
            for char in value:
                if char in self.INVALID_CHARS:
                    self.error.set(f'Illegal character: {char!r}')
                    return False
        if self.RE is not None:
            if isinstance(self.RE, str) and not re.fullmatch(self.RE, value):
                self.error.set(self.MSG_NOMATCH)
                return False
            elif not re.fullmatch(self.RE, value):
                self.error.set(self.MSG_NOMATCH)
                return False
        return True


T = TypeVar('T')


class Selector(CombinedMixin, ttk.Combobox, Generic[T]):
    """Enhanced Combobox widget with validation"""

    CHOICES: Optional[List[Tuple[str, T]]] = None
    ALLOW_OTHER: bool = True

    def __init__(self, *args, enablevar: Optional[tk.BooleanVar] = None,
                 choices: List[Tuple[str, Any]] = None, **kwargs):

        self.choices: List[Tuple[str, T]] = self.CHOICES or choices or []
        self.variable: tk.StringVar = kwargs.pop('textvariable', tk.StringVar())
        super().__init__(*args, textvariable=self.variable,
                         values=[x[0] for x in self.choices],
                         enablevar=enablevar, readonly=not self.ALLOW_OTHER, **kwargs)

        self._opts: Dict[str, T] = dict(self.choices)
        self._ropts: Dict[T, str] = dict(reversed(x) for x in self.choices)

    def get(self) -> T:
        """Set the internal variable"""

        selected: T = self.variable.get()
        if selected in self._opts:
            return self._opts[selected]
        elif self.ALLOW_OTHER:
            return selected
        raise ValueError(f'Invalid value: {selected!r}')

    def set(self, value: T):
        """Get the internal variable"""

        if value in self._ropts:
            return self.variable.set(self._ropts[value])
        elif self.ALLOW_OTHER:
            return self.variable.set(value)
        raise ValueError(f'Invalid value: {value!r}')

    def _focusout_validate(self, **kwargs):
        try:
            if not self.get():
                self.error.set('A value is required')
                return False
        except tk.TclError:
            self.error.set('A value is required')
            return False
        except KeyError:
            self.error.set('A value is required')
            return False
        return True


class PortInput(NumericInput):
    """Input for TCP/IP Port number"""

    MIN: int = 0
    MAX: int = 65535
    INCREMENT: int = 1
    VARTYPE = tk.IntVar


class PortSelectorInput(Selector[int]):
    """Combobox input for TCP IP Port numbers"""
    CHOICES: Optional[List[Tuple[str, int]]] = [x[::-1] for x in DEFAULTPORTS]
    ALLOW_OTHER: bool = True
    MIN: int = 0
    MAX: int = 65535
    INCREMENT: int = 1

    _key_validate = PortInput._key_validate

    def _focusout_validate(self, **kwargs):
        super()._focusout_validate()
        PortInput._focusout_validate(self)


class FileInput(StringInput):
    """Input for file (file must exist)"""

    def _focusout_validate(self, **kwargs):
        super()._focusout_validate(**kwargs)
        value: str = self.get()
        value = os.path.expanduser(value)
        value = os.path.expandvars(value)
        if not os.path.isfile(value):
            self.error.set(f'File not found: {value!r}')
            return False
        return True


class HostnameInput(StringInput):
    """Input for host name"""

    def _focusout_validate(self, **kwargs):
        super()._focusout_validate(**kwargs)

        try:
            is_hostname(self.get())
            return True
        except ValueError as exc:
            self.error.set(exc.args[0])
            return False


class UsernameInput(StringInput):
    """Input for host name"""

    RE: Optional[Union[re.Pattern, str]] = re.compile(r'[a-zA-Z0-9_]*')
    MSG_NOMATCH = 'Username must be an alphanumeric value'


class PwEntry(ttk.Entry, SwitchableMixin):
    def __init__(self, master, *args, variable=None, on_enter=None, **kwargs):

        self.frame = ttk.Frame(master)
        self.variable = variable or tk.StringVar()

        super().__init__(self.frame, show='*', textvariable=self.variable)
        # self.entry = ttk.Entry(self, show='*', textvariable=self.variable)
        self.button = ttk.Button(self.frame, text='👁', width=3)

        super().grid(row=0, column=1, sticky='ew')
        self.button.grid(row=0, column=2, sticky='ew')
        self.grid_columnconfigure(0, weight=1)

        self.button.bind("<ButtonPress-1>", self.show_pw)
        self.button.bind("<ButtonRelease-1>", self.hide_pw)

    def get(self):
        return self.variable.get()

    def set(self, value):
        return self.variable.set(value)

    def show_pw(self, *args):
        self.configure(show='')

    def hide_pw(self, *args):
        self.configure(show='*')

    def update_state(self, *args):
        if self.enablevar.get():
            if self._is_readonly:
                self.configure(state='readonly')
            else:
                self.configure(state='normal')
        else:
            self.configure(state='disabled')

    def grid(self, *args, sticky='ew', **kwargs):
        self.frame.grid(*args, sticky=sticky, **kwargs)

    def pack(self, *args, **kwargs):
        self.frame.pack(*args, **kwargs)

    def place(self, *args, **kwargs):
        self.frame.grid(*args, **kwargs)
