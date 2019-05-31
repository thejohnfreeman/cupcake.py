"""A pseudo-shell for nicer subprocesses.

- Keep preferred defaults as state.
- Echo the command to stdout.
- TODO: Do not echo subprocess output unless there was an error.
- Assert zero return code by default.
"""

import shlex
import subprocess


class Shell:

    def __init__(self, **kwargs):
        self.defaults = {'check': True, **kwargs}

    def run(self, command, *args, **kwargs):
        # Let callers pass `int`s. Just do the right thing.
        command = tuple(str(arg) for arg in command)
        kwargs = {**self.defaults, **kwargs}
        # TODO: Prefix with the CWD?
        print('$ ' + ' '.join(shlex.quote(arg) for arg in command))
        return subprocess.run(command, *args, **kwargs)
