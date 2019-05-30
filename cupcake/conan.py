"""Conan as a package manager for CMake."""

import os
from pathlib import Path
import typing as t

from cupcake.cmake import CMake


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

    def configure(self, *args):
        """Install dependencies and configure with CMake."""
        os.makedirs(self.build_dir, exist_ok=True)

        # conaninfo.txt is modified on every install.
        ci = self.build_dir / 'conaninfo.txt'
        cf = conanfile(self.source_dir)
        if cf.is_file(
        ) and (not ci.is_file() or cf.stat().st_mtime > ci.stat().st_mtime):
            self.shell.run(
                ['conan', 'install', self.source_dir],
                cwd=self.build_dir,
            )

        cmake_toolchain_file = self.build_dir / 'conan_paths.cmake'
        cmake_args = (
            [f'-DCMAKE_TOOLCHAIN_FILE={cmake_toolchain_file}']
            if cmake_toolchain_file.is_file() else []
        )
        super().configure(*args, *cmake_args)

    def package(self):
        self.shell.run(
            [
                'conan',
                'create',
                self.source_dir,
                f'{self.name}/{self.version}@demo/testing',
            ]
        )
