import subprocess
import tempfile

def test_new():
    with tempfile.TemporaryDirectory() as work_dir:
        def test(*args):
            subprocess.check_call(['cupcake', *args], cwd=work_dir)
        test('new', 'foo')
        test('build', '-S', 'foo', '-B', '.build')
        test('clean', '-S', 'foo', '-B', '.build')
        test('test', '-S', 'foo', '-B', '.build')
        test('install', '-S', 'foo', '-B', '.build', '--prefix', '.install')
        test('add', '-S', 'foo', 'boost')
