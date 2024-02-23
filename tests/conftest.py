import pathlib
import pytest
import shush
import tempfile

def pytest_addoption(parser):
    parser.addoption('--cupcake', action='store', default='alpha')

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
