"""Implementation of PortForwardingTool"""

import sys as _sys

__version__ = 'UNKNOWN'
if getattr(_sys, "frozen", False):
    try:
        from forwardingtool._version import __version__
    except ModuleNotFoundError:
        pass
