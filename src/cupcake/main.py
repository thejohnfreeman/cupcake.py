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
import libcst as cst
import libcst.matchers
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
import urllib.parse

from cupcake import cascade, confee

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
    'release': 'Release',
    'debug': 'Debug',
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
    aa = re.split('(\D+)', a)
    bb = re.split('(\D+)', b)
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

def parse_options(options, default):
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

PATTERN_GITHUB_PATH = r'/([^/]+)/([^/]+)(?:/tree/[^/]+(.+))?'

@contextmanager
def pack_directory(path):
    yield path

@contextmanager
def pack_github(path):
    """Return a path to a Conan package directory identified by _url_."""
    with tempfile.TemporaryDirectory() as tmp:
        user, project, suffix = re.match(PATTERN_GITHUB_PATH, path).groups()
        if suffix is None:
            suffix = '/'
        run(['git', 'clone', f'https://github.com/{user}/{project}', tmp])
        yield tmp + suffix

def update_dependency(metadata, group, name, f):
    dependencies = metadata.dependencies[group]([])
    i = next((i for i, d in enumerate(dependencies) if d['name'] == name), -1)
    if i < 0:
        before = None
    else:
        before = dependencies[i]
        del dependencies[i:i+1]
    after = f(before)
    if after is not None:
        dependencies.append(after)
    dependencies.sort(key=lambda item: item['name'])
    metadata.dependencies[group] = dependencies

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
    def __init__(self, CONAN):
        self.CONAN = CONAN

    def search(self, query):
        # TODO: Look into Conan Python API. Currently undocumented.
        # TODO: Implement version constraints like Python.
        # Use them to filter list.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp) / 'search.json'

            # Search local cache.
            run(
                [self.CONAN, 'search', '--json', tmp,  query],
                stdout=subprocess.DEVNULL,
            )
            with tmp.open() as f:
                local = json.load(f)
            if local['error']:
                raise SystemExit('unknown error searching local cache')

            # Search remotes.
            run(
                [self.CONAN, 'search', '--json', tmp,  query, '--remote', 'all'],
                stdout=subprocess.DEVNULL,
            )
            with tmp.open() as f:
                remote = json.load(f)
            if remote['error']:
                raise SystemExit('unknown error searching remotes')

            results = itertools.chain(local['results'], remote['results'])
            results = [
                SearchResult(result['remote'], item['recipe']['id'])
                for result in results
                for item in result['items']
            ]
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
                    self.CONAN, 'install',
                    '--build', 'missing',
                    '--install-folder', build_dir,
                    '--output-folder', build_dir,
                    conanfile,
                    '--options', f'requirement={rref}',
                ], stdout=subprocess.DEVNULL)
                with (build_dir / 'output.json').open('r') as out:
                    names = json.load(out)
        return names

class CMake:
    def __init__(self, CMAKE):
        self.CMAKE = CMAKE

    def is_multi_config(self, generator):
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

    def configure(self, build_dir, source_dir, generator, variables={}):
        """
        source_dir : path-like
            If relative, must be relative to build_dir.
        """
        variables = dict(variables)
        args = [f'-D{name}={value}' for name, value in variables.items()]
        args = [*args, source_dir]
        if generator is not None:
            args = ['-G', generator, *args]
            # CMake will warn when this variable is unused by the generator.
            # https://cmake.org/cmake/help/latest/variable/CMAKE_EXPORT_COMPILE_COMMANDS.html
            # TODO: Let `cupcake_project()` set a different default for this
            # variable, and Cupcake can just link it in the build directory if
            # it is found after the `cmake` step.
            if re.search('Makefiles|Ninja', generator):
                variables['CMAKE_EXPORT_COMPILE_COMMANDS'] = 'ON'
        run([self.CMAKE, *args], cwd=build_dir)

TEST_TEMPLATE_ = """
'{{ cmake }}' --build '{{ cmakeDir }}'
{% if multiConfig %} --config {{ flavor }} {% endif %}
--target {% if multiConfig %} RUN_TESTS {% else %} test {% endif %}
"""

def cstNewLine(indent=''):
    return cst.ParenthesizedWhitespace(
        indent=True,
        last_line=cst.SimpleWhitespace(indent),
    )

class ChangeRequirements(cst.CSTTransformer):

    def __init__(self, properties=['requires']):
        m = cst.matchers
        self.properties = m.OneOf(*map(m.Name, properties))

    def leave_Assign(self, old, new):
        m = cst.matchers
        if len(new.targets) != 1:
            return new
        if not m.matches(new.targets[0].target, self.properties):
            return new
        if not m.matches(
            new.value,
            (m.List | m.Set | m.Tuple)(
                elements=[m.ZeroOrMore(m.Element(value=m.SimpleString()))]
            )
        ):
            raise SystemExit('requirements is not a list of strings')
        matches = [
            re.match(r'^[\'"]([^/]+)/(.*)[\'"]$', e.value.value)
            for e in new.value.elements
        ]
        ids = {match.group(1): match.group(2) for match in matches}
        ids = self.change_(ids)
        ids = [f'{k}/{v}' for k, v in ids.items()]
        ids = sorted(ids)
        elements = [
            cst.Element(
                value=cst.SimpleString(f"'{id}'"),
                comma=cst.Comma(whitespace_after=cstNewLine('    ')),
            ) for id in ids
        ]
        elements[-1] = cst.Element(value=elements[-1].value, comma=cst.Comma())
        return new.with_changes(
            value=new.value.with_changes(
                elements=elements,
                lbracket=cst.LeftSquareBracket(whitespace_after=cstNewLine('    ')),
                rbracket=cst.RightSquareBracket(whitespace_before=cstNewLine()),
            )
        )

class AddRequirement(ChangeRequirements):

    def __init__(self, property, name, version):
        super().__init__(properties=[property])
        self.name = name
        self.version = version

    def change_(self, ids):
        if self.name not in ids:
            ids[self.name] = self.version
        return ids

class RemoveRequirement(ChangeRequirements):

    def __init__(self, name):
        super().__init__(properties=['requires', 'test_requires'])
        self.name = name

    def change_(self, ids):
        ids.pop(self.name, None)
        return ids

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
        help='Absolute path or relative to current directory.',
        metavar='PATH',
        default='.',
    )
    def source_dir_(self, source_dir):
        return pathlib.Path(source_dir).resolve()

    @cascade.value()
    @cascade.option(
        '--config',
        default='.cupcake.toml',
        help='Absolute path or relative to source directory.',
        metavar='PATH',
    )
    def config_(self, source_dir_, config):
        path = source_dir_ / config
        return confee.read(path)

    @cascade.value()
    def CONAN(self, config_):
        # TODO: Enable overrides from environment.
        return confee.resolve(None, config_.CONAN, 'conan')

    @cascade.value()
    def CMAKE(self, config_):
        return confee.resolve(None, config_.CMAKE, 'cmake')

    @cascade.value()
    @cascade.option(
        '--build-dir', '-B',
        help='Absolute path or relative to source directory.',
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
        """Configure Conan."""
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
        profile_path = pathlib.Path.home() / '.conan/profiles' / profile
        m = hashlib.sha256()
        # TODO: Separate values with markers to disambiguate.
        m.update(profile_path.read_bytes())
        m.update(conanfile_path_.read_bytes())
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
            CONAN, 'install', source_dir_, '--build', 'missing',
            '--output-folder', conan_dir,
            '--profile:build', profile, '--profile:host', profile,
        ]
        for option in options:
            command.extend(['--options', option])
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
    ):
        """Configure CMake."""
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
        # We need to know what flavors are configured in CMake after this
        # step.
        # If we find that the generator is single-config and the CMake state
        # ID is the same, then we can add the new flavor to the existing
        # CMake state flavors.
        # If we find that the generator is multi-config, then we'll use all
        # the configured flavors (which matches the Conan state flavors).
        # Otherwise, the generator is single-config and the CMake state ID is
        # different, so only the new flavor is valid.
        # We start with that assumption, and change the value only when
        # we can prove one of the above conditions.
        new_flavors = [flavor_]
        cmake_dir = build_dir_ / 'cmake'
        if state_.cmake:
            old_flavors = state_.cmake.flavors([])
            multiConfig = state_.cmake.multiConfig()
            if state_.cmake.id() == id:
                if flavor_ in old_flavors:
                    return state_.cmake
                if not multiConfig:
                    # We're going to configure an additional single-config
                    # build directory. The others are not invalidated.
                    new_flavors = [*old_flavors, flavor_]
        else:
            # Once CMake is configured, its binary directory cannot be moved,
            # but our choice of binary directory depends on whether the
            # generator is multi-config.
            # We first configure a tiny project in a temporary directory to
            # find out whether the generator is multi-config. 
            multiConfig = CMake(CMAKE).is_multi_config(generator)
        if not multiConfig:
            cmake_dir /= flavor_
        shutil.rmtree(cmake_dir, ignore_errors=True)
        # This directory should not yet exist, but its parent might.
        cmake_dir.mkdir(parents=True)
        cmake_args = {}
        cmake_args['BUILD_SHARED_LIBS'] = 'ON' if shared else 'OFF'
        cmake_args['CMAKE_INSTALL_PREFIX'] = prefix_
        if conan is not None:
            cmake_args['CMAKE_TOOLCHAIN_FILE:FILEPATH'] = conan.toolchain()
        if tests is not None:
            cmake_args['BUILD_TESTING'] = 'ON' if tests else 'OFF'
        if prefixes:
            cmake_args['CMAKE_PREFIX_PATH'] = ';'.join(prefixes)
        if multiConfig:
            new_flavors = config_.flavors()
            cmake_args['CMAKE_CONFIGURATION_TYPES'] = ';'.join(new_flavors)
        else:
            cmake_args['CMAKE_BUILD_TYPE'] = FLAVORS[flavor_]
        # Add these last to let callers override anything.
        for name, value in cvars.items():
            cmake_args[name] = value
        CMake(CMAKE).configure(
            cmake_dir, source_dir_, generator, cmake_args
        )
        state_.cmake.id = id
        state_.cmake.multiConfig = multiConfig
        state_.cmake.flavors = new_flavors
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
        '--jobs', '-j', help='Maximum number of simultaneous jobs.'
    )
    @cascade.argument('target', required=False)
    def build(self, CMAKE, build_dir_, log_dir_, cmake_dir_, flavor_, cmake, jobs, target):
        """Build the selected flavor."""
        command = [CMAKE, '--build', cmake_dir_, '--verbose']
        if cmake.multiConfig():
            command.extend(['--config', FLAVORS[flavor_]])
        command.append('--parallel')
        if jobs is not None:
            command.append(jobs)
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
    def test(self, config_, CMAKE, log_dir_, cmake_dir_, flavor_, cmake):
        """Test the selected flavor."""
        template = confee.resolve(None, config_.scripts.test, TEST_TEMPLATE_)
        template = jinja2.Template(template)
        context = {
            'cmake': CMAKE,
            'cmakeDir': cmake_dir_,
            'multiConfig': cmake.multiConfig(),
            'flavor': FLAVORS[flavor_],
        }
        command = shlex.split(template.render(**context))
        env = os.environ.copy()
        env['CTEST_OUTPUT_ON_FAILURE'] = 'ON'
        with (log_dir_ / 'test').open('wb') as stream:
            tee(command, stream=stream, env=env)

    @cascade.command()
    @cascade.argument('path', required=False, default='.')
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
        '--github', '--gh', help='The GitHub user or organization.',
    )
    @cascade.option(
        '--force', '-f',
        help='Ignore whether directory is empty.',
        is_flag=True,
    )
    def new(
        self,
        path,
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
        loader = jinja2.PackageLoader('cupcake', 'data/new')
        env = jinja2.Environment(
            loader=loader,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        if author is None:
            username = subprocess.run(
                ['git', 'config', 'user.name'], capture_output=True
            ).stdout.decode().strip()
            email = subprocess.run(
                ['git', 'config', 'user.email'], capture_output=True
            ).stdout.decode().strip()
            author = f'{username} <{email}>'

        # TODO: Take default license and github from user config.
        context = dict(
            with_library=library,
            with_executable=executable,
            with_tests=tests,
            license=license,
            author=author,
            github=github,
        )

        prefix = pathlib.Path(path).resolve()
        if not force and prefix.exists() and any(prefix.iterdir()):
            raise SystemExit('directory is not empty')
        if name is None:
            name = prefix.name

        if not re.match(r'[a-z][a-z0-9-]*', name):
            raise SystemExit(f'name must contain only lowercase letters, numbers, and dashes: {name}')

        NameTitle = name.title().replace('-', '')
        name_snake_lower = name.replace('-', '_')
        NAME_SNAKE_UPPER = name_snake_lower.upper()

        context.update({
            'name': name,
            'NameTitle': NameTitle,
            'name_snake_lower': name_snake_lower,
            'NAME_SNAKE_UPPER': NAME_SNAKE_UPPER,
        })

        for tname in loader.list_templates():
            suffix = env.from_string(tname).render(**context)
            if not library and suffix.startswith('include/'):
                continue
            if not library and suffix.startswith('src/lib'):
                continue
            if not executable and suffix.startswith('src/') and not suffix.startswith('src/lib'):
                continue
            if not tests and suffix.startswith('tests/'):
                continue
            path = pathlib.Path(prefix, suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            template = env.get_template(tname)
            path.write_text(template.render(**context))

    @cascade.command()
    @cascade.argument('query')
    def search(self, CONAN, query):
        """Search for packages."""
        results = Conan(CONAN).search(query)
        # Put the top results at the end
        # to guarantee they can be seen without scrolling.
        for result in reversed(results):
            remote = result.remote
            remote = remote if remote else '<local>'
            print(f'{remote:20} {result}')

    # TODO: Handle reference ending in '@'.
    @cascade.command()
    # TODO: Mutually exclusive option group to choose dependency group.
    @cascade.option(
        '--test', '-T', 'as_test', is_flag=True, help='As a test requirement.',
    )
    @cascade.argument('name')
    def add(self, CONAN, source_dir_, conanfile_path_, as_test, name):
        """Add a requirement."""
        # TODO: Support conanfile.txt.
        if conanfile_path_.name != 'conanfile.py':
            raise SystemExit('missing conanfile.py')
        results = Conan(CONAN).search(name)
        if len(results) < 1:
            raise SystemExit('no matches found')
        version = results[0].version

        # Update the recipe.
        # TODO: Add --upgrade option.
        with tempfile.NamedTemporaryFile(mode='w') as recipe_out:
            tree = cst.parse_module(conanfile_path_.read_bytes())
            tree = tree.visit(AddRequirement(
                'test_requires' if as_test else 'requires', name, version,
            ))
            recipe_out.write(tree.code)
            recipe_out.flush()
            shutil.copy(recipe_out.name, conanfile_path_)

        # Find the CMake names.
        names = Conan(CONAN).get_cmake_names(f'{name}/{version}')

        # Find the cupcake.json.
        path = source_dir_ / 'cupcake.json'
        metadata = confee.read(path)

        # Add or update the dependency.
        group = 'test' if as_test else 'main'
        def add_dependency(before):
            if before is not None:
                # TODO: Update existing dependency.
                raise SystemExit(f'{name} already in dependencies.{group}')
            return {
                'name': name,
                'file': names['file'],
                'targets': names['targets']
            }
        update_dependency(metadata, group, name, add_dependency)

        # Update cupcake.json.
        confee.write(metadata)

    @cascade.command()
    @cascade.argument('name')
    def remove(self, conanfile_path_, source_dir_, name):
        """Remove a requirement."""
        # TODO: Support conanfile.txt.
        if conanfile_path_.name != 'conanfile.py':
            raise SystemExit('missing conanfile.py')
        with tempfile.NamedTemporaryFile(mode='w') as recipe_out:
            tree = cst.parse_module(conanfile_path_.read_bytes())
            tree = tree.visit(RemoveRequirement(name))
            recipe_out.write(tree.code)
            recipe_out.flush()
            shutil.copy(recipe_out.name, conanfile_path_)

        # Find the cupcake.json.
        path = source_dir_ / 'cupcake.json'
        metadata = confee.read(path)
        update_dependency(metadata, 'main', name, const(None))
        update_dependency(metadata, 'test', name, const(None))
        confee.write(metadata)

    @cascade.command()
    @cascade.argument('url', default='.')
    def pack(self, CONAN, url):
        """
        Add a Conan package to your local cache.

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
            context = pack_github(parts.path)
        elif parts.scheme == 'gh':
            context = pack_github(parts.path)
        elif parts.scheme in ('', 'file'):
            context = pack_directory(parts.path)
        with context as path:
            run([CONAN, 'export', path])

    @cascade.command()
    @cascade.option('--remote', default='github')
    def publish(self, CONAN, source_dir, remote):
        """Upload package to Conan remote."""
        stream = io.BytesIO()
        tee([CONAN, 'export', source_dir], stream=stream)
        line = stream.getvalue().splitlines()[-1]
        reference = re.match(rb'([^/]+/[^@]+@[^/]+/[^:]+): Exported revision: ', line)
        if not reference:
            raise SystemExit('cannot find reference in stdout')
        reference = reference.group(1)
        run([CONAN, 'upload', '--remote', remote, reference])

    @cascade.command()
    def clean(self, build_dir_path_):
        """Remove the build directory."""
        shutil.rmtree(build_dir_path_, ignore_errors=True)

def main():
    start = time.time()
    try:
        Cupcake()
    finally:
        finish = time.time()
        print(f'{finish - start:.3}s')
