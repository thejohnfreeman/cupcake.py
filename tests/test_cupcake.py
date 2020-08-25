from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def project_template_cpp():
    root = Path(__file__).parents[1]
    return root / 'submodules' / 'project-template-cpp'


def test_build(project_template_cpp, tmp_path):
    subprocess.check_call(
        [
            'cupcake',
            'build',
            '--source-directory',
            project_template_cpp,
            '--build-directory',
            tmp_path,
        ]
    )
    assert (tmp_path / 'debug' / 'src' / 'libgreetings.a').is_file()
    assert subprocess.check_output(
        [tmp_path / 'debug' / 'src' / 'greet']
    ) == b'hello!\n'


def test_test(project_template_cpp, tmp_path):
    subprocess.check_call(
        [
            'cupcake',
            'test',
            '--source-directory',
            project_template_cpp,
            '--build-directory',
            tmp_path,
        ]
    )


def test_install(project_template_cpp, tmp_path):
    prefix = tmp_path / 'install'
    subprocess.check_call(
        [
            'cupcake',
            'install',
            '--source-directory',
            project_template_cpp,
            '--build-directory',
            tmp_path / 'build',
            '--prefix',
            prefix,
        ]
    )
    subprocess.check_call(
        [
            'diff',
            project_template_cpp / 'include' / 'greetings' / 'greetings.hpp',
            prefix / 'include' / 'greetings' / 'greetings.hpp',
        ]
    )
    assert (prefix / 'lib' / 'libgreetings.a').is_file()
    assert subprocess.check_output([prefix / 'bin' / 'greet']) == b'hello!\n'
