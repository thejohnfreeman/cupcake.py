import click
import functools
import inspect

from cupcake import functional as fn

# A metaclass must return a class for inheritance to work.
# Inheritance must work to give users a convenient intermediate class.

_MISSING = object()

class Middle:
    def __init__(self, bottom, methods):
        self.bottom = bottom
        self.methods = methods
        self.cache = {}

    def exec(self, name, kwargs):
        value = self.cache.get(name, _MISSING)
        if value is not _MISSING:
            return value
        value = self.methods[name](self, kwargs)
        self.cache[name] = value
        return value

def group(*args, **kwargs):
    def decorator(klass):
        @click.group(*args, **kwargs)
        @click.version_option()
        def group():
            pass

        methods = {}
        members = klass.__dict__

        def add(name):
            method = methods.get(name, None)
            if method is not None:
                return method

            member = members.get(name, None)
            if member is None:
                return

            attr = getattr(member, 'cascade.value', None)
            if attr is None:
                return

            parameters = {
                name: getattr(member, 'cascade.parameters', fn.identity)
            }

            signature = inspect.signature(member)
            dependencies = []
            options = []
            for p in signature.parameters:
                if p == 'self':
                    continue
                method = add(p)
                if method is None:
                    options.append(p)
                else:
                    dependencies.append(p)
                    parameters.update(getattr(method, 'cascade.parameters'))

            attr = getattr(member, 'cascade.command', None)
            if attr is not None:
                args, kwargs = attr
                @group.command(*args, **kwargs)
                @fn.compose(*parameters.values())
                @click.pass_context
                # Set the name of the function to match the command
                # so that Click will call it.
                @functools.wraps(member)
                def command(context, **kwargs):
                    middle = context.obj
                    return middle.exec(name, kwargs)

            def method(middle, kwargs):
                ds = {d: middle.exec(d, kwargs) for d in dependencies}
                os = {o: kwargs[o] for o in options}
                return getattr(middle.bottom, name)(**ds, **os)
            setattr(method, 'cascade.parameters', parameters)

            methods[name] = method
            return method

        for name in members:
            add(name)

        def result(*args, **kwargs):
            bottom = klass(*args, **kwargs)
            middle = Middle(bottom, methods)
            group(obj=middle)

        return result
    return decorator

def command(*args, **kwargs):
    def decorator(method):
        assert getattr(method, 'cascade.command', None) is None
        setattr(method, 'cascade.command', (args, kwargs))
        setattr(method, 'cascade.value', True)
        assert getattr(method, 'cascade.command', None) is not None
        return method
    return decorator

def option(*args, **kwargs):
    def decorator(method):
        inner = getattr(method, 'cascade.parameters', fn.identity)
        outer = fn.compose(click.option(*args, **kwargs), inner)
        setattr(method, 'cascade.parameters', outer)
        return method
    return decorator

def argument(*args, **kwargs):
    def decorator(method):
        inner = getattr(method, 'cascade.parameters', fn.identity)
        outer = fn.compose(click.argument(*args, **kwargs), inner)
        setattr(method, 'cascade.parameters', outer)
        return method
    return decorator

def value():
    def decorator(method):
        setattr(method, 'cascade.value', True)
        return method
    return decorator
