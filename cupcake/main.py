"""The command-line application."""

import functools
import subprocess

import click

from cupcake import conan


@click.group(context_settings={'help_option_names': ('--help', '-h')})
def main():
    pass


# A mapping from lowercase names to CMake names.
# TODO: When mypy updates after 0.701, we should be able to remove this `type:
# ignore`.
_CONFIG_CHOICES = click.Choice(  # type: ignore
    ('debug', 'release'), case_sensitive=False
)
_DEFAULT_CONFIG = 'debug'


def echoes():
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


@main.command()
def clean():
    """Remove the build and install directories."""
    project = conan.Conan.construct()
    project.clean()


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
@echoes()
def configure(config):
    """Configure the build directory."""
    project = conan.Conan.construct()
    project.configure(config)


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
@echoes()
def build(config):
    """Build the project."""
    project = conan.Conan.construct()
    project.build(config)


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
@echoes()
def test(config):
    """Test the project."""
    project = conan.Conan.construct()
    project.test(config)


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
@echoes()
def install(config):
    """Install the project."""
    project = conan.Conan.construct()
    project.install(config)


@main.command()
@echoes()
def package():
    """Package the project."""
    project = conan.Conan.construct()
    project.package()
    # TODO: Test package.
