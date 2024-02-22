import re
import typing as t

from cupcake import confee

def _remove_includes(lines: t.Iterator[str], file: t.TextIO, name: str):
        edited = False
        comment = False
        for line in lines:
            match = re.match(f'#include\\s+<{name}[/.]', line)
            if not comment and match:
                edited = True
                continue
            file.write(line)
            if comment:
                if re.search(r'\*/', line):
                    comment = False
                continue
            match = re.match(r'(\s*)(#|//|/\*|$)', line)
            if not match:
                break
            if match.group(2) == '/*':
                comment = True
        for line in lines:
            file.write(line)
        if not edited:
            raise confee.CancelOperation()

def remove_includes(pathlike, name):
    """Remove includes of named library from file."""
    with confee.atomic(pathlike, mode='w') as fout:
        with open(pathlike, 'r') as fin:
            _remove_includes(iter(fin), fout, name)
