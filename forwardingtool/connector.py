from typing import Optional
import sys
import os

import sshtunnel
import paramiko
from paramiko.ssh_exception import SSHException, PasswordRequiredException
import keyring
from keyring.errors import NoKeyringError, KeyringLocked

from . import views
from . import config

APP: str = 'forwardingtool'


def load_key(master, keyfile: str) -> Optional[paramiko.RSAKey]:
    """
    Load RSA key from file.

    If the key file is encrypted, try to load the key from keyring. If no password is found in the keyring or if the \
    password is incorrect, prompt the user up to three times to enter the correct password. If the entered password is \
    correct, it will be automatically stored in the keyring.
    """

    # Try key without password
    key: Optional[paramiko.RSAKey] = None
    try:
        key = paramiko.RSAKey.from_private_key_file(keyfile)
    except PasswordRequiredException:
        # key is encrypted
        # try to fetch password from keyring
        try:
            pwd: Optional[str] = keyring.get_password(APP, keyfile)
            key = paramiko.RSAKey.from_private_key_file(keyfile, password=pwd)
        except (PasswordRequiredException, NoKeyringError, KeyringLocked, SSHException):
            # Password was not found in keyring, or no keyring backend available or keyring locked
            for _ in range(3):
                pwdialog = views.PasswordDialog(master)
                pwd = pwdialog.ask()
                if pwdialog.aborted:
                    break
                try:
                    key = paramiko.RSAKey.from_private_key_file(keyfile, password=pwd)
                except SSHException:
                    # Invalid password
                    pass
                else:
                    try:
                        keyring.set_password(APP, keyfile, pwd)
                    except (NoKeyringError, KeyringLocked):
                        pass
                    break
    except SSHException:
        # Key is invalid (e.g. wrong format)
        pass

    return key


def connect(cfg: config.Config, key: paramiko.RSAKey) -> sshtunnel.SSHTunnelForwarder:
    """
    Create SSH tunnels from config.
    """

    t = sshtunnel.open_tunnel(
        (cfg.jump_host, cfg.jump_port),
        ssh_username=cfg.username,
        ssh_pkey=key,
        remote_bind_addresses=[(forwarding.hostname, forwarding.remote_port) for forwarding in cfg.forwardings],
        local_bind_addresses=[('0.0.0.0', forwarding.local_port) for forwarding in cfg.forwardings]
    )
    t.start()

    return t
