"""A build-system abstraction for CMake."""

# At first, we only have time to support CMake. In the future, we might want
# to support other build systems. It seems unlikely now, but just keep it in
# mind as you design this abstraction. Only add methods that other parts of
# Cupcake need.

from dataclasses import dataclass
from enum import Enum
import os
import multiprocessing
from pathlib import Path
import platform
import shutil
import typing as t

from cached_property import cached_property  # type: ignore
import cmakelists_parsing.parsing as cmp  # type: ignore
from semantic_version import Version  # type: ignore

from cupcake.filesystem import is_modified_before
from cupcake.shell import Shell

# It would be easier for us to keep package metadata in a more readable file,
# but that would require users to move their metadata to that file (from
# `CMakeLists.txt`) and then read it from within `CMakeLists.txt`, which does
# not have parsing utilities as capable or convenient as those in Python. We
# will bear the burden of parsing `CMakeLists.txt` for the user's convenience.


class GeneratorConfiguration(Enum):
    """A generator configuration (aka build type)."""
    DEBUG = 'Debug'
    RELEASE = 'Release'
    MIN_SIZE_REL = 'MinSizeRel'
    REL_WITH_DEB_INFO = 'RelWithDebInfo'

    _lookup_table = {
        'debug': DEBUG,
        'release': RELEASE,
        'minsizerel': MIN_SIZE_REL,
        'relwithdebinfo': REL_WITH_DEB_INFO,
    }

    @staticmethod
    def lookup(name):
        return GeneratorConfiguration._lookup_table[name.lower()]


_PathLike = t.Union[str, Path]


def _config_sub_dir(config: GeneratorConfiguration):
    # If we have a multi-configuration generator, we can put all of them in
    # one build directory / solution, and users expect that.
    # If we have a single-configuration generator, we want to manage multiple
    # configuration directories on behalf of the user.
    # This branch affects our build and install directories.
    return config if platform.system() == 'Linux' else ''


@dataclass
class CMake:

    source_dir: Path
    build_dir_prefix: Path
    install_dir_prefix: Path
    generator: t.Optional[str]
    shell: Shell = Shell()

    def build_dir(self, config) -> Path:
        return self.build_dir_prefix / _config_sub_dir(config)

    def install_dir(self, config) -> Path:
        return self.install_dir_prefix / _config_sub_dir(config)

    # TODO: Set options from command-line arguments, environment, and
    # configuration file.
    @classmethod
    def construct( # pylint: disable=too-many-arguments
        cls, *,
        source_dir: _PathLike = os.getcwd(),
        build_dir_prefix: _PathLike = '.build',
        install_dir_prefix: _PathLike = '.install',
        generator: str = None,
    ):
        # Use whatever default generator CMake chooses, unless it is Linux, in
        # which case choose the better default (Ninja over Make).
        if generator is None:
            if platform.system() == 'Linux':
                generator = 'Ninja'

        return cls(
            source_dir=Path(source_dir),
            build_dir_prefix=Path(build_dir_prefix),
            install_dir_prefix=Path(install_dir_prefix),
            generator=generator,
        )

    def clean(self):
        """Remove the build and install directories."""
        shutil.rmtree(self.build_dir_prefix, ignore_errors=True)
        shutil.rmtree(self.install_dir_prefix, ignore_errors=True)

    def configure(self, config, *args):
        """Configure the build directory."""
        build_dir = self.build_dir(config)
        install_dir = self.install_dir(config)

        if (build_dir / 'CMakeCache.txt').is_file():
            # Depend on CMake to reconfigure itself.
            # TODO: Will it? Fill the gaps.
            return

        os.makedirs(build_dir, exist_ok=True)
        # `FutureInstallDirs` expects the installation directory to exist.
        os.makedirs(install_dir, exist_ok=True)
        if platform.system() == 'Linux':
            os.makedirs(install_dir / 'lib/cmake', exist_ok=True)

        # yapf output is critically wrong when a comma appears in an expression in
        # an f-string.
        cmake_configuration_types = ','.join(
            c.name for c in GeneratorConfiguration
        )
        # TODO: Invoke CMake to determine the default generator? Look up in
        # a known list to judge if it is single- or multi- configuration?
        config_arg = (
            f'-DCMAKE_BUILD_TYPE={config}'
            if platform.system() in ('Linux', 'Darwin') else
            f'-DCMAKE_CONFIGURATION_TYPES={cmake_configuration_types}'
        )
        self.shell.run(
            [
                'cmake',
                # There is no long option for `-G`.
                '-G',
                self.generator,
                # We get a warning if we pass `CMAKE_CONFIGURATION_TYPES` to
                # a single-configuration generator.
                config_arg,
                # `CMAKE_EXPORT_COMPILE_COMMANDS` should be on by default.
                '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                # `CMAKE_INSTALL_PREFIX` is relative to the build directory.
                f'-DCMAKE_INSTALL_PREFIX={install_dir.resolve()}',
                *args,
                self.source_dir,
            ],
            cwd=build_dir,
        )

    def build(self, config):
        """Build the project."""
        self.configure(config)
        self.shell.run(
            [
                'cmake',
                '--build',
                '.',
                '--config',
                config,
                '--parallel',
                multiprocessing.cpu_count(),
            ],
            cwd=self.build_dir(config),
        )

    def test(self, config):
        """Test the project."""
        self.configure(config)
        self.shell.run(
            [
                'ctest',
                '--build-config',
                config,
                '--parallel',
                multiprocessing.cpu_count(),
            ],
            cwd=self.build_dir(config),
        )

    def install(self, config):
        """Install the project."""
        self.configure(config)
        self.shell.run(
            ['cmake', '--build', '.', '--target', 'install'],
            cwd=self.build_dir(config),
        )

    # TODO: Separate the build system abstraction from the package metadata
    # abstraction.
    @property
    def name(self) -> str:
        """Return the package name from ``CMakeLists.txt``.

        Raises
        ------
        Exception
            If there is no ``project`` command in ``CMakeLists.txt``. Do not
            hide it behind an ``include``!
        """
        return self._project.body[0].contents

    @property
    def version(self) -> Version:
        """Return the version string from ``CMakeLists.txt``.

        Raises
        ------
        Exception
            If the version string cannot be found or is not a semantic version
            (major.minor.patch).
        """
        args = self._project.body
        for index, arg in enumerate(args):
            if arg.contents == 'VERSION':
                version_string = args[index + 1].contents
                try:
                    return Version(version_string)
                except ValueError:
                    raise Exception(
                        f'`VERSION` argument is not a semantic version string: {version_string}'
                    )
        raise Exception(
            '`VERSION` argument missing from `project` command in CMakeLists.txt'
        )

    @cached_property
    def _ast(self):
        """Return an AST of the top-level ``CMakeLists.txt``.

        We would love an easier way to pull metadata from CMakeLists.txt
        without parsing it, but alas. Sadly, our parser does not evaluate
        ``include``s.
        """
        with open(self.source_dir / 'CMakeLists.txt', 'r') as f:
            return cmp.parse(f.read())

    @cached_property
    def _project(self):
        """Return the AST of the ``project`` command."""
        for command in self._ast:
            # All the AST node types have predictable names except `_Command`
            # and `_Arg`.
            if not isinstance(command, cmp._Command):  # pylint: disable=protected-access
                continue
            if command.name.lower() == 'project':
                return command
        raise Exception('could not find `project` command in CMakeLists.txt')
