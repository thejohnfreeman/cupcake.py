"""The command-line application."""

import functools
import logging
from pathlib import Path
import subprocess

import click
from toolz.functoolz import compose  # type: ignore

from cupcake.config import Configuration, GENERATOR_ALIASES
from cupcake.cmake import CMake
from cupcake.conan import Conan


def _hide_stack_trace():
    """Hide the stack trace of a ``CalledProcessError``."""

    def decorator(f):

        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except subprocess.CalledProcessError as cause:
                raise SystemExit(cause.returncode)

        return wrapped

    return decorator


@click.group(context_settings={'help_option_names': ('--help', '-h')})
@click.option('-v', '--verbose', count=True)
@click.option('-q', '--quiet', count=True)
@click.version_option()
def main(verbose, quiet):
    logging.basicConfig(level=(3 - verbose + quiet) * 10)
    pass


_DEFAULT_CONFIGURATION = {
    'configure_source_directory': '.',
    'configure_build_directory': '.build',
    'configure_generator': 'Ninja',
    'configure_flavor': 'debug',
    'configure_shared': False,
    'install_prefix': '.install',
}


_configure_source_directory_option = click.option( # pylint: disable=invalid-name
    '--source-directory',
    'configure_source_directory',
    type=click.Path(exists=True),
    default=_DEFAULT_CONFIGURATION['configure_source_directory'],
    help='The source directory.',
)

_configure_build_directory_option = click.option( # pylint: disable=invalid-name
    '-d',
    '--build-directory',
    'configure_build_directory',
    type=click.Path(),
    default=_DEFAULT_CONFIGURATION['configure_build_directory'],
    help='The build directory.',
)

_configure_generator_option = click.option( # pylint: disable=invalid-name
    '-g',
    '--generator',
    'configure_generator',
    type=click.Choice(GENERATOR_ALIASES.keys(), case_sensitive=False),
    default=_DEFAULT_CONFIGURATION['configure_generator'],
    help='The build system generator.',
)

_configure_flavor_option = compose( # pylint: disable=invalid-name
    click.option(
        '--debug',
        'configure_flavor',
        flag_value='debug',
        help='Shorthand for --flavor debug.',
    ),
    click.option(
        '--release',
        'configure_flavor',
        flag_value='release',
        help='Shorthand for --flavor release.',
    ),
    # This must be composed last
    # because `flag_value` sets the default to `False`.
    click.option(
        '--flavor',
        'configure_flavor',
        default=_DEFAULT_CONFIGURATION['configure_flavor'],
        help='The configuration flavor.',
    ),
)

_configure_shared_option = compose( # pylint: disable=invalid-name
    click.option(
        '--shared',
        'configure_shared',
        flag_value=True,
        help='Build shared libraries.',
    ),
    click.option(
        '--static',
        'configure_shared',
        flag_value=False,
        help='Build static libraries.',
    ),
)

_configure_definitions_option = click.option(
    '-D',
    'configure_definitions',
    multiple=True,
    metavar='NAME[=VALUE]',
    help='CMake variable definitions.',
)

_configure_options = compose(
    _configure_source_directory_option,
    _configure_build_directory_option,
    _configure_generator_option,
    _configure_flavor_option,
    _configure_shared_option,
    _configure_definitions_option,
)


@main.command()
@_configure_options
@_hide_stack_trace()
def configure(
    *,
    configure_source_directory,
    configure_build_directory,
    configure_generator,
    configure_flavor,
    configure_shared,
    configure_definitions,
    **kwargs,
):
    """Configure the build."""
    configuration = Configuration.from_all(
        source_directory=configure_source_directory,
        build_directory=configure_build_directory,
        generator=configure_generator,
        flavor=configure_flavor,
        shared=configure_shared,
        definitions=configure_definitions,
    )
    logging.debug(configuration)
    cupcake = Conan(configuration)
    cupcake.configure()
    return cupcake


_build_options = compose(_configure_options)


@main.command()
@_build_options
@click.pass_context
@_hide_stack_trace()
def build(context, **kwargs):
    """Build the package."""
    cupcake = context.forward(configure)
    cupcake.build()
    return cupcake


@main.command()
@_build_options
@click.argument('targets', nargs=-1)
@click.pass_context
@_hide_stack_trace()
def test(context, targets, **kwargs):
    """Build and execute the tests."""
    cupcake = context.forward(configure)
    cupcake.build(targets)
    cupcake.test()
    return cupcake


_install_prefix_option = click.option( # pylint: disable=invalid-name
    '-p',
    '--prefix',
    'install_prefix',
    type=click.Path(),
    default=_DEFAULT_CONFIGURATION['install_prefix'],
    help='The installation prefix. A relative path is taken relative to the source directory.',
)

_install_options = compose(
    _build_options,
    _install_prefix_option,
)


@main.command()
@_install_options
@click.pass_context
@_hide_stack_trace()
def install(context, *, install_prefix, **kwargs):
    """Install the package."""
    cupcake = context.forward(configure)
    cupcake.build()
    cupcake.install(prefix=install_prefix)


@main.command()
@_build_options
@click.argument('target')
@click.argument('arguments', nargs=-1)
@click.pass_context
@_hide_stack_trace()
def run(context, target, arguments, **kwargs):
    """Run an executable target."""
    cupcake = context.forward(configure)
    cupcake.build([target])
    cupcake.run(target, arguments)
