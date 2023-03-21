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

def install(source_dir, install_dir):
    with tempfile.TemporaryDirectory() as build_dir:
        subprocess.check_call([
            'cupcake',
            'install',
            '-S',
            source_dir,
            '-B',
            build_dir,
            '--prefix',
            install_dir,
        ])

@pytest.fixture
def package_zero(install_dir):
    install(project_template_cpp / '00-upstream', install_dir)

def test_zero_installs(install_dir, package_zero):
    assert subprocess.check_output([install_dir / 'bin' / 'true']) == b''

@pytest.fixture
def package_one(install_dir, package_zero):
    install(project_template_cpp / '01-find-package', install_dir)

def test_one(install_dir, package_one):
    assert subprocess.check_output(
        [install_dir / 'bin' / 'hello']
    ) == b'hello!\n'

@pytest.fixture
def package_two(install_dir):
    install(project_template_cpp / '02-add-subdirectory', install_dir)

def test_two(install_dir, package_two):
    assert subprocess.check_output(
        [install_dir / 'bin' / 'goodbye']
    ) == b'goodbye!\n'

@pytest.fixture
def package_three(install_dir, package_one):
    install(project_template_cpp / '03-fp-fp', install_dir)

def test_three(install_dir, package_three):
    assert subprocess.check_output(
        [install_dir / 'bin' / 'aloha']
    ) == b'aloha!\n'

@pytest.fixture
def package_four(install_dir, package_two):
    install(project_template_cpp / '04-as-fp', install_dir)

def test_four(install_dir, package_four):
    assert subprocess.check_output([install_dir / 'bin' / 'four']) == b'4\n'

@pytest.fixture
def package_five(install_dir):
    install(project_template_cpp / '05-fetch-content', install_dir)

def test_five(install_dir, package_five):
    assert subprocess.check_output([install_dir / 'bin' / 'five']) == b'5!\n'
