import click
from click_option_group import optgroup
from contextlib import contextmanager
import functools
import hashlib
from importlib import resources
import io
import itertools
import jinja2
import json
import operator
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import typing as t
import urllib.parse

from cupcake import cascade, confee, transformations
from cupcake.expression import subject, contains

def run(command, *args, **kwargs):
    # TODO: Print this in a special color if writing to terminal.
    print(' '.join(shlex.quote(str(arg)) for arg in command), flush=True)
    proc = subprocess.run(command, *args, **kwargs)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc

def tee(command, *args, stream, **kwargs):
    proc = subprocess.Popen(
        command, *args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs
    )
    line = ' '.join(shlex.quote(str(arg)) for arg in command)
    line += '\n'
    line = line.encode()
    stream.write(line)
    sys.stdout.buffer.write(line)
    for line in proc.stdout:
        stream.write(line)
        sys.stdout.buffer.write(line)
    if proc.wait() != 0:
        raise SystemExit(proc.returncode)

def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def max_by(compare):
    def function(x, y):
        return y if compare(x, y) < 0 else x
    return function

# Build flavor is selected at build time.
# Configuration commands take a set of possible flavors.

# Map from friendly Cupcake name to Conan/CMake name.
FLAVORS = {
    'd': 'Debug',
    'debug': 'Debug',
    'minsizerel': 'MinSizeRel',
    'msr': 'MinSizeRel',
    'r': 'Release',
    'rd': 'RelWithDebInfo',
    'release': 'Release',
    'relwithdebinfo': 'RelWithDebInfo',
    'rwdi': 'RelWithDebInfo',
    'size': 'MinSizeRel',
}

PATTERN_INDEX_FILENAME = re.compile(r'^index-.*\.json$')

def const(value):
    def f(*args, **kwargs):
        return value
    return f

def compare(a, b):
    # Insane that Python does not have an efficient method for this.
    # https://stackoverflow.com/q/50782317/618906
    if a < b:
        return -1
    if a > b:
        return 1
    return 0

nonet = type(None)
compares = {
    (int, int): operator.sub,
    (str, str): compare,
    (int, nonet): const(1),
    (nonet, int): const(-1),
    (int, str): const(1),
    (str, int): const(-1),
    (str, nonet): const(-1),
    (nonet, str): const(1),
}

def print_call():
    def decorate(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            argss = ', '.join(map(str, args))
            print(f'{f.__name__}({argss}) => ', end='')
            value = f(*args, **kwargs)
            print(value)
            return value
        return decorated
    return decorate

def compare_version(a, b):
    # Not all Conan packages use Semantic Versioning.
    # To be as flexible as possible,
    # we treat version strings as non-digit-separated sequences of numbers.
    # Sequences are compared item-by-item, in order.
    # Numbers are compared numerically,
    # non-numbers are compared lexicographically.
    # Numbers are considered higher/later/younger versions than non-numbers.
    # Numbers are considered higher/later/younger versions than nothing.
    # Non-numbers are considered lower/earlier/older versions than nothing.
    aa = re.split('(\\D+)', a)
    bb = re.split('(\\D+)', b)
    for aaa, bbb in itertools.zip_longest(aa, bb):
        try:
            aaa = int(aaa)
            aaat = int
        except (ValueError, TypeError):
            aaat = type(aaa)
        try:
            bbb = int(bbb)
            bbbt = int
        except (ValueError, TypeError):
            bbbt = type(bbb)
        diff = compares[(aaat, bbbt)](aaa, bbb)
        if diff:
            return diff
    return 0

key = functools.cmp_to_key(
    lambda a, b: compare_version(a, b)
)

def assert_legal_name(name):
    if not re.match(r'^[a-z][a-z0-9-]*$', name):
        raise SystemExit(f'name must contain only lowercase letters, numbers, and dashes: {name}')

def parse_options(options: t.Iterable[str], default):
    """Parse "name[=value]" strings into a {name: value, ...} dictionary."""
    adds = {}
    for option in options:
        match = re.match(r'^([^=]+)(?:=(.+))?$', option)
        if not match:
            raise SystemExit(f'bad option: `{option}`')
        name = match.group(1)
        value = match.group(2)
        if value is None:
            value = default
        adds[name] = value
    return adds

def snake(string):
    return string.replace('-', '_')

def pascal(string):
    return string.title().replace('-', '')

PATTERN_GITHUB_PATH = r'/([^/]+)/([^/]+)(?:/tree/[^/]+(.+))?'

@contextmanager
def pack_directory(path):
    yield path

@contextmanager
def export_github(path):
    """Return a path to a Conan package directory identified by _url_."""
    with tempfile.TemporaryDirectory() as tmp:
        user, project, suffix = re.match(PATTERN_GITHUB_PATH, path).groups()
        if suffix is None:
            suffix = '/'
        run(['git', 'clone', f'https://github.com/{user}/{project}', tmp])
        yield tmp + suffix

def update_requirement(metadata, name, f):
    # TODO: Turn this into a confee function?
    requirements = metadata.imports([])
    i = next((i for i, d in enumerate(requirements) if d['name'] == name), -1)
    if i < 0:
        before = None
    else:
        before = requirements[i]
        del requirements[i:i+1]
    after = f(before)
    if after is not None:
        requirements.append(after)
    requirements.sort(key=lambda item: item['name'])
    metadata.imports = requirements

def expand(reference):
    if reference.startswith('lib'):
        return ('libraries', reference[len('lib'):])
    if reference.startswith('test.'):
        return ('tests', reference[len('test.'):])
    return ('executables', reference)

class SearchResult:
    """Representation for a Conan package search result."""

    key = functools.cmp_to_key(
        lambda a, b: compare_version(a.version, b.version)
    )

    def __init__(self, remote, reference):
        self.remote = remote
        match = re.match(f'^([^/]+)/([^@]+)(?:@(.*))?$', reference)
        self.package = match[1]
        self.version = match[2]
        self.remainder = match[3]

    def __str__(self):
        s = f'{self.package}/{self.version}@'
        if self.remainder:
            s += self.remainder
        return s

class Conan:
    def __init__(self, command):
        self.command = command

    def search(self, query):
        # TODO: Implement version constraints like Python.
        # Use them to filter list.
        local = self.search_local(query)
        remote = self.search_remotes(query)
        results = itertools.chain(local, remote)
        # They seem to be in ascending version order,
        # but I'm not sure we can rely on that.
        results = sorted(results, key=SearchResult.key, reverse=True)
        return results

    def get_cmake_names(self, rref):
        conanfile = resources.as_file(
            resources.files('cupcake')
            .joinpath('data')
            .joinpath('cmake_names.py')
        )
        with conanfile as conanfile:
            with tempfile.TemporaryDirectory() as build_dir:
                build_dir = pathlib.Path(build_dir)
                run([
                    self.command, 'install',
                    '--build', 'missing',
                    '--output-folder', build_dir,
                    conanfile,
                    '--options', f'requirement={rref}',
                ], stdout=subprocess.DEVNULL, cwd=build_dir)
                with (build_dir / 'output.json').open('r') as out:
                    names = json.load(out)
        return names

    @staticmethod
    def construct(command):
        stdout = subprocess.check_output(['conan', '--version']).strip()
        match = re.match(b'^Conan version (\\d)\\.', stdout)
        if not match:
            raise SystemExit('unrecognized Conan version')
        version = int(match.group(1))
        if version == 1:
            return Conan1(command)
        if version == 2:
            return Conan2(command)
        raise SystemExit('unsupported Conan version')

    def search_local(self, query):
        """Search the local cache."""

    def search_remotes(self, query):
        """Search all remotes."""

    def find_profile(self, name) -> pathlib.Path:
        """Return path to named profile."""


class Conan1(Conan):
    """Conan 1.x specialization."""

    def find_profile(self, name):
        return pathlib.Path.home() / '.conan/profiles' / name

    def search_local(self, query):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp) / 'search.json'
            run(
                [self.command, 'search', '--json', tmp,  query],
                stdout=subprocess.DEVNULL,
            )
            with tmp.open() as file:
                results = json.load(file)
            # {"error": bool, "results": [{"remote": null, "items": [{"recipe": {"id": reference}}]}]}
            if results['error']:
                raise SystemExit('unknown error searching local cache')
            return _parse_search_v1(results)

    def search_remotes(self, query):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp) / 'search.json'
            run(
                [self.command, 'search', '--json', tmp,  query, '--remote', 'all'],
                stdout=subprocess.DEVNULL,
            )
            with tmp.open() as file:
                results = json.load(file)
            # {"error": bool, "results": [{"remote": name, "items": [{"recipe": {"id": reference}}]}]}
            if results['error']:
                raise SystemExit('unknown error searching remotes')
            return _parse_search_v1(results)

def _parse_search_v1(results):
    return [
        SearchResult(result['remote'], item['recipe']['id'])
        for result in results['results']
        for item in result['items']
    ]


class Conan2(Conan):
    """Conan 2.x specialization."""

    def find_profile(self, name):
        stdout = subprocess.check_output(
            [self.command, 'profile', 'path', name]
        ).strip()
        return pathlib.Path(stdout.decode())

    def search_local(self, query):
        proc = run(
            [self.command, 'list', '--format', 'json',  query],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        # { "Local Cache": { reference: {}, ... } }
        results = json.loads(proc.stdout)
        results = {None: results['Local Cache']}
        return _parse_search_v2(results)

    def search_remotes(self, query):
        # TODO: Look into Conan Python API. Currently undocumented.
        proc = run(
            [self.command, 'search', '--format', 'json',  query],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        # { name: { reference: {}, ... }, name: { "error": str }
        results = json.loads(proc.stdout)
        return _parse_search_v2(results)

def _parse_search_v2(results):
    return [
        SearchResult(remote, reference)
        for remote in results
        for reference in results[remote]
        if reference != 'error'
    ]


_SINGLES = ('Unix Makefiles', 'Ninja')
_MULTIS = ('Ninja Multi-Config', 'Xcode')

class CMake:
    def __init__(self, CMAKE):
        self.CMAKE = CMAKE

    def is_multi_config(self, generator):
        """
        Configure a tiny project
        using the CMake file API
        in a temporary directory
        to find out whether the generator is multi-config.
        """
        if type(generator) == str:
            if generator in _SINGLES:
                return False
            if generator in _MULTIS:
                return True
            if generator.startswith('Visual Studio '):
                return True
        with tempfile.TemporaryDirectory() as cmake_dir:
            cmake_dir = pathlib.Path(cmake_dir)
            api_dir = cmake_dir / '.cmake/api/v1'
            query_dir = api_dir / 'query'
            query_dir.mkdir(parents=True)
            (query_dir / 'cmakeFiles-v1').touch()
            source_dir = resources.as_file(
                resources.files('cupcake')
                .joinpath('data')
                .joinpath('query')
            )
            with source_dir as source_dir:
                self.configure(cmake_dir, source_dir, generator)
            reply_dir = api_dir / 'reply'
            # TODO: Handle 0 or >1 matches.
            index_file = next(
                f for f in reply_dir.iterdir()
                if PATTERN_INDEX_FILENAME.match(f.name)
            )
            index = json.loads(index_file.read_text())
            multiConfig = index['cmake']['generator']['multiConfig']
            return multiConfig

    def configure(self, build_dir, source_dir, generator, variables={}, env={}):
        """
        source_dir : path-like
            If relative, must be relative to build_dir.
        """
        variables = dict(variables)
        args = [f'-D{name}={value}' for name, value in variables.items()]
        if generator is not None:
            args = ['-G', generator, *args]
        args = [*args, source_dir]
        env = { **os.environ, **env }
        run([self.CMAKE, *args], cwd=build_dir, env=env)

TEST_TEMPLATE_ = """
'{{ ctest }}' --test-dir '{{ cmakeDir }}'
{% if multiConfig %} --build-config {{ flavor }} {% endif %}
{% if regex %} --tests-regex {{ regex }} {% endif %}
"""

# We want commands to call dependencies,
# and want them to be able to pass options.
# That means dependent command must accept all the options of all its
# dependencies.

@cascade.group(context_settings=dict(
    help_option_names=['--help', '-h'],
    show_default=True,
))
class Cupcake:

    @cascade.value()
    @cascade.option(
        '--source-dir', '-S',
        help='Path to source directory. Absolute, or relative to current directory.',
        metavar='PATH',
        default='.',
    )
    def source_dir_(self, source_dir):
        return pathlib.Path(source_dir).resolve()

    @cascade.value()
    @cascade.option(
        '--config',
        default='.cupcake.toml',
        help='Path to Cupcake configuration file. Absolute, or relative to source directory.',
        metavar='PATH',
    )
    def config_(self, source_dir_, config):
        path = source_dir_ / config
        return confee.read(path)

    @cascade.value()
    def CONAN(self, config_):
        # TODO: Enable overrides from environment.
        command = confee.resolve(None, config_.CONAN, 'conan')
        return Conan.construct(command)

    @cascade.value()
    def CMAKE(self, config_):
        return confee.resolve(None, config_.CMAKE, 'cmake')

    @cascade.value()
    def CTEST(self, config_):
        return confee.resolve(None, config_.CTEST, 'ctest')

    @cascade.value()
    @cascade.option(
        '--build-dir', '-B',
        help='Path to build directory. Absolute, or relative to source directory.',
        metavar='PATH',
    )
    def build_dir_path_(self, source_dir_, config_, build_dir) -> pathlib.Path:
        """
        :param build_dir: pretty format of build directory
        """
        # This value is separate from `build_dir_` so that `clean` can use the
        # path without creating the directory.
        # TODO: Resolve command-line value against current directory,
        # but configuration or default value against source directory.
        build_dir = confee.resolve(build_dir, config_.directory, '.build')
        build_dir = source_dir_ / build_dir
        return build_dir

    @cascade.value()
    def build_dir_(self, build_dir_path_) -> pathlib.Path:
        """
        :param build_dir: pretty format of build directory
        """
        build_dir_path_.mkdir(parents=True, exist_ok=True)
        return build_dir_path_

    @cascade.value()
    def log_dir_(self, build_dir_) -> pathlib.Path:
        log_dir_path_ = build_dir_ / 'logs'
        log_dir_path_.mkdir(exist_ok=True)
        return log_dir_path_

    @cascade.value()
    def state_(self, build_dir_):
        path = build_dir_ / 'cupcake.toml'
        return confee.read(path)

    # TODO: Case-insensitive flavor name.
    # TODO: Mutex options --release and --debug.
    @cascade.value()
    @cascade.option(
        '--flavor',
        type=click.Choice(FLAVORS.keys()),
    )
    def flavor_(self, config_, flavor):
        flavor = confee.resolve(flavor, config_.selection, 'release')
        return flavor

    @cascade.command()
    def select(self, flavor_):
        """Select a flavor."""

    @cascade.value()
    @cascade.option(
        '--prefix', help='Prefix at which to install this package.', metavar='PATH',
    )
    def prefix_(self, config_, source_dir_, prefix):
        prefix = confee.resolve(prefix, config_.prefix, '.install')
        prefix = source_dir_ / prefix
        prefix = prefix.resolve()
        return prefix

    @cascade.value()
    def conanfile_path_(self, source_dir_):
        conanfile_path = source_dir_ / 'conanfile.py'
        if not conanfile_path.exists():
            conanfile_path = source_dir_ / 'conanfile.txt'
        if not conanfile_path.exists():
            return
        return conanfile_path

    @cascade.command()
    @cascade.option('--profile', help='Name of Conan profile.', metavar='NAME')
    # TODO: Add option to configure shared linkage.
    @cascade.option(
        '-o', 'options',
        help='Set a Conan option. Repeatable.',
        metavar='NAME[=VALUE]',
        multiple=True,
    )
    def conan(
        self,
        source_dir_,
        conanfile_path_,
        build_dir_,
        log_dir_,
        config_,
        CONAN,
        state_,
        flavor_,
        profile,
        options,
    ):
        """Configure Conan for all enabled flavors."""
        if not conanfile_path_:
            return
        # TODO: Respect `conan config get general.default_profile`.
        profile = confee.resolve(profile, config_.conan.profile, 'default')
        # Options are a little unique.
        # We must start with `config.conan.options` (default `{}`),
        # override with `options`,
        # and then write the result to `config.conan.options`.
        adds = parse_options(options, 'True')
        copts = confee.merge(adds, [], config_.conan.options, {})

        # TODO: Accept parameter to override settings.
        # TODO: Find path to profile.
        profile_path = CONAN.find_profile(profile)
        m = hashlib.sha256()
        # TODO: Separate values with markers to disambiguate.
        m.update(profile_path.read_bytes())
        m.update(conanfile_path_.read_bytes())
        path = source_dir_ / 'cupcake.json'
        if path.is_file():
            m.update(path.read_bytes())
        for name, value in copts.items():
            m.update(name.encode())
            m.update(value.encode())
        id = m.hexdigest()
        old_flavors = state_.conan.flavors([])
        new_flavors = list({*config_.flavors([]), flavor_})
        diff_flavors = [f for f in new_flavors if f not in old_flavors]
        conan_dir = build_dir_ / 'conan'
        if state_.conan:
            if state_.conan.id() == id:
                if not diff_flavors:
                    return state_.conan
            else:
                shutil.rmtree(conan_dir, ignore_errors=True)
                diff_flavors = new_flavors
        conan_dir.mkdir(parents=True, exist_ok=True)
        command = [
            CONAN.command, 'install', source_dir_, '--build', 'missing',
            '--output-folder', conan_dir,
            '--profile:build', profile, '--profile:host', profile,
        ]
        for name, value in copts.items():
            command.extend(['--options', f'{name}={value}'])
        for flavor in diff_flavors:
            with (log_dir_ / 'conan').open('wb') as stream:
                tee(
                    [*command, '--settings', f'build_type={FLAVORS[flavor_]}'],
                    stream=stream,
                    cwd=conan_dir,
                )
        state_.conan.id = id
        state_.conan.flavors = new_flavors
        # TODO: Find layout. How?
        toolchain = conan_dir / 'conan_toolchain.cmake'
        if not toolchain.exists():
            toolchain = conan_dir / 'build' / 'generators' / 'conan_toolchain.cmake'
        if not toolchain.exists():
            for flavor in ['Debug', 'Release']:
                toolchain = conan_dir / 'build' / flavor / 'generators' / 'conan_toolchain.cmake'
                if toolchain.exists():
                    break
        if not toolchain.exists():
            raise Exception('cannot find toolchain file')
        state_.conan.toolchain = str(toolchain)
        config_.flavors = new_flavors
        confee.write(config_)
        confee.write(state_)
        return state_.conan

    @cascade.command()
    @cascade.option(
        '--generator', '-G',
        help='Name of CMake generator.',
        metavar='NAME',
    )
    # TODO: Modify the Conan options to agree. Warn on explicit disagreement.
    @cascade.option(
        '--shared/--static',
        help='Whether to build shared libraries.',
        default=None,
    )
    @cascade.option(
        '--tests/--no-tests',
        help='Whether to include tests.',
        default=None,
    )
    @cascade.option(
        '-P', 'prefixes',
        help='Prefix to search for installed packages. Repeatable.',
        metavar='PATH',
        multiple=True,
    )
    @cascade.option(
        '-D', 'variables',
        help='Set a CMake variable. Repeatable.',
        metavar='NAME[=VALUE]',
        multiple=True,
    )
    @cascade.option(
        '-U', 'unvariables',
        help='Unset a CMake variable. Repeatable.',
        metavar='NAME',
        multiple=True,
    )
    @cascade.option(
        '--keep',
        help='Do not delete the CMake directory.',
        is_flag=True,
    )
    def cmake(
        self,
        source_dir_,
        config_,
        CMAKE,
        build_dir_,
        state_,
        flavor_,
        prefix_,
        conan,
        generator,
        shared,
        tests,
        prefixes,
        variables,
        unvariables,
        keep,
    ):
        """Configure CMake for at least the selected flavor."""
        # Variables are a little unique.
        # We must start with `config.cmake.variables` (default `{}`),
        # override with `variables`,
        # remove `unvariables`,
        # and then write the result to `config.cmake.variables`.
        adds = parse_options(variables, 'TRUE')
        cvars = confee.merge(adds, unvariables, config_.cmake.variables, {})

        generator = confee.resolve(generator, config_.cmake.generator, None)
        shared = confee.resolve(shared, config_.cmake.shared, False)
        tests = confee.resolve(tests, config_.cmake.tests, True)
        prefixes = confee.resolve(prefixes or None, config_.cmake.prefixes, [])
        # TODO: Convenience API for hashing identities.
        m = hashlib.sha256()
        if conan is not None:
            m.update(conan.id().encode())
        # TODO: Calculate ID from all files read during configuration.
        m.update((source_dir_ / 'CMakeLists.txt').read_bytes())
        if generator is not None:
            m.update(generator.encode())
        if shared:
            m.update(b'shared')
        if tests:
            m.update(b'tests')
        for p in prefixes:
            m.update(p.encode())
        for name, value in cvars.items():
            m.update(name.encode())
            m.update(value.encode())
        id = m.hexdigest()

        # Check for the conditions that enable a short-circuit.
        if state_.cmake.id(None) == id and flavor_ in state_.cmake.flavors([]):
            return state_.cmake

        # Once CMake is configured, its binary directory cannot be moved,
        # but our choice of binary directory depends on whether the
        # generator is multi-config.
        multiConfig = (
            state_.cmake.multiConfig()
            if state_.cmake.multiConfig
            and state_.cmake.generator(None) == generator else
            CMake(CMAKE).is_multi_config(generator)
        )

        # The config names the set of interesting flavors.
        # It was already assigned by the `conan` step
        # unless there is no conanfile.
        cflavors = list({*config_.flavors([]), flavor_})

        # The state names the subset of interesting flavors
        # that are configured in the build directory.
        # In a multi-config scenario, they should be an equal subset.
        # In a single-config scenario,
        # flavors are configured only when selected.
        if multiConfig:
            sflavors = cflavors
        elif state_.cmake.id(None) == id:
            # We're going to configure an additional single-config
            # CMake directory. The others are not invalidated.
            sflavors = list({*state_.cmake.flavors([]), flavor_})
        else:
            sflavors = [flavor_]

        cmake_dir = build_dir_ / 'cmake'
        if not multiConfig:
            cmake_dir /= flavor_

        if not keep:
            shutil.rmtree(cmake_dir, ignore_errors=True)
        cmake_dir.mkdir(parents=True, exist_ok=True)
        # CMake complains if any of these variables are unused,
        # but it is impossible to predict which will be unused.
        # Don't sweat it.
        cmake_args = {}
        cmake_args['CMAKE_EXPORT_COMPILE_COMMANDS'] = 'ON'
        cmake_args['CMAKE_POLICY_DEFAULT_CMP0091'] = 'NEW'
        cmake_args['BUILD_SHARED_LIBS'] = 'ON' if shared else 'OFF'
        cmake_args['CMAKE_INSTALL_PREFIX'] = prefix_
        if conan is not None:
            cmake_args['CMAKE_TOOLCHAIN_FILE:FILEPATH'] = conan.toolchain()
        if tests is not None:
            cmake_args['BUILD_TESTING'] = 'ON' if tests else 'OFF'
        if prefixes:
            cmake_args['CMAKE_PREFIX_PATH'] = ';'.join(prefixes)
        if multiConfig:
            flavors = [FLAVORS[f] for f in sflavors]
            cmake_args['CMAKE_CONFIGURATION_TYPES'] = ';'.join(flavors)
        else:
            cmake_args['CMAKE_BUILD_TYPE'] = FLAVORS[flavor_]
        # Add these last to let callers override anything.
        for name, value in cvars.items():
            cmake_args[name] = value
        CMake(CMAKE).configure(
            cmake_dir, source_dir_, generator, cmake_args,
            env={'CMAKE_OUTPUT_DIR': build_dir_ / 'output'},
        )

        state_.cmake.id = id
        state_.cmake.generator = generator
        state_.cmake.multiConfig = multiConfig
        state_.cmake.flavors = sflavors
        confee.write(config_)
        confee.write(state_)
        return state_.cmake

    @cascade.value()
    def cmake_dir_(self, build_dir_, flavor_, cmake):
        build_dir_ /= 'cmake'
        if not cmake.multiConfig():
            build_dir_ /= flavor_
        return build_dir_

    @cascade.command()
    @cascade.option(
        '--jobs', '-j', type=int, help='Maximum number of simultaneous jobs.',
    )
    @cascade.argument('target', required=False)
    def build(self, config_, CMAKE, build_dir_, log_dir_, cmake_dir_, flavor_, cmake, jobs, target):
        """Build the selected flavor."""
        jobs = confee.resolve(jobs, config_.jobs, None)
        confee.write(config_)
        command = [CMAKE, '--build', cmake_dir_, '--verbose']
        if cmake.multiConfig():
            command.extend(['--config', FLAVORS[flavor_]])
        command.append('--parallel')
        if jobs is not None:
            command.append(str(jobs))
        if target is not None:
            command.extend(['--target', target])
        with (log_dir_ / 'build').open('wb') as stream:
            tee(command, stream=stream)
        return cmake

    @cascade.command()
    @cascade.argument('executable', required=False)
    # TODO: No way to pass arguments to default executable.
    @cascade.argument('arguments', nargs=-1)
    def exe(self, CMAKE, cmake_dir_, flavor_, cmake, executable, arguments):
        """Execute an executable target."""
        target = 'execute'
        if executable is not None:
            target += '-' + executable
        command = [CMAKE, '--build', cmake_dir_, '--target', target]
        if cmake.multiConfig():
            command.extend(['--config', FLAVORS[flavor_]])
        env = os.environ.copy()
        env['CUPCAKE_EXE_ARGUMENTS'] = ' '.join(map(shlex.quote, arguments))
        run(command, env=env)

    @cascade.command()
    def install(self, CMAKE, cmake_dir_, flavor_, build, prefix_):
        """Install the selected flavor."""
        run([
            CMAKE,
            '--install',
            cmake_dir_,
            '--config',
            FLAVORS[flavor_],
            '--prefix',
            prefix_,
        ])

    @cascade.command()
    @cascade.argument('regex', required=False)
    def test(self, config_, CTEST, log_dir_, cmake_dir_, flavor_, cmake, regex):
        """Test the selected flavor."""
        template = confee.resolve(None, config_.scripts.test, TEST_TEMPLATE_)
        template = jinja2.Template(template)
        context = {
            'ctest': CTEST,
            'cmakeDir': cmake_dir_,
            'multiConfig': cmake.multiConfig(),
            'flavor': FLAVORS[flavor_],
            'regex': regex,
        }
        command = shlex.split(template.render(**context))
        env = os.environ.copy()
        env['CTEST_OUTPUT_ON_FAILURE'] = 'ON'
        with (log_dir_ / 'test').open('wb') as stream:
            tee(command, stream=stream, env=env)

    def jenv_(self, directory):
        loader = jinja2.PackageLoader('cupcake', directory)
        jenv = jinja2.Environment(
            loader=loader,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        jenv.filters['pascal'] = pascal
        jenv.filters['snake'] = snake
        return jenv

    @cascade.command()
    @cascade.argument('path', required=False, default='.')
    @cascade.option(
        '--version', help='Version of requirement cupcake.cmake@github/thejohnfreeman.', default='1.0.0',
    )
    @cascade.option(
        '--special/--general', help='Whether to enable special commands.', default=True,
    )
    @cascade.option(
        '--library/--no-library', help='Whether to export a library.', default=True,
    )
    @cascade.option(
        '--executable/--no-executable', help='Whether to export an executable.', default=True,
    )
    @cascade.option(
        '--tests/--no-tests', help='Whether to include tests.', default=True,
    )
    @cascade.option(
        '--name', help='Package name. Default is the directory name.'
    )
    @cascade.option(
        '--license',
        help='The software license SPDX identifier.',
        default='ISC',
    )
    @cascade.option(
        '--author',
        help='''
        The author name and/or email address,
        in the format "First Last <user@host.com>".
        The default is taken from `git config`.
        ''',
    )
    @cascade.option(
        '--github', '--gh', help='The GitHub project owner.',
    )
    @cascade.option(
        '--force', '-f',
        help='Ignore whether directory is empty.',
        is_flag=True,
    )
    def new(
        self,
        path,
        version: str,
        special: bool,
        library: bool,
        executable: bool,
        tests: bool,
        name,
        license,
        author,
        github,
        force,
    ):
        """Create a new project."""
        jenv = self.jenv_('data/new')

        if author is None:
            username = subprocess.run(
                ['git', 'config', 'user.name'], capture_output=True
            ).stdout.decode().strip()
            email = subprocess.run(
                ['git', 'config', 'user.email'], capture_output=True
            ).stdout.decode().strip()
            author = f'{username} <{email}>'

        prefix = pathlib.Path(path).resolve()
        if not force and prefix.exists() and any(prefix.iterdir()):
            raise SystemExit('directory is not empty')
        if name is None:
            name = prefix.name

        # TODO: Take default license and github from user config.
        context = dict(
            version=version,
            special=special,
            with_library=library,
            with_executable=executable,
            with_tests=tests,
            license=license,
            author=author,
            github=github,
        )

        tnames = [
            n for n in jenv.list_templates()
            if (library or not n.startswith('include/'))
            or (library or not n.startswith('src/lib'))
            or (executable or not (n.startswith('src/') and not n.startswith('src/lib')))
            or (tests or not n.startswith('tests/'))
        ]
        self.generate_(jenv, prefix, tnames, name, context)

        # Assemble and write cupcake.json.
        if special:
            metadata = confee.read(prefix / 'cupcake.json')
            metadata.project.name = name
            if library:
                metadata.libraries = [
                    {'name': name, 'links': ['${PROJECT_NAME}.imports.main'] }
                ]
            if executable:
                links = ['${PROJECT_NAME}.imports.main']
                if library:
                    links.append(f'{name}.lib{name}')
                exe = {'name': name, 'links': links}
                metadata.executables = [exe]
            if tests:
                metadata.imports = [
                    {
                        'name': 'doctest',
                        'version': '2.4.8',
                        'reference': 'doctest/2.4.8',
                        'file': 'doctest',
                        'targets': ['doctest::doctest'],
                        'groups': ['test'],
                    }
                ]
                links = ['${PROJECT_NAME}.imports.test']
                if library:
                    links.append(f'{name}.lib{name}')
                test = {'name': name, 'links': links }
                metadata.tests = [test]
            confee.write(metadata)


    def generate_(self, jenv, prefix, tnames, name, context):
        assert_legal_name(name)

        context = {
            **context,
            'name': name,
            'namespaces': [name],
        }

        for tname in tnames:
            suffix = jenv.from_string(tname).render(**context)
            path = pathlib.Path(prefix, suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            template = jenv.get_template(tname)
            path.write_text(template.render(**context))


    @cascade.command()
    @cascade.argument('query')
    def search(self, CONAN, query):
        """Search for packages."""
        results = CONAN.search(query)
        # Put the top results at the end
        # to guarantee they can be seen without scrolling.
        for result in reversed(results):
            remote = result.remote
            remote = remote if remote else '<local>'
            print(f'{remote:20} {result}')

    @cascade.command()
    # TODO: Mutually exclusive option group to choose requirement group.
    @cascade.option(
        '--group', '-g', metavar='GROUP', multiple=True, default=('main',),
        help='Requirement groups, e.g. "main" or "test".',
    )
    @cascade.argument('query')
    def add(self, CONAN, source_dir_, conanfile_path_, group, query):
        """Add a requirement."""
        # TODO: Support conanfile.txt.
        if conanfile_path_.name != 'conanfile.py':
            raise SystemExit('missing conanfile.py')

        # Parse reference into name/version@user/channel
        # with optional version, user, and channel.
        match = re.match('([^/@]+)(?:/([^/@]+))?(?:@([^/@]+)/([^/@]+))?', query)
        if not match:
            raise SystemExit(f'not a reference pattern: "{query}"')
        name, version, user, channel = match.groups()

        if version is None:
            subquery = f'{name}/*'
            if user is not None:
                subquery += f'@{user}/{channel}'
            results = CONAN.search(subquery)
            if len(results) < 1:
                raise SystemExit('no matches found')
            version = results[0].version

        reference = f'{name}/{version}'
        if user is not None:
            reference += f'@{user}/{channel}'

        # Find the CMake names.
        names = CONAN.get_cmake_names(reference)

        # Find the cupcake.json.
        path = source_dir_ / 'cupcake.json'
        metadata = confee.read(path)

        # Add or update the requirement.
        def add_requirement(before):
            if before is not None:
                # TODO: Add --upgrade option.
                raise SystemExit(f'{name} already in imports')
            return {
                'name': name,
                'version': version,
                'reference': reference,
                'file': names['file'],
                'targets': names['targets'],
                'groups': group,
            }
        update_requirement(metadata, name, add_requirement)

        # Update cupcake.json.
        confee.write(metadata)

    @cascade.command()
    @cascade.argument('name')
    def remove(self, conanfile_path_, source_dir_, name):
        """Remove a requirement."""
        # TODO: Support conanfile.txt.
        if conanfile_path_.name != 'conanfile.py':
            raise SystemExit('missing conanfile.py')

        path = source_dir_ / 'cupcake.json'
        metadata = confee.read(path)
        imports = confee.filter(metadata.imports[:], subject['name'] == name)
        imports = list(imports)
        # Exit if it is missing or ambiguous.
        if len(imports) < 1:
            raise SystemExit(f'requirement not found: {name}')
        assert(len(imports) == 1)
        update_requirement(metadata, name, const(None))
        confee.write(metadata)

    @cascade.command()
    def list(self, source_dir_):
        """List targets and their links."""
        metadata = confee.read(source_dir_ / 'cupcake.json')
        kinds = [
            ('libraries', 'lib'),
            ('executables', ''),
            ('tests', 'test.'),
        ]
        for kind, prefix in kinds:
            for item in metadata[kind][:]:
                line = f'{prefix}{item.name()}'
                links = item.links([])
                if links:
                    line += ' -> ' + ', '.join(links)
                print(line)

    @cascade.command()
    @cascade.argument('downstream', required=True)
    @cascade.argument('upstreams', required=True, nargs=-1)
    def link(self, source_dir_, downstream, upstreams):
        """Link downstream artifact to upstream libraries."""
        metadata = confee.read(source_dir_ / 'cupcake.json')
        pname = metadata.project.name()

        def unprefix(reference):
            for prefix in (pname + '.', '${PROJECT_NAME}.'):
                if reference.startswith(prefix):
                    return reference[len(prefix):]
            return reference

        def find(reference):
            kind, name = expand(reference)
            items = confee.filter(metadata[kind][:], subject['name'] == name)
            items = list(items)
            if len(items) > 1:
                raise SystemExit(f'ambiguous reference: {reference}')
            if len(items) < 1:
                raise SystemExit(f'unknown reference: {reference}')
            return items[0]

        downstream = unprefix(downstream)
        dproxy = find(downstream)

        for upstream in upstreams:
            upstream = unprefix(upstream)
            if upstream.startswith('lib'):
                uproxy = find(upstream)
                if uproxy == dproxy:
                    raise SystemExit(f'cannot link to self')
            elif not re.match(f'^imports.\\w+$', upstream):
                raise SystemExit(f'upstream is not a library: {upstream}')

            link1 = '${PROJECT_NAME}.' + upstream
            link2 = pname + '.' + upstream

            existing = confee.filter(dproxy.links[:], (
                (subject == link1) | (subject == link2) |
                (subject['target'] == link1) | (subject['target'] == link2)
            ))
            existing = list(existing)
            if len(existing) > 0:
                raise SystemExit('already linked')
            confee.add(dproxy.links, link1)

        confee.write(metadata)

    @cascade.command()
    @cascade.argument('downstream', required=True)
    @cascade.argument('upstreams', required=True, nargs=-1)
    def unlink(self, source_dir_, downstream, upstreams):
        """Unlink downstream artifact from upstream libraries."""
        metadata = confee.read(source_dir_ / 'cupcake.json')
        pname = metadata.project.name()

        def unprefix(reference):
            for prefix in (pname + '.', '${PROJECT_NAME}.'):
                if reference.startswith(prefix):
                    return reference[len(prefix):]
            return reference

        def find(reference):
            kind, name = expand(reference)
            items = confee.filter(metadata[kind][:], subject['name'] == name)
            items = list(items)
            if len(items) > 1:
                raise SystemExit(f'ambiguous reference: {reference}')
            if len(items) < 1:
                raise SystemExit(f'unknown reference: {reference}')
            return items[0]

        downstream = unprefix(downstream)
        dproxy = find(downstream)

        for upstream in upstreams:
            upstream = unprefix(upstream)
            # We don't need to check that upstream is a library.
            # All we care is whether it appears in the links.

            link1 = '${PROJECT_NAME}.' + upstream
            link2 = pname + '.' + upstream

            confee.remove_if(dproxy.links[:], (
                (subject == link1) | (subject == link2) |
                (subject['target'] == link1) | (subject['target'] == link2)
            ))

        confee.write(metadata)

    @cascade.command('add:lib')
    @cascade.option('--public/--private', is_flag=True, default=True, help='Whether to export the library.')
    @cascade.option('--header-only', is_flag=True, help='Whether to create a source file.')
    @cascade.argument('name', required=True)
    def add_lib(self, source_dir_, public, header_only, name):
        """Add a library."""
        jenv = self.jenv_('data/new')

        tnames = ['include/{{name}}/{{name}}.hpp']
        if not header_only:
            tnames.append('src/lib{{name}}.cpp')
        self.generate_(jenv, source_dir_, tnames, name, context={})

        metadata = confee.read(source_dir_ / 'cupcake.json')
        library = {'name': name, 'links': ['${PROJECT_NAME}.imports.main'] }
        if not public:
            library['private'] = True
        confee.add(metadata.libraries, library)
        confee.write(metadata)

    @cascade.command('remove:lib')
    @cascade.argument('name', required=True)
    def remove_lib(self, source_dir_, name):
        """Remove a library."""
        # Find the library in the metadata.
        metadata = confee.read(source_dir_ / 'cupcake.json')
        libraries = confee.filter(metadata.libraries[:], subject['name'] == name)
        libraries = list(libraries)
        # Exit if it is missing or ambiguous.
        if len(libraries) < 1:
            raise SystemExit(f'unknown library name: {name}')
        if len(libraries) > 1:
            raise SystemExit(f'ambiguous library name: {name}')
        [proxy] = libraries
        library = proxy()
        confee.delete(proxy)

        # TODO: Remove its sources according to its section.
        (source_dir_ / 'include' / f'{name}.hpp').unlink(missing_ok=True)
        (source_dir_ / 'include' / f'{name}.h').unlink(missing_ok=True)
        try:
            shutil.rmtree(source_dir_ / 'include' / f'{name}')
        except FileNotFoundError:
            pass

        (source_dir_ / 'src' / f'lib{name}.cpp').unlink(missing_ok=True)
        (source_dir_ / 'src' / f'lib{name}.c').unlink(missing_ok=True)
        try:
            shutil.rmtree(source_dir_ / 'src' / f'lib{name}')
        except FileNotFoundError:
            pass

        # Find links to the library in the metadata.
        # It must be an internal library.
        targets = [f'${{PROJECT_NAME}}.lib{name}']
        if metadata.project.name:
            targets.append(f'{metadata.project.name()}.lib{name}')

        for kind in {'libraries', 'executables', 'tests'}:
            for target in metadata[kind][:]:
                for link in target.links[:]:
                    # Take target from shorthand or longhand.
                    ltarget = link()
                    if 'target' in ltarget:
                        ltarget = ltarget['target']
                    # Proceed only if target matches removed library.
                    if ltarget not in targets:
                        continue
                    # Remove link from metadata.
                    confee.delete(link)
                    # Remove includes from source files.
                    section = 'tests' if kind == 'tests' else 'exports'
                    section = target.section(section)
                    root = 'tests' if section == 'tests' else 'src'
                    root = pathlib.Path(root)
                    for suffix in ('h', 'hpp', 'c', 'cpp'):
                        if (file := root / f'{name}.{suffix}').is_file():
                            print(file)
                            transformations.remove_includes(file, name)
                    for parent, _, files in os.walk(root / name):
                        parent = pathlib.Path(parent)
                        for file in files:
                            print(parent / file)
                            transformations.remove_includes(parent / file, name)

        confee.write(metadata)

    @cascade.command('add:exe')
    @cascade.option('--public/--private', is_flag=True, default=True, help='Whether to export the executable.')
    @cascade.argument('name', required=True)
    def add_exe(self, source_dir_, public, name):
        """Add an executable."""
        jenv = self.jenv_('data/new')

        tnames = ['src/{{name}}.cpp']
        self.generate_(jenv, source_dir_, tnames, name, context={})

        metadata = confee.read(source_dir_ / 'cupcake.json')
        executable = { 'name': name, 'links': ['${PROJECT_NAME}.imports.main'] }
        if not public:
            executable['private'] = True
        confee.add(metadata.executables, executable)
        confee.write(metadata)

    @cascade.command('remove:exe')
    @cascade.argument('name', required=True)
    def remove_exe(self, source_dir_, name):
        """Remove an executable."""
        # Find the executable in the metadata.
        metadata = confee.read(source_dir_ / 'cupcake.json')
        executables = confee.filter(metadata.executables[:], subject['name'] == name)
        executables = list(executables)
        # Exit if it is missing or ambiguous.
        if len(executables) < 1:
            raise SystemExit(f'unknown executable name: {name}')
        if len(executables) > 1:
            raise SystemExit(f'ambiguous executable name: {name}')
        [proxy] = executables
        confee.delete(proxy)

        (source_dir_ / 'src' / f'{name}.cpp').unlink(missing_ok=True)
        (source_dir_ / 'src' / f'{name}.c').unlink(missing_ok=True)
        try:
            shutil.rmtree(source_dir_ / 'src' / f'{name}')
        except FileNotFoundError:
            pass

        confee.write(metadata)

    @cascade.command('add:test')
    @cascade.argument('name', required=True)
    def add_test(self, source_dir_, name):
        """Add a test."""
        jenv = self.jenv_('data/new')

        tnames = ['tests/{{name}}.cpp']
        self.generate_(jenv, source_dir_, tnames, name, context={})

        metadata = confee.read(source_dir_ / 'cupcake.json')
        confee.add(
            metadata.tests,
            {'name': name, 'links': ['${PROJECT_NAME}.imports.test'] },
        )
        confee.write(metadata)

    @cascade.command('remove:test')
    @cascade.argument('name', required=True)
    def remove_test(self, source_dir_, name):
        """Remove a test."""
        # Find the test in the metadata.
        metadata = confee.read(source_dir_ / 'cupcake.json')
        tests = confee.filter(metadata.tests[:], subject['name'] == name)
        tests = list(tests)
        # Exit if it is missing or ambiguous.
        if len(tests) < 1:
            raise SystemExit(f'unknown test name: {name}')
        if len(tests) > 1:
            raise SystemExit(f'ambiguous test name: {name}')
        [proxy] = tests
        confee.delete(proxy)

        (source_dir_ / 'tests' / f'{name}.cpp').unlink(missing_ok=True)
        (source_dir_ / 'tests' / f'{name}.c').unlink(missing_ok=True)
        try:
            shutil.rmtree(source_dir_ / 'tests' / f'{name}')
        except FileNotFoundError:
            pass

        confee.write(metadata)

    @cascade.command('add:header')
    @cascade.argument('qname', required=True)
    def add_header(self, source_dir_, qname):
        """
        Add a new header to an existing library.

        The argument should be a qualified name,
        e.g. "foo.bar.baz" for include/foo/bar/baz.hpp.
        """
        namespaces = qname.split('.')
        for name in namespaces:
            assert_legal_name(name)
        path = source_dir_.joinpath('include', *namespaces).with_suffix('.hpp')
        if path.exists():
            raise SystemExit(f'file already exists: {path}')
        name = namespaces.pop()

        metadata = confee.read(source_dir_ / 'cupcake.json')
        if not any(l.name() == namespaces[0] for l in metadata.libraries[:]):
            raise SystemExit(f'missing library: {namespaces[0]}')

        path.parent.mkdir(parents=True, exist_ok=True)
        jenv = self.jenv_('data/new')
        template = jenv.get_template('include/{{name}}/{{name}}.hpp')
        path.write_text(template.render({
            'namespaces': namespaces,
            'name': name,
        }))

    @cascade.command()
    @cascade.argument('url', default='.')
    def export(self, CONAN, url):
        """
        Copy a Conan package to your local cache.

        For this command, it is important to understand the idea of a "Conan
        package directory", which is a directory containing a `conanfile.py`
        Conan recipe.
        The URL argument must resolve to a Conan package directory.

        The default URL is `.`, which is the package you are in,
        but a few schemes are understood:

        \b
        - An absolute or relative path to a Conan package directory.
        - A file:// URL for an absolute path to a Conan package directory.
        - An http:// or https:// URL for the github.com domain pointing to
          a Conan package directory.
        - A gh://username/project[/path/to/directory] URL that identifies
          a GitHub project and an optional path within that project to
          a Conan package directory.
        """
        parts = urllib.parse.urlparse(url)
        if parts.scheme in ('http', 'https'):
            if parts.netloc != 'github.com':
                raise ValueError('unknown URL')
            context = export_github(parts.path)
        elif parts.scheme == 'gh':
            context = export_github(parts.path)
        elif parts.scheme in ('', 'file'):
            context = pack_directory(parts.path)
        with context as path:
            run([CONAN.command, 'export', path])

    @cascade.command()
    @cascade.option('--remote', default='github')
    def publish(self, CONAN, source_dir, remote):
        """Upload package to Conan remote."""
        stream = io.BytesIO()
        tee([CONAN.command, 'export', source_dir], stream=stream)
        line = stream.getvalue().splitlines()[-1]
        reference = re.match(rb'([^/]+/[^@]+@[^/]+/[^:]+): Exported revision: ', line)
        if not reference:
            raise SystemExit('cannot find reference in stdout')
        reference = reference.group(1)
        run([CONAN.command, 'upload', '--remote', remote, reference])

    @cascade.command()
    def clean(self, build_dir_path_):
        """Remove the build directory."""
        shutil.rmtree(build_dir_path_, ignore_errors=True)

def main():
    start = time.time()
    try:
        Cupcake()
    finally:
        duration = time.time() - start # in seconds
        if duration > 1:
            # TODO: Print human-friendly representation.
            print(f'{duration:.3}s')
