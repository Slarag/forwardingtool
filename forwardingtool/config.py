"""Configuration for the forwardingtool"""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from typing import List, Optional
import os.path
import re
import argparse
import shlex

DEFAULTCONFIG: str = './lastused.json'
IPV4PAT: re.Pattern = re.compile(r'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})')


def expandpath(path: str) -> str:
    """Expand environment variables, replace ~ with the users homepath"""
    return os.path.normcase(os.path.expandvars(os.path.expanduser(path)))


def is_port(value: int):
    """Raises a Value Error if the given value is not a valid port number"""
    if not 0 <= value <= 65535:
        raise ValueError(f'{value!r} is not a valid port number. Must be within 0 to 65535')


def is_hostname(value: str):
    """Raises a Value Error if the given value is not a valid host name"""
    if value == '':
        raise ValueError('Remote hostname must not be empty')
    elif IPV4PAT.search(value):
        fullmatch = IPV4PAT.fullmatch(value)
        if not fullmatch:
            raise ValueError(f'{value!r} is not not a valid IPv4 address')
        elif any(filter(lambda x: not 0 <= x <= 255, [int(i) for i in fullmatch.groups()])):
            raise ValueError(f'{value!r} is not not a valid IPv4 address')


@dataclass(order=True)
class ForwardedPort:
    """Dataclass describing a single forwarded port"""
    local_port: int
    hostname: str
    remote_port: int
    label: str = ''

    def validate(self) -> None:
        """Raises a ValueError if configuration is not valid"""
        is_hostname(self.hostname)
        is_port(self.remote_port)
        is_port(self.local_port)
        if self.label and not self.label.isprintable():
            raise ValueError('Label must be printable')

    def __str__(self) -> str:
        return f'{self.local_port}:{self.hostname}:{self.remote_port}'


@dataclass
class Config:
    """Dataclass for configuration"""
    jump_host: str
    username: str = ''
    jump_port: int = 22
    key: Optional[str] = None
    forwardings: List[ForwardedPort] = field(default_factory=list)

    @classmethod
    def load(cls, filename: str) -> Config:
        """Load config from json file"""
        with open(os.path.abspath(filename), mode='r') as file:
            data = json.load(file)
            data['forwardings'] = [ForwardedPort(**x) for x in data['forwardings']]
            instance = cls(**data)
            instance.validate()
            return instance

    @classmethod
    def from_cmd(cls, cmd: str):
        parser = argparse.ArgumentParser()
        parser.add_argument('cmd')
        parser.add_argument('user_host')
        parser.add_argument('-i', default=None)
        parser.add_argument('-L', action='append')
        parser.add_argument('-p', type=int, default=22)
        parser.add_argument('-N', action='store_true')

        args, unknown = parser.parse_known_args(shlex.split(cmd, posix=False))

        if '@' in args.user_host:
            username, jump_host = args.user_host.split('@', maxsplit=1)
        else:
            username = ''
            jump_host = args.user_host

        forwardings: List[ForwardedPort] = []
        for f in args.L:
            local_port, hostname, remote_port = f.split(':', maxsplit=2)
            fw = ForwardedPort(int(local_port), hostname, int(remote_port))
            forwardings.append(fw)

        instance = cls(jump_host, username, args.p, args.i, forwardings)
        instance.validate()
        return instance

    def save(self, filename: str) -> None:
        """Save config to json file"""
        with open(os.path.abspath(filename), mode='w') as file:
            json.dump(asdict(self), file, indent=2)

    def validate(self) -> None:
        """Raises a ValueError if configuration is not valid"""
        is_hostname(self.jump_host)
        is_port(self.jump_port)
        if self.username and not self.username.isalnum():
            raise ValueError(f'{self.username!r} is not an alphanumeric username')
        if self.key is not None and not os.path.isfile(expandpath(self.key)):
            raise ValueError(f'Public key file {expandpath(self.key)!r} not found')

    def __str__(self) -> str:
        s: str = 'ssh ' + \
                 (f'{self.username}@' if self.username else '') + \
                 f'{self.jump_host}' + \
                 (f' -p {self.jump_port}' if self.jump_port != 22 else '') + \
                 (f' -i {expandpath(self.key)}' if self.key else '') + \
                 ''.join(f' -L {fwd}' for fwd in self.forwardings) + \
                 ' -N'
        return s

    def as_args(self) -> List[str]:
        """Return a list of arguments to be used for a call to subprocesses.run()"""
        args = ['ssh',
                (f'{self.username}@' if self.username else '') + f'{self.jump_host}',
                '-N',
                ]
        if self.jump_port != 22:
            args += ['-p', f'{self.jump_port}']
        if self.key:
            args += ['-i', f'{expandpath(self.key)}']
        for fwd in self.forwardings:
            args += ['-L', f'{fwd}']
        return args
