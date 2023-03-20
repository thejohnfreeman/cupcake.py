import pathlib
import pytest
import subprocess
import tempfile

@pytest.fixture
def project_template_cpp():
    # TODO: Better way to get this path?
    root = pathlib.Path(__file__).parents[1]
    return root / 'submodules' / 'project-template-cpp'

@pytest.fixture
def build_dir():
    with tempfile.TemporaryDirectory() as path:
        yield pathlib.Path(path)

@pytest.fixture
def install_dir():
    with tempfile.TemporaryDirectory() as path:
        yield pathlib.Path(path)

def test_zero(project_template_cpp, build_dir, install_dir):
    subprocess.check_call([
        'cupcake',
        'install',
        '-S',
        project_template_cpp / '00-upstream',
        '-B',
        build_dir,
        '--prefix',
        install_dir,
    ])
    assert subprocess.check_output([install_dir / 'bin' / 'true']) == b''
