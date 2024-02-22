"""
Keys need to know where they sit in the object tree
because a path may need to be filled in with new objects
when a leaf is assigned.

We want to support three operations on keys: get, set, and delete.
These mirror the operations available for native keys in Python:
`__getitem__`, `__setitem__`, and `__delitem__`.

Syntactically, the operations look like this:

- get:    `x = a.b.c()`
- set:    `a.b.c = x`
- delete: `del a.b.c`

Those forms translate into these:

- get:    `a.__getattr__('b').__getattr__('c').__call__(default=KeyError)`
- set:    `a.__getattr__('b').__setattr__('c', x)
- delete: `a.__getattr__('b').__delattr__('c')

Those expressions are not perfectly decomposable.
Consider the translation-preserving equivalent operations
on a binding `y = a.b.c`:

- get:    `x = y()`
- set:    `confee.set(y, x)` [^1]
- delete: `confee.delete(y)` [^2]

[^1]: Assignment cannot be overridden!
[^2]: `del y` calls the destructor `y.__del__()`.
We could override that to delete the setting proxied by `y`,
but destructors are called all the time, automatically,
not just by the programmer. We must ignore calls to the destructor.
"""

import contextlib
import copy
import json
import pathlib
import shutil
import tempfile
import tomlkit
import typing as t

from cupcake.expression import evaluate

_MISSING = object()
_SELVES = {}

class CancelOperation(BaseException):
    """Signal the calling context to not commit any changes."""

@contextlib.contextmanager
def atomic(pathlike, *args, **kwargs):
    dst = pathlib.Path(pathlike)
    kwargs['delete'] = False
    # Write to temporary file and then atomically move into place.
    with tempfile.NamedTemporaryFile(*args, **kwargs) as file:
        try:
            yield file
        except CancelOperation:
            return
        # Other exceptions will cancel AND bubble.
    src = pathlib.Path(file.name)
    try:
        # https://stackoverflow.com/a/21116654/618906
        shutil.move(src, dst)
    finally:
        src.unlink(missing_ok=True)

def resolve(override, proxy, default):
    """Resolve a configuration value.

    If the override is missing, use the value from the config.
    If the config has no value, use the default.
    If the override is not missing, use it and store it in the config.
    """
    self = _SELVES[proxy]
    if override is None:
        value = self.value
        if value is _MISSING:
            return default() if callable(default) else default
        return value
    # The proxy should point to a leaf in the config.
    assert self.parent
    self.parent.set(self.name, override)
    return override

# Variables are a little unique.
# We must start with `config.cmake.variables` (default `{}`),
# override with `variables`,
# remove `unvariables`,
# and then write the result to `config.cmake.variables`.
def merge(adds, removes, proxy, default):
    """
    Compile a set of options.

    Start with a saved setting in `proxy` (default `default`),
    override with `adds`, remove `removes`,
    and then write the result back to the saved setting
    if it does not match `default`,
    or delete the saved setting if it does.
    """
    start = copy.copy(default)
    group = proxy(start)
    for name, value in adds.items():
        group[name] = value
    for name in removes:
        group.pop(name, None)
    if group == default:
        delete(proxy)
    else:
        set(proxy, group)
    return group

class TomlType:
    def read(self, file):
        return tomlkit.load(file)
    def write(self, file, value):
        tomlkit.dump(value, file)
    def root(self):
        return tomlkit.document()
    def object(self):
        return tomlkit.table()

class JsonType:
    def read(self, file):
        return json.load(file)
    def write(self, file, value):
        json.dump(value, file)
    def root(self):
        return {}
    def object(self):
        return {}

def read(pathlike, typ=None):
    path = pathlib.Path(pathlike)
    if typ is None:
        if path.suffix == '.json':
            typ = JsonType()
        else:
            # Default is TOML.
            typ = TomlType()
    # TODO: try-except?
    if path.exists():
        with path.open('r') as file:
            root = typ.read(file)
    else:
        root = typ.root()
    return Proxy(typ, None, path, root)

def write(proxy):
    self = _SELVES[proxy]
    path = self.name
    with atomic(path, 'w') as file:
        self.typ.write(file, self.value)

# Because configs must be serializeable to TOML or JSON,
# the only permissible keys are strings and integers.
Subscript = t.Union[str, int]

def lookup(subscriptable, subscript, default):
    try:
        return subscriptable[subscript]
    except LookupError:
        return default

class Value:
    def __init__(self, typ, parent, name, value):
        self.typ = typ
        self.parent = parent
        self.name = name
        self.value = value
        # Map from names to proxies.
        self.members = {}
    def get(self, name: Subscript):
        proxy = self.members.get(name, None)
        if proxy is None:
            value = (
                _MISSING
                if self.value is _MISSING
                else lookup(self.value, name, _MISSING)
            )
            proxy = Proxy(self.typ, self, name, value)
            self.members[name] = proxy
        return proxy
    def set(self, name, value):
        # TOML has no null value.
        if value is None:
            return self.delete(name)
        if self.value is _MISSING:
            self.parent.set(self.name, self.typ.object())
        self.value[name] = value
        proxy = self.members.get(name, None)
        if proxy is not None:
            _SELVES[proxy].value = value
    def delete(self, name):
        if self.value is _MISSING:
            return
        try:
            del self.value[name]
        except KeyError:
            pass
        # Parents are always containers.
        # Empty containers should be removed.
        # Empty containers can be distinguished because they are falsy.
        if not self.value and self.parent:
            self.parent.delete(self.name)
        proxy = self.members.get(name, None)
        if proxy is not None:
            del self.members[name]
            del _SELVES[proxy]

class Proxy:
    def __init__(self, typ, parent, name, value):
        _SELVES[self] = Value(typ, parent, name, value)
    def __getitem__(self, name):
        # TODO: Can we use `Subscript` somehow?
        if isinstance(name, (str, int)):
            return _SELVES[self].get(name)
        return MultiProxy(self, name)
    def __getattr__(self, name):
        return self[name]
    def __setitem__(self, name, value):
        _SELVES[self].set(name, value)
    def __setattr__(self, name, value):
        self[name] = value
    def __delattr__(self, name):
        return _SELVES[self].delete(name)
    def __call__(self, default=_MISSING, *args, **kwargs):
        underlying = _SELVES[self]
        value = underlying.value
        if value is _MISSING:
            if default is _MISSING:
                raise KeyError(_path(underlying))
            return default
        return value
    def __iter__(self):
        return iter([self])
    def __bool__(self):
        return _SELVES[self].value is not _MISSING

class MultiProxy:
    """An iterable that yields proxies."""
    def __init__(self, parent, indices):
        self.parent = parent
        self.indices = indices
    def __iter__(self):
        for proxy in self.parent:
            # Recompute exact indices for each iterable.
            indices = self.indices
            if isinstance(indices, slice):
                if not proxy:
                    continue
                # Raises if there is no underlying.
                underlying = proxy()
                if isinstance(underlying, t.Mapping):
                    # Only unbounded slices are valid for mappings.
                    assert(indices.start is None and indices.stop is None)
                    yield from (proxy[key] for key in underlying)
                    continue
                else:
                    # JSON does not have sequences other than array.
                    assert(isinstance(underlying, t.Sequence))
                    indices = to_indices(indices, len(underlying))
            yield from (proxy[index] for index in indices)
    def __getitem__(self, indices):
        if isinstance(indices, (int, str)):
            indices = [indices]
        return MultiProxy(self, indices)
    def __getattr__(self, name):
        return self[name]

def sign(i):
    return 1 if i > 0 else -1 if i < 0 else 0

def to_indices(slice, length):
    step = slice.step
    if step is None:
        step = 1

    start = slice.start
    if start is None:
        start = 0 if step > 0 else length - 1
    elif start < 0:
        start += length
    if start < 0:
        start = -1 + sign(step)
    elif start >= length:
        start = length + sign(step)

    stop = slice.stop
    if stop is None:
        stop = length if step > 0 else -1
    elif stop < 0:
        stop += length
    if stop < 0:
        stop = -1
    elif stop > length:
        stop = length

    while sign(stop - start) == sign(step):
        yield start
        start += step

def _path(self, suffix=''):
    if self.parent is None:
        return ''
    return _path(self.parent, '.') + self.name + suffix

def path(proxy):
    return _path(_SELVES[proxy])

def set(proxy, value):
    self = _SELVES[proxy]
    if self.parent is None:
        self.value = value
    else:
        self.parent.set(self.name, value)

def delete(proxy):
    self = _SELVES[proxy]
    return self.parent.delete(self.name)

def add(proxy, item):
    items = proxy([])
    set(proxy, items + type(items)([item]))

def filter(proxies, pred):
    for proxy in proxies:
        if evaluate(pred, proxy()):
            yield proxy

def remove_if(proxies, pred):
    for proxy in proxies:
        # Is no default correct here?
        if evaluate(pred, proxy()):
            delete(proxy)
