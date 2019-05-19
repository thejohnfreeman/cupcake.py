"""The command-line application."""

import click
from cupcake import cmake
import subprocess as sh


@click.group()
def main():
    pass


@main.command()
def package():
    """Package the project"""
    package = cmake.CMake()
    sh.run(
        [
            'conan', 'create', '.',
            f'{package.name}/{package.version}@demo/testing'
        ],
        check=True,
    )
    # TODO: Test package.
