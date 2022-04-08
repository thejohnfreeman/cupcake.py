import click
from click_option_group import optgroup
from contextlib import contextmanager
import hashlib
import os
import pathlib
import psutil
import re
import shutil
import subprocess
import tempfile
import tomlkit
import toolz

# TODO: Make these proper command line > environment > configuration file
# settings.
CONAN = os.environ.get('CONAN', 'conan')
CMAKE = os.environ.get('CMAKE', 'cmake')


def run(command, *args, **kwargs):
    print(' '.join(str(arg) for arg in command))
    return subprocess.run(command, *args, **kwargs)

_MISSING = object()
_SELVES = {}

_GENERATORS = {
    'Ninja': {'multi': False},
}

def is_multi(generator):
    # Assume a generator is single-config.
    return _GENERATORS.get(generator, {}).get('multi', False)

class Value:
    def __init__(self, parent, name, value):
        self.parent = parent
        self.name = name
        self.value = value
        self.members = {}
    def get(self, name):
        proxy = self.members.get(name, None)
        if proxy is None:
            value = (
                _MISSING
                if self.value is _MISSING
                else self.value.get(name, _MISSING)
            )
            proxy = ValueProxy(self, name, value)
            self.members[name] = proxy
        return proxy
    def set(self, name, value):
        if self.value is _MISSING:
            self.parent.set(self.name, tomlkit.table())
        _SELVES[self.get(name)].value = value
        self.value[name] = value

class ValueProxy:
    def __init__(self, parent, name, value):
        _SELVES[self] = Value(parent, name, value)
    def __getattr__(self, name):
        return _SELVES[self].get(name)
    def __setattr__(self, name, value):
        return _SELVES[self].set(name, value)
    def __call__(self, default=None, *args, **kwargs):
        value = _SELVES[self].value
        return default if value is _MISSING else value
    def __del__(self):
        del _SELVES[self]

class Cupcake:
    def __init__(self):
        self.source_dir = pathlib.Path('.').resolve()
        self.build_dir = self.source_dir / '.build'
        self.install_dir = self.build_dir / 'install'
        self.config_file = self.build_dir / 'cupcake.toml'
        if self.config_file.exists():
            with self.config_file.open() as f:
                config = tomlkit.load(f)
        else:
            config = tomlkit.document()
        self.config = ValueProxy(None, '<root>', config)

    def clear(self):
        shutil.rmtree(self.build_dir, ignore_errors=True)

    def save(self):
        with self.config_file.open('w') as f:
            tomlkit.dump(self.config(), f)

    def conan(self, flavor):
        self.config.selection = flavor

        # TODO: Handle single-config Conan generators.
        # Gather the inputs.
        conanfile = self.source_dir / 'conanfile.py'
        if not conanfile.exists():
            conanfile = self.source_dir / 'conanfile.txt'
        if not conanfile.exists():
            return
        # Identify the inputs.
        id = hashlib.sha1(conanfile.read_bytes()).hexdigest()
        flavors = self.config.conan.flavors([])
        conan_dir = self.build_dir / 'conan'
        if self.config.conan.id() != id:
            # Dependencies have changed. Clear everything.
            shutil.rmtree(self.build_dir / 'conan', ignore_errors=True)
        elif flavor in flavors:
            # We have previously created this resource.
            return conan_dir
        # Create the outputs.
        conan_dir.mkdir(parents=True, exist_ok=True)
        run(
            [
                CONAN, 'install', self.source_dir,
                '--build', 'missing',
                '--settings', f'build_type={flavor}'
            ],
            cwd=conan_dir,
        )
        self.config.conan.id = id
        self.config.conan.flavors = [*flavors, flavor]
        return conan_dir

    def cmake(self, generator, flavor, shared):
        conan_dir = self.conan(flavor)
        id = [generator, shared]
        flavors = self.config.cmake.flavors([])
        cmake_dir = self.build_dir / 'cmake'
        if not is_multi(generator):
            cmake_dir /= flavor
        if self.config.cmake.id() != id:
            shutil.rmtree(self.build_dir / 'cmake', ignore_errors=True)
        elif flavor in flavors:
            return cmake_dir
        cmake_dir.mkdir(parents=True)
        run(
            [
                CMAKE, '-G', generator,
                f'-DCMAKE_TOOLCHAIN_FILE={conan_dir / "conan_toolchain.cmake"}',
                f'-DCMAKE_INSTALL_PREFIX={self.install_dir}',
                f'-DBUILD_SHARED_LIBS={"ON" if shared else "OFF"}',
                self.source_dir,
            ],
            cwd=cmake_dir,
        )
        self.config.cmake.id = id
        self.config.cmake.generator = generator
        self.config.cmake.flavors = [*flavors, flavor]
        self.config.cmake.shared = shared
        return cmake_dir

    def build(self, flavor, target):
        cmake_dir = self.cmake(
            self.config.cmake.generator('Ninja'),
            flavor,
            self.config.cmake.shared(False),
        )
        command = [
            CMAKE,
            '--build',
            cmake_dir,
            '--verbose',
            '--parallel',
            str(psutil.cpu_count()),
        ]
        if target is not None:
            command.extend(['--target', target])
        run(command)


cupcake = Cupcake()

@click.group(context_settings={
    'help_option_names': ('--help', '-h'),
    'auto_envvar_prefix': 'CUPCAKE',
})
def main():
    pass

_option_flavor = toolz.compose(
    optgroup.group('Flavor'),
    optgroup.option('--release', 'flavor', flag_value='Release'),
    optgroup.option('--debug', 'flavor', flag_value='Debug'),
    optgroup.option(
        '--flavor',
        default=cupcake.config.selection('Release'),
        show_default=True,
        envvar='CUPCAKE_FLAVOR',
        show_envvar=True,
    ),
)

@main.command()
@click.argument('selection', required=False, default=None)
def select(selection):
    if selection is None:
        print(cupcake.config.selection())
    else:
        cupcake.config.selection = selection
        cupcake.save()


@main.command()
@_option_flavor
def conan(flavor):
    cupcake.conan(flavor)
    cupcake.save()


@main.command()
@click.option('-g', '--generator', default=cupcake.config.generator('Ninja'),
              show_default=True, envvar='CUPCAKE_GENERATOR', show_envvar=True)
@_option_flavor
@click.option('--shared', default=False)
@click.pass_context
def configure(context, generator, flavor, shared):
    cupcake.cmake(generator, flavor, shared)
    cupcake.save()


@main.command()
@_option_flavor
@click.argument('target', required=False, default=None)
def build(flavor, target):
    cupcake.build(flavor, target)
    cupcake.save()


@main.command()
@_option_flavor
def test(flavor):
    generator = cupcake.config.cmake.generator()
    target = 'RUN_TESTS' if is_multi(generator) else 'test'
    cupcake.build(flavor, target)
    cupcake.save()


@main.command()
@_option_flavor
def install(flavor):
    cupcake.build(flavor, 'install')
    cupcake.save()


@main.command()
def clear():
    cupcake.clear()


@main.command()
@click.argument('path', required=False, default='.')
def new(path):
    import jinja2

    loader = jinja2.PackageLoader('cupcake', 'data')
    env = jinja2.Environment(loader=loader, keep_trailing_newline=True)

    # TODO: Load user configuration.
    config = dict(
        license='ISC',
        author='John Freeman <jfreeman08@gmail.com>',
        github='thejohnfreeman',
    )

    prefix = pathlib.Path(path).resolve()
    name = prefix.name

    for tname in loader.list_templates():
        suffix = env.from_string(tname).render(**config, name=name)
        path = pathlib.Path(prefix, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        template = env.get_template(tname)
        path.write_text(template.render(**config, name=name))

@main.command()
@click.argument('query')
def search(query):
    run([CONAN, 'search', '--remote', 'conancenter', query])

def is_package_ref(query):
    process = subprocess.run([
        CONAN, 'info',
        '--remote', 'conancenter',
        '--only', 'None',
        query + '@',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return not process.returncode

@contextmanager
def atomic_file(path):
    (file, tpath) = tempfile.mkstemp()
    file = os.fdopen(file, 'w')
    try:
        yield file
    finally:
        if file.closed:
            os.replace(tpath, path)
        else:
            file.close()
            os.remove(tpath)

@main.command()
@click.argument('package')
@click.option('--dev', '-D', is_flag=True)
def add(package, dev):
    # If the given package is not a complete reference, try to complete it
    # by selecting the latest version.
    if not is_package_ref(package):
        process = run(
            [CONAN, 'search', '--remote', 'conancenter', package],
            capture_output=True, text=True,
        )
        selection = process.stdout.split()[-1]
        if not is_package_ref(selection):
            raise SystemExit(f'unknown package: {package}')
        package = selection
    section = '[tool_requires]' if dev else '[requires]'
    with atomic_file('conanfile.txt') as ofile:
        ifile = open('conanfile.txt', 'r')
        entered = False
        for line in ifile:
            ofile.write(line)
            if line == section:
                entered = True
                break
        if not entered:
            print('', file=ofile)
            print(section, file=ofile)
        eof = False
        for line in ifile:
            if re.match('^\[[^]]+\]$', line) or line > package:
                break
        else:
            eof = True
        print(package, file=ofile)
        if not eof:
            ofile.write(line)
        for line in ifile:
            ofile.write(line)
        ofile.close()
