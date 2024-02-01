import pytest
import shush
import tempfile

def pytest_addoption(parser):
    # TODO: Take default version from library.
    parser.addoption('--cupcake', action='store', default='0.6.0')

@pytest.fixture(scope='session')
def version(request):
    return request.config.option.cupcake

@pytest.fixture()
def sh():
    with tempfile.TemporaryDirectory() as cwd:
        yield shush.Shell() @ cwd
