"""
These tests all use the system Conan and the user's Conan cache.
Running them in parallel can create race conditions on the cache.
Be careful.
"""

# TODO: Create a module-scope, auto-use fixture that builds all Conan
# dependencies to eliminate any race condition on the cache.

import os
import pathlib
import pytest
import subprocess
import tempfile

# TODO: Better way to get this path?
root = pathlib.Path(__file__).parents[1]
project_template_cpp = root / 'submodules' / 'project-template-cpp'
try:
    os.symlink(
        project_template_cpp / '00-upstream',
        project_template_cpp / '02-add-subdirectory' / 'external' / '00-upstream',
    )
except FileExistsError:
    pass

@pytest.fixture
def install_dir():
    with tempfile.TemporaryDirectory() as path:
        yield pathlib.Path(path)

examples = [
    ('zero', '00-upstream', [], 'true', b''),
    ('one', '01-find-package', ['00-upstream'], 'hello', b'hello!\n'),
    ('two', '02-add-subdirectory', [], 'goodbye', b'goodbye!\n'),
    ('three', '03-fp-fp', ['00-upstream', '01-find-package'], 'aloha', b'aloha!\n'),
    ('four', '04-as-fp', ['02-add-subdirectory'], 'four', b'4\n'),
    ('five', '05-fetch-content', [], 'five', b'5!\n'),
    ('six', '06-fp-fc', ['00-upstream'], 'six', b'6!\n'),
    ('seven', '07-as-fc', [], 'seven', b'7!\n'),
    ('eight', '08-find-module', ['00-upstream'], 'eight', b'8!\n'),
    ('nine', '09-external-project', [], 'nine', b'9!\n'),
    ('ten', '10-conan', [], 'ten', b'10!\n'),
]

@pytest.mark.parametrize(
    ('subdirectory', 'dependencies', 'executable', 'output'),
    map(lambda args: pytest.param(*args[1:], id=args[0]), examples)
)
def test_package(subdirectory, dependencies, install_dir, executable, output):
    # Install any dependencies that must be installed.
    for dependency in dependencies:
        source_dir = project_template_cpp / dependency
        with tempfile.TemporaryDirectory() as build_dir:
            subprocess.check_call([
                'cupcake',
                'install',
                '--config',
                os.devnull,
                '-S',
                source_dir,
                '-B',
                build_dir,
                '--prefix',
                install_dir,
            ],
            stderr=subprocess.STDOUT)

    source_dir = project_template_cpp / subdirectory
    with tempfile.TemporaryDirectory() as build_dir:
        with tempfile.NamedTemporaryFile() as config:
            # Test the package tests.
            subprocess.check_call([
                'cupcake',
                'test',
                '--config',
                config.name,
                '-S',
                source_dir,
                '-B',
                build_dir,
                '-P',
                install_dir,
            ],
            stderr=subprocess.STDOUT)
            # Test the package installation.
            subprocess.check_call([
                'cupcake',
                'install',
                '--config',
                config.name,
                '-S',
                source_dir,
                '-B',
                build_dir,
                '--prefix',
                install_dir,
            ],
            stderr=subprocess.STDOUT)
    assert subprocess.check_output([install_dir / 'bin' / executable]) == output
