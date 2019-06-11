"""The command-line application."""

import functools
import subprocess

import click
from toolz.functoolz import compose  # type: ignore

from cupcake import cmake, conan


@click.group(context_settings={'help_option_names': ('--help', '-h')})
@click.version_option()
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

_build_dir_option = click.option( # pylint: disable=invalid-name
    '--dir',
    'build_dir_prefix',
    type=click.Path(),
    default='.build',
    help='The build directory.',
)

# Modeled after `./configure --prefix`.
_install_dir_option = click.option( # pylint: disable=invalid-name
    '--prefix',
    'install_dir_prefix',
    type=click.Path(),
    default='.install',
    help='The installation prefix.',
)

_config_option = compose( # pylint: disable=invalid-name
    # These must be composed in this order,
    # because `flag_value` sets the default to `False`.
    click.option(
        '--debug',
        'config',
        flag_value='debug',
        help='Shorthand for --config debug.',
    ),
    click.option(
        '--release',
        'config',
        flag_value='release',
        help='Shorthand for --config release.',
    ),
    click.option(
        '-c',
        '--config',
        type=_CONFIG_CHOICES,
        callback=lambda ctx, param, value: cmake.BuildConfiguration.lookup(value),
        default=_DEFAULT_CONFIG,
        help='The build configuration.',
    ),
)


@main.command()
@_build_dir_option
@_install_dir_option
def clean(build_dir_prefix, install_dir_prefix):
    """Remove the build and install directories."""
    project = conan.Conan.construct(
        build_dir_prefix=build_dir_prefix,
        install_dir_prefix=install_dir_prefix,
    )
    project.clean()


@main.command()
@_build_dir_option
@_install_dir_option
@click.option(
    '-g', '--generator', 'generator', default=cmake.CMake.DEFAULT_GENERATOR
)
@_config_option
@click.option(
    '-f',
    '--force/--no-force',
    default=False,
    help='Reconfigure even if everything appears up-to-date.',
)
@click.option(
    '-D',
    'definitions',
    multiple=True,
    metavar='NAME[=VALUE]',
    help='CMake variable definitions.',
)  # pylint: disable=too-many-arguments
@click.argument('cmake_args', nargs=-1)
@_hide_stack_trace()
def configure(
    build_dir_prefix,
    install_dir_prefix,
    generator,
    config: cmake.BuildConfiguration,
    force,
    definitions,
    cmake_args,
):
    """Configure the build directory."""
    project = conan.Conan.construct(
        build_dir_prefix=build_dir_prefix,
        install_dir_prefix=install_dir_prefix,
        generator=generator,
    )
    if any(d.startswith('CMAKE_INSTALL_PREFIX') for d in definitions):
        raise click.BadParameter(
            'Please use --prefix instead of -DCMAKE_INSTALL_PREFIX.'
        )
    project.configure(
        config,
        *(f'-D{d}' for d in definitions),
        *cmake_args,
        force=force,
    )


@main.command()
@_build_dir_option
@_config_option
@_hide_stack_trace()
def build(build_dir_prefix, config):
    """Build the project."""
    project = conan.Conan.construct(build_dir_prefix=build_dir_prefix)
    project.build(config)


@main.command()
@_build_dir_option
@_config_option
@_hide_stack_trace()
@click.argument('ctest_args', nargs=-1)
def test(build_dir_prefix, config, ctest_args):
    """Test the project."""
    project = conan.Conan.construct(build_dir_prefix=build_dir_prefix)
    project.test(config, *ctest_args)


@main.command()
@_build_dir_option
@_install_dir_option
@_config_option
@_hide_stack_trace()
def install(build_dir_prefix, install_dir_prefix, config):
    """Install the project."""
    project = conan.Conan.construct(
        build_dir_prefix=build_dir_prefix,
        install_dir_prefix=install_dir_prefix,
    )
    project.install(config)


@main.command()
@_hide_stack_trace()
def package():
    """Package the project."""
    project = conan.Conan.construct()
    project.package()
    # TODO: Test package.
