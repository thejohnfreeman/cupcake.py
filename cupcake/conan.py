"""Conan as a package manager for CMake."""

import logging
import os
import tempfile

from cached_property import cached_property

from cupcake.cmake import CMake
from cupcake import filesystem


class Conan(CMake):

    def conanfile(self):
        return self.configuration.source_directory / 'conanfile.txt'

    def conan_configuration_changed(self):
        conaninfo = self.build_directory / 'conaninfo.txt'
        try:
            toolchain_time = conaninfo.stat().st_mtime
        except FileNotFoundError:
            logging.debug(f'missing Conan cache file: {conaninfo}')
            return True
        if self.conanfile.stat().st_mtime > toolchain_time:
            logging.debug(f'changed Conan configuration: {self.conanfile}')
            return True
        return False

    @cached_property
    def conan_toolchain_file(self):
        if self.force or self.conan_configuration_changed():
            self.shell.run(
                [
                    'conan',
                    'install',
                    self.configuration.source_directory,
                    '--settings',
                    f'build_type={self.configuration.flavor.value}',
                    '--build',
                    'missing',
                ]
            )
        return self.cmake_directory / 'conan_paths.cmake'

    @cached_property
    def cmake_toolchain_file(self):
        super().cmake_toolchain_file
        self.conan_toolchain_file
        # Because we don't have sub-second resolution on modification times,
        # we need a file that never existed to track whether we have already
        # merged the CMake and Conan toolchain files.
        path = self.cmake_directory / 'merged_toolchain.cmake'
        if not path.is_file():
            with path.open('w') as file:
                print(
                    'include(${CMAKE_CURRENT_LIST_DIR}/toolchain.cmake)',
                    file=file
                )
                # The Conan generator cmake_find_package installs Find Modules
                # in the current directory, but does not add that directory to
                # the CMAKE_MODULE_PATH it defines in conan_paths.cmake.
                # We must pass it ourselves.
                print(
                    f'set(CMAKE_MODULE_PATH, {self.cmake_directory})',
                    file=file
                )
                # The Conan generator cmake_find_package_multi installs
                # Package Configuration Files in the current directory, but
                # does not add that directory to the CMAKE_PREFIX_PATH it
                # defines in conan_paths.cmake. We must pass it ourselves.
                print(
                    f'set(CMAKE_PREFIX_PATH, {self.cmake_directory})',
                    file=file
                )
                print(
                    'include(${CMAKE_CURRENT_LIST_DIR}/conan_paths.cmake)',
                    file=file
                )
        return path
