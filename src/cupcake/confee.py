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

- get:    `a.__getattr__('b').__getattr__('c').__call__(default=None)`
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

import copy
import pathlib
import tomlkit

_MISSING = object()
_SELVES = {}

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
    """Compile a set of options.

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

def read(pathlike):
    path = pathlib.Path(pathlike)
    # TODO: try-except?
    if path.exists():
        with path.open('r') as f:
            root = tomlkit.load(f)
    else:
        root = tomlkit.document()
    return ValueProxy(None, path, root)

def write(proxy):
    self = _SELVES[proxy]
    path = self.name
    with path.open('w') as f:
        tomlkit.dump(self.value, f)

class Value:
    def __init__(self, parent, name, value):
        self.parent = parent
        self.name = name
        self.value = value
        # Map from names to proxies.
        self.members = {}
    def get(self, name):
        proxy = self.members.get(name, None)
        if proxy is None:
            value = (
                _MISSING
                if self.value is _MISSING
                else self.value.get(name, _MISSING)
            )
            proxy = ValueProxy(self, name, value)
            self.members[name] = proxy
        return proxy
    def set(self, name, value):
        if self.value is _MISSING:
            self.parent.set(self.name, tomlkit.table())
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
        proxy = self.members.get(name, None)
        if proxy is not None:
            del self.members[name]
            del _SELVES[proxy]

class ValueProxy:
    def __init__(self, parent, name, value):
        _SELVES[self] = Value(parent, name, value)
    def __getattr__(self, name):
        return _SELVES[self].get(name)
    def __setattr__(self, name, value):
        return _SELVES[self].set(name, value)
    def __delattr__(self, name):
        return _SELVES[self].delete(name)
    def __call__(self, default=None, *args, **kwargs):
        value = _SELVES[self].value
        return default if value is _MISSING else value
    def __bool__(self):
        return _SELVES[self].value is not _MISSING

def set(proxy, value):
    self = _SELVES[proxy]
    if self.parent is None:
        self.value = value
    else:
        self.parent.set(self.name, value)

def delete(proxy):
    self = _SELVES[proxy]
    return self.parent.delete(self.name)
