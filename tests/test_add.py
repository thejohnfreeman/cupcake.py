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
    sh> sh.cupcake('new', 'foo')
    source = resources.as_file(
        resources.files('tests')
        .joinpath('data')
        .joinpath(src)
    )
    os.unlink(cwd / dst)
    with source as source:
        shutil.copy(source, cwd / dst)
    with pytest.raises(subprocess.CalledProcessError):
        sh> sh.cupcake(command, '-S', 'foo', '-B', '.build')
    sh> sh.cupcake('add', reference, '--group', group, '-S', 'foo')
    sh> sh.cupcake(command, '-S', 'foo', '-B', '.build')
    sh> sh.cupcake('remove', 'fmt', '-S', 'foo')
    with pytest.raises(subprocess.CalledProcessError):
        sh> sh.cupcake(command, '-S', 'foo', '-B', '.build')
    with pytest.raises(subprocess.CalledProcessError):
        sh> sh.cupcake('remove', 'fmt', '-S', 'foo')
