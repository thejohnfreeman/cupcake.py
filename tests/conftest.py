import pathlib
import pytest
import shush
import tempfile

def pytest_addoption(parser):
    # TODO: Take default version from library.
    parser.addoption('--cupcake', action='store', default='0.7.0')

@pytest.fixture(scope='session')
def version(request):
    return request.config.option.cupcake

@pytest.fixture()
def cwd():
    with tempfile.TemporaryDirectory() as cwd:
        yield pathlib.Path(cwd)

@pytest.fixture()
def sh(cwd):
    return shush.Shell() @ cwd
