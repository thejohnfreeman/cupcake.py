import os
import pytest
import subprocess
import tempfile

@pytest.fixture(scope='session', params=[True, False])
def special(request):
    return request.param

@pytest.fixture(scope='session', params=[True, False])
def library(request):
    return request.param

@pytest.fixture(scope='session', params=[True, False])
def executable(request):
    return request.param

@pytest.fixture(scope='session', params=[True, False])
def tests(request):
    return request.param

def test_new(sh, special, library, executable, tests):
    args = []
    env = dict(os.environ)
    if not special:
        args.append('--general')
        env.update({'CUPCAKE_NO_SPECIAL': '1'})
    if not library:
        args.append('--no-library')
    if not executable:
        args.append('--no-executable')
    if not tests:
        args.append('--no-tests')
    sh> sh.cupcake('new', 'foo', *args).env(env)
    sh = sh @ 'foo'
    command = 'test' if tests else 'exe' if executable else 'build'
    sh> sh.cupcake(command)
    sh> sh.cupcake('install')
