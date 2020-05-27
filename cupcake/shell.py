"""A pseudo-shell for nicer subprocesses.

- Keep preferred defaults as state.
- Accept convertible-to-string arguments instead of just string-like.
- Log the command to stderr by default.
- TODO: Do not echo subprocess output unless there was an error.
- Assert zero return code by default.
"""

import shlex
import subprocess
import sys


class Shell:

    def __init__(self, *, log=sys.stderr, **kwargs):
        self.defaults = {'check': True, **kwargs}
        self.log = log

    def run(self, command, *args, **kwargs):
        # Let callers pass `int`s. Just do the right thing.
        command = tuple(str(arg) for arg in command)
        kwargs = {**self.defaults, **kwargs}
        # TODO: Prefix with the CWD?
        print('$ ' + ' '.join(shlex.quote(arg) for arg in command), file=self.log)
        return subprocess.run(command, *args, **kwargs)
