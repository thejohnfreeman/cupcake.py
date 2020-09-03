"""A build-system abstraction for CMake.

One instance is one build configuration, known at construction.
I've never had a use case where I was interested in building multiple
configurations simultaneously.
Either I'm testing or debugging or I'm benchmarking or publishing.
Using this lowest common denominator lets us support more build systems
more naturally, without wasting work on unused configurations.

Each phase is separate and no phase may call another.
One layer (e.g. Conan) may want to compose with another (e.g. CMake) but
with different parameters or even different phases.

A build flavor is a starting set of configuration settings.
"""

# At first, we only have time to support CMake. In the future, we might want
# to support other build systems. It seems unlikely now, but just keep it in
# mind as you design this abstraction. Only add methods that other parts of
# Cupcake need.

import logging
import os
import multiprocessing
from pathlib import Path
import subprocess

from cached_property import cached_property

from cupcake import filesystem
from cupcake.project import Cupcake
from cupcake.shell import Shell


class CMake(Cupcake):

    @cached_property
    def cmake_directory(self):
        # TODO: Support multi-config generators.
        return self.build_directory / self.configuration.flavor.value

    @cached_property
    def shell(self):
        return Shell(
            cwd=self.cmake_directory,
            env={
                **os.environ,
                'CMAKE_BUILD_PARALLEL_LEVEL':
                str(multiprocessing.cpu_count()),
            },
        )

    @cached_property
    def cmake_toolchain_file(self):
        path = self.cmake_directory / 'toolchain.cmake'
        if not path.is_file():
            os.makedirs(self.cmake_directory, exist_ok=True)
            with path.open('w') as file:
                # `CMAKE_EXPORT_COMPILE_COMMANDS` should be on by default.
                print('set(CMAKE_EXPORT_COMPILE_COMMANDS ON)', file=file)
                # TODO: Only if single-config generator?
                print(
                    f'set(CMAKE_BUILD_TYPE {self.configuration.flavor.value})',
                    file=file
                )
                for name, value in self.configuration.definitions:
                    print(f'set({name} {value})', file=file)
        return path

    DEFAULT_ARGS = [
        # Enable developer warnings.
        '-W',
        'dev',
        # Enable deprecation warnings.
        '-W',
        'deprecated',
        # All variables are effectively initialized to the empty string.
        # '--warn-uninitialized',
        # Most (automatic) variables go unused. Do not warn about them.
        # '--warn-unused-vars',
    ]

    def cmake_configuration_changed(self):
        # Search recursively for all `CMakeLists.txt` and `*.cmake`.
        # Return `True` if any modified after build_directory / `CMakeCache.txt`.
        path = self.cmake_directory / 'CMakeCache.txt'
        try:
            configure_time = path.stat().st_mtime
        except FileNotFoundError:
            logging.debug(f'missing CMake cache file: {path}')
            return True
        for prefix, filename in filesystem.find(
            self.configuration.source_directory,
            self.configuration.build_directory
        ):
            if filename == 'CMakeLists.txt' or filename.endswith('.cmake'):
                path = prefix / filename
                if path.stat().st_mtime > configure_time:
                    logging.debug(f'changed CMake configuration: {path}')
                    return True
        return False

    def configure(self, args=tuple()):
        if not self.force and not self.cmake_configuration_changed():
            return

        # TODO: Acquire file lock?

        if self.cmake_directory != self.configuration.build_directory:
            try:
                os.unlink(
                    self.configuration.build_directory / 'compile_commands.json'
                )
            except FileNotFoundError:
                pass
            os.symlink(
                self.cmake_directory.relative_to(self.build_directory) /
                'compile_commands.json',
                self.configuration.build_directory / 'compile_commands.json'
            )

        self.shell.run(
            [
                'cmake',
                *CMake.DEFAULT_ARGS,
                '-G',
                self.configuration.generator.value,
                f'-DCMAKE_TOOLCHAIN_FILE={self.cmake_toolchain_file}',
                *args,
                self.configuration.source_directory,
            ]
        )
        (self.cmake_directory / 'CMakeCache.txt').touch()

    def build(self, targets=tuple()):
        targets_args = ['--target', *targets] if targets else tuple()
        self.shell.run(
            [
                'cmake',
                '--build',
                self.cmake_directory,
                # TODO: Add this option only if generator is multi-config?
                '--config',
                self.configuration.flavor.value,
                '--parallel',
                multiprocessing.cpu_count(),
                *targets_args,
            ]
        )

    def test(self):
        self.shell.run(
            [
                'cmake',
                '--build',
                self.cmake_directory,
                # TODO: Add this option only if generator is multi-config?
                '--config',
                self.configuration.flavor.value,
                '--parallel',
                multiprocessing.cpu_count(),
                '--target',
                'test',
            ]
        )

    def install(self, prefix):
        self.shell.run(
            [
                'cmake',
                '--install',
                self.cmake_directory,
                # TODO: Add this option only if generator is multi-config?
                '--config',
                self.configuration.flavor.value,
                '--prefix',
                self.configuration.source_directory / prefix,
            ]
        )

    def run(self, target: str, arguments):
        subprocess.run([self.cmake_directory / 'bin' / target, *arguments])
