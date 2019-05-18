"""A build-system abstraction for CMake."""

# At first, we only have time to support CMake. In the future, we might want
# to support other build systems. It seems unlikely now, but just keep it in
# mind as you design this abstraction. Only add methods that other parts of
# Cupcake need.

import re
from semantic_version import Version

# project(project_template VERSION 0.1.0 LANGUAGES CXX)
_PROJECT_PATTERN = re.compile(r'^\s*project\s*\(', re.IGNORECASE)
_VERSION_ARGUMENT_PATTERN = re.compile(r'VERSION\s*([^ )]+)')


class CMake:
    def version(self) -> Version:
        """Return the version string from CMakeLists.txt

        Raises
        ------
        Exception
            If the version string cannot be found or is not a semantic version
            (major.minor.patch).
        """
        # We would love if CMake offered a way to pull the version from
        # a CMakeLists.txt without configuring the project, but alas.
        with open('CMakeLists.txt', 'r') as f:
            for lineno, line in enumerate(f):
                if not _PROJECT_PATTERN.match(line):
                    continue
                match = _VERSION_ARGUMENT_PATTERN.search(line)
                if not match:
                    raise Exception(
                        f'could not find version argument on line {lineno + 1}'
                    )
                version_string = match.group(1)
                try:
                    return Version(version_string)
                except ValueError:
                    raise Exception(
                        f'VERSION argument is not a semantic version string: {version_string}'
                    )
        raise Exception('could not find project command in CMakeLists.txt')
