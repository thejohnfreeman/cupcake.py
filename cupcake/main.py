"""The command-line application."""

import subprocess as sh

import click
from cupcake import conan


@click.group(context_settings={'help_option_names': ('--help', '-h')})
def main():
    pass


# A mapping from lowercase names to CMake names.
_CONFIG_CHOICES = click.Choice(('debug', 'release'), case_sensitive=False)
_DEFAULT_CONFIG = 'debug'


@main.command()
def clean():
    """Remove the build and install directories."""
    project = conan.Conan.construct()
    project.clean()


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
def configure(config):
    """Configure the build directory."""
    project = conan.Conan.construct(config=config)
    project.configure()


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
def build(config):
    """Build the project."""
    project = conan.Conan.construct(config=config)
    project.build()


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
def test(config):
    """Test the project."""
    project = conan.Conan.construct(config=config)
    project.test()


@main.command()
@click.option('--config', type=_CONFIG_CHOICES, default=_DEFAULT_CONFIG)
def install(config):
    """Install the project."""
    project = conan.Conan.construct(config=config)
    project.install()


@main.command()
def package():
    """Package the project."""
    project = conan.Conan.construct()
    project.package()
    # TODO: Test package.
