"""The command-line application."""

import functools
import subprocess

import click
from toolz.functoolz import compose

from cupcake import conan


@click.group(context_settings={'help_option_names': ('--help', '-h')})
def main():
    pass


# A mapping from lowercase names to CMake names.
# TODO: When mypy updates after 0.701, we should be able to remove this `type:
# ignore`.
_CONFIG_CHOICES = click.Choice(  # type: ignore
    ('debug', 'release', 'minsizerel', 'relwithdebinfo'), case_sensitive=False
)
_DEFAULT_CONFIG = 'debug'


def _hide_stack_trace():
    """Hide the stack trace of a ``CalledProcessError``."""

    def decorator(f):

        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except subprocess.CalledProcessError as cause:
                raise SystemExit(cause.returncode)

        return wrapped

    return decorator


_config_option = compose( # pylint: disable=invalid-name
    # These must be composed in this order,
    # because `flag_value` sets the default to `False`.
    click.option('--debug', 'config', flag_value='debug'),
    click.option('--release', 'config', flag_value='release'),
    click.option(
        '-c', '--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG
    ),
)


@main.command()
def clean():
    """Remove the build and install directories."""
    project = conan.Conan.construct()
    project.clean()


@main.command()
@_config_option
@_hide_stack_trace()
def configure(config):
    """Configure the build directory."""
    project = conan.Conan.construct()
    project.configure(config)


@main.command()
@_config_option
@_hide_stack_trace()
def build(config):
    """Build the project."""
    project = conan.Conan.construct()
    project.build(config)


@main.command()
@_config_option
@_hide_stack_trace()
def test(config):
    """Test the project."""
    project = conan.Conan.construct()
    project.test(config)


@main.command()
@_config_option
@_hide_stack_trace()
def install(config):
    """Install the project."""
    project = conan.Conan.construct()
    project.install(config)


@main.command()
@_hide_stack_trace()
def package():
    """Package the project."""
    project = conan.Conan.construct()
    project.package()
    # TODO: Test package.
