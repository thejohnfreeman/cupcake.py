"""Conan as a package manager for CMake."""

import os
from pathlib import Path

from cupcake.cmake import CMake


# TODO: Decorate/inherit CMake.
class Conan(CMake):

    @classmethod
    def construct(cls, *, source_dir='.', **kwargs):  # pylint: disable=arguments-differ
        source_dir = Path(source_dir)
        if (
            not (source_dir / 'conanfile.txt').is_file() and
            not (source_dir / 'conanfile.py').is_file()
        ):
            return CMake.construct(**kwargs)
        return super(Conan, cls).construct(**kwargs)

    def configure(self, *args):
        """Install dependencies and configure with CMake."""
        os.makedirs(self.build_dir, exist_ok=True)

        # TODO: Compose CMake and Conan into a larger ProjectManager.
        # Conan needs to wrap CMake because it knows how to satisfy CMake's
        # assumptions.
        self.shell.run(
            ['conan', 'install', self.source_dir],
            cwd=self.build_dir,
        )
        cmake_toolchain_file = self.build_dir / 'conan_paths.cmake'
        super().configure(
            *args, f'-DCMAKE_TOOLCHAIN_FILE={cmake_toolchain_file}'
        )

    def package(self):
        self.shell.run(
            [
                'conan',
                'create',
                self.source_dir,
                f'{self.name}/{self.version}@demo/testing',
            ]
        )
