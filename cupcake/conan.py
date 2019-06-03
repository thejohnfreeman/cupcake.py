"""Conan as a package manager for CMake."""

import os
from pathlib import Path
import typing as t

from cupcake.cmake import CMake, BuildConfiguration
from cupcake.filesystem import is_modified_after


def conanfile(source_dir: Path) -> t.Optional[Path]:
    path = source_dir / 'conanfile.py'
    if path.is_file():
        return path
    path = source_dir / 'conanfile.txt'
    if path.is_file():
        return path
    return None


class Conan(CMake):
    # Conan needs to wrap CMake because it knows how to satisfy CMake's
    # assumptions.

    @classmethod
    def construct(cls, *, source_dir='.', **kwargs):  # pylint: disable=arguments-differ
        source_dir = Path(source_dir)
        if conanfile(source_dir) is None:
            return CMake.construct(**kwargs)
        return super(Conan, cls).construct(**kwargs)

    def configure(self, config: BuildConfiguration, *cmake_args, force=False):
        """Install dependencies and configure with CMake."""
        build_dir = self.build_dir(config)
        os.makedirs(build_dir, exist_ok=True)

        # conaninfo.txt is modified on every install.
        ci = build_dir / 'conaninfo.txt'
        cf = conanfile(self.source_dir)
        if cf is not None and not is_modified_after(ci, cf):
            self.shell.run(
                ['conan', 'install', self.source_dir],
                cwd=build_dir,
            )

        cmake_toolchain_file = build_dir / 'conan_paths.cmake'
        cmake_args_conan = (
            [f'-DCMAKE_TOOLCHAIN_FILE={cmake_toolchain_file}']
            if cmake_toolchain_file.is_file() else []
        )
        super().configure(config, *cmake_args_conan, *cmake_args, force=force)

    def package(self):
        self.shell.run(
            [
                'conan',
                'create',
                self.source_dir,
                f'{self.name}/{self.version}@demo/testing',
            ]
        )
