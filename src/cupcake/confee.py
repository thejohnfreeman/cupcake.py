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

def read(path):
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
        _SELVES[self.get(name)].value = value
        self.value[name] = value

class ValueProxy:
    def __init__(self, parent, name, value):
        _SELVES[self] = Value(parent, name, value)
    def __getattr__(self, name):
        return _SELVES[self].get(name)
    def __setattr__(self, name, value):
        return _SELVES[self].set(name, value)
    def __call__(self, default=None, *args, **kwargs):
        value = _SELVES[self].value
        return default if value is _MISSING else value
    def __bool__(self):
        return _SELVES[self].value is not _MISSING
    def __del__(self):
        # TODO: Sometimes `_SELVES` is `None`. How?
        if _SELVES:
            del _SELVES[self]
