"""The command-line application."""

import click
from cupcake import cmake


@click.group()
def main():
    pass


@main.command()
def package():
    build_system = cmake.CMake()
    print(f'version = {build_system.version()}')
