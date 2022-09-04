"""
cx_Freeze build script for the ForwardingTool to create a frozen (compiled) version of the tool.
"""


import sys
import subprocess
import os.path

from cx_Freeze import setup, Executable

import forwardingtool


def create_versionmodule(packagepath: str):
    """
    creates a file packagepath/_version.py which defines a __version__ variable
    which contains the stripped output of "git describe --dirty --always --tags"
    """

    version = subprocess.run(['git', 'describe', '--dirty', '--always', '--tags'],
                             capture_output=True, encoding='utf-8').stdout.strip()
    with open(os.path.join(packagepath, '_version.py'), mode='w', encoding='utf-8') as file:
        file.write(f'__version__: str = {version!r}\n')


buildOptions = {
    'packages': [
        "tkinter",
        "forwardingtool",
        "keyring",
        # "keyring.backends.Windows",
        "paramiko",
        "sshtunnel",
    ],
    'excludes': [
    ],
    'include_files': [
        'lastused.json',
        'README.md',
    ],
    'include_msvcr': True
}

base = 'Win32GUI' if sys.platform == 'win32' else None
create_versionmodule(packagepath=os.path.dirname(forwardingtool.__file__))

executables = [
    Executable('main.py', base=base, target_name="ForwardingTool.exe", icon='forwardingtool/logo.ico'),
]

setup(name='forwardingtool',
      options={'build_exe': buildOptions},
      executables=executables,
      )
