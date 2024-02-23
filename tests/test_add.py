from importlib import resources
import os
import pytest
import subprocess
import shutil

@pytest.mark.parametrize('reference', [
    'fmt', 'fmt@', 'fmt/10.2.1', 'fmt/10.2.1@',
])
@pytest.mark.parametrize(['src', 'dst', 'command', 'group'], [
    ('fmt.test.cpp', 'foo/tests/foo.cpp', 'test', 'test'),
    ('fmt.executable.cpp', 'foo/src/foo.cpp', 'exe', 'main'),
])
def test_add_requirement(cwd, sh, reference, src, dst, command, group):
    sh> sh.cupcake('new', 'foo', '--no-library')
    sh = sh @ 'foo'
    source = resources.as_file(
        resources.files('tests')
        .joinpath('data')
        .joinpath(src)
    )
    os.unlink(cwd / dst)
    with source as source:
        shutil.copy(source, cwd / dst)
    with pytest.raises(subprocess.CalledProcessError):
        sh> sh.cupcake(command)
    sh> sh.cupcake('add', reference, '--group', group)
    sh> sh.cupcake(command)
    sh> sh.cupcake('remove', 'fmt')
    with pytest.raises(subprocess.CalledProcessError):
        sh> sh.cupcake(command)
    with pytest.raises(subprocess.CalledProcessError):
        sh> sh.cupcake('remove', 'fmt')

@pytest.mark.parametrize('kind', ['lib'])
def test_add_target(sh, kind):
    sh> sh.cupcake('new', 'foo')
    sh = sh @ 'foo'
    sh> sh.cupcake('build')
    sh> sh.cupcake('test')
    proc = sh.here> sh.cupcake('list') | sh.wc('-l')
    assert(proc.stdout == b'3\n')

    sh> sh.cupcake(f'add:{kind}', 'bar')
    sh> sh.cupcake('build')
    sh> sh.cupcake('test')
    proc = sh.here> sh.cupcake('list') | sh.wc('-l')
    assert(proc.stdout == b'4\n')

    sh> sh.cupcake(f'remove:{kind}', 'bar')
    sh> sh.cupcake('build')
    sh> sh.cupcake('test')
    proc = sh.here> sh.cupcake('list') | sh.wc('-l')
    assert(proc.stdout == b'3\n')
