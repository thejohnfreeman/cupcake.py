"""A build-system abstraction for CMake."""

# At first, we only have time to support CMake. In the future, we might want
# to support other build systems. It seems unlikely now, but just keep it in
# mind as you design this abstraction. Only add methods that other parts of
# Cupcake need.

from cached_property import cached_property
import cmakelists_parsing.parsing as cmp
from semantic_version import Version

# It would be easier for us to keep package metadata in a more readable file,
# but that would require users to move their metadata to that file (from
# `CMakeLists.txt`) and then read it from within `CMakeLists.txt`, which does
# not have parsing utilities as capable or convenient as those in Python. We
# will bear the burden of parsing `CMakeLists.txt` for the user's convenience.


class CMake:
    @cached_property
    def _ast(self):
        # We would love an easier way to pull metadata from CMakeLists.txt
        # without parsing it, but alas. Sadly, we do not see through
        # ``include``s.
        with open('CMakeLists.txt', 'r') as f:
            return cmp.parse(f.read())

    @cached_property
    def _project(self):
        for command in self._ast:
            # All the AST node types have predictable names except `_Command`
            # and `_Arg`.
            if not isinstance(command, cmp._Command):
                continue
            if command.name.lower() == 'project':
                return command
        raise Exception('could not find `project` command in CMakeLists.txt')

    # TODO: Separate the build system abstraction from the package metadata
    # abstraction.
    # TODO: Parse CMakeLists.txt with the cmakelists_parsing package.
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
        for i, arg in enumerate(args):
            if arg.contents == 'VERSION':
                version_string = args[i + 1].contents
                try:
                    return Version(version_string)
                except ValueError:
                    raise Exception(
                        f'`VERSION` argument is not a semantic version string: {version_string}'
                    )
        raise Exception(
            '`VERSION` argument missing from `project` command in CMakeLists.txt'
        )
