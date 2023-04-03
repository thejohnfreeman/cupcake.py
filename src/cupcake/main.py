import click
from click_option_group import optgroup
from contextlib import contextmanager
import functools
import hashlib
from importlib import resources
import itertools
import jinja2
import json
import libcst as cst
import libcst.matchers
import os
import pathlib
import re
import semver
import shlex
import shutil
import subprocess
import tempfile

from cupcake import cascade, confee

def run(command, *args, **kwargs):
    # TODO: Print this in a special color.
    print(' '.join(shlex.quote(str(arg)) for arg in command), flush=True)
    proc = subprocess.run(command, *args, **kwargs)
    proc.check_returncode()
    return proc

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


class SearchResult:
    """Representation for a Conan package search result."""

    key = functools.cmp_to_key(
        lambda a, b: semver.compare(a.version, b.version)
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

    @staticmethod
    def compare(a, b):
        return semver.compare(a.version, b.version)

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
            key = functools.cmp_to_key(SearchResult.compare)
            results = sorted(results, key=key, reverse=True)
            return results


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
            if relative, must be relative to build_dir
        """
        variables = {
            'CMAKE_EXPORT_COMPILE_COMMANDS': 'ON',
            **variables,
        }
        args = [f'-D{name}={value}' for name, value in variables.items()]
        args = [*args, source_dir]
        if generator is not None:
            args = ['-G', generator, *args]
        run([self.CMAKE, *args], cwd=build_dir)

test_template = """
{{ cmake }} --build {{ cmakeDir }}
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
        default='.',
    )
    def source_dir_(self, source_dir):
        return pathlib.Path(source_dir).resolve()

    @cascade.value()
    @cascade.option(
        '--config',
        default='.cupcake.toml',
        help='Absolute path or relative to source directory.',
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
        help='Absolute path or relative to source directory.'
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
    def state_(self, build_dir_):
        path = build_dir_ / 'cupcake.toml'
        return confee.read(path)

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
        '--prefix', help='Prefix at which to install this package.'
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
    @cascade.option('--profile', help='Name of Conan profile.')
    # TODO: Add option to configure shared linkage.
    def conan(
        self,
        source_dir_,
        conanfile_path_,
        build_dir_,
        config_,
        CONAN,
        state_,
        flavor_,
        profile,
    ):
        """Configure Conan."""
        if not conanfile_path_:
            return
        # TODO: Respect `conan config get general.default_profile`.
        profile = confee.resolve(profile, config_.conan.profile, 'default')
        # TODO: Accept parameter to override settings.
        # TODO: Find path to profile.
        profile_path = pathlib.Path.home() / '.conan/profiles' / profile
        m = hashlib.sha256()
        m.update(profile_path.read_bytes())
        m.update(conanfile_path_.read_bytes())
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
        base_command = [
            CONAN, 'install', source_dir_, '--build', 'missing',
            '--output-folder', conan_dir,
            '--profile:build', profile, '--profile:host', profile,
        ]
        for flavor in diff_flavors:
            run(
                [*base_command, '--settings', f'build_type={FLAVORS[flavor_]}'],
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
    @cascade.option('--generator', '-G', help='Name of CMake generator.')
    @cascade.option(
        '--shared/--static',
        help='Whether to build shared libraries.',
        default=None,
    )
    @cascade.option(
        '--with-tests/--without-tests',
        help='Whether to include tests.',
        default=None,
    )
    @cascade.option(
        '-P', 'prefixes',
        help='Prefix to search for installed packages. Repeatable.',
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
        with_tests,
        prefixes,
    ):
        """Configure CMake."""
        generator = confee.resolve(generator, config_.cmake.generator, None)
        shared = confee.resolve(shared, config_.cmake.shared, False)
        with_tests = confee.resolve(with_tests, config_.cmake.tests, True)
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
        if with_tests:
            m.update(b'tests')
        for p in prefixes:
            m.update(p.encode())
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
        if with_tests is not None:
            cmake_args['BUILD_TESTING'] = 'ON' if with_tests else 'OFF'
        if prefixes:
            cmake_args['CMAKE_PREFIX_PATH'] = ';'.join(prefixes)
        if multiConfig:
            new_flavors = config_.flavors()
            cmake_args['CMAKE_CONFIGURATION_TYPES'] = ';'.join(new_flavors)
        else:
            cmake_args['CMAKE_BUILD_TYPE'] = FLAVORS[flavor_]
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
    def build(self, CMAKE, cmake_dir_, flavor_, cmake, jobs):
        """Build the selected flavor."""
        args = ['--verbose']
        if cmake.multiConfig():
            args.extend(['--config', FLAVORS[flavor_]])
        args.append('--parallel')
        if jobs is not None:
            args.append(jobs)
        run([CMAKE, '--build', cmake_dir_, *args])
        return cmake

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
    def test(self, config_, CMAKE, cmake_dir_, flavor_, cmake):
        """Test the selected flavor."""
        template = confee.resolve(None, config_.scripts.test, test_template)
        template = jinja2.Template(template)
        context = {
            'cmake': CMAKE,
            'cmakeDir': cmake_dir_,
            'multiConfig': cmake.multiConfig(),
            'flavor': FLAVORS[flavor_],
        }
        command = shlex.split(template.render(**context))
        run(command, env={'CTEST_OUTPUT_ON_FAILURE': 'ON'})

    @cascade.command()
    @cascade.argument('path', required=False, default='.')
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
        in the format "First Last <user@domain.com>".
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
    def new(self, path, name, license, author, github, force):
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

        # TODO: Take these values from a user config or Git.
        # $ git config user.name
        # $ git config user.email
        context = dict(
            license=license,
            author=author,
            github=github,
        )

        prefix = pathlib.Path(path).resolve()
        if not force and prefix.exists() and any(prefix.iterdir()):
            raise SystemExit('directory is not empty')
        if name is None:
            name = prefix.name

        for tname in loader.list_templates():
            suffix = env.from_string(tname).render(**context, name=name)
            path = pathlib.Path(prefix, suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            template = env.get_template(tname)
            path.write_text(template.render(**context, name=name))

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

    @cascade.command()
    # TODO: Mutually exclusive option group for category.
    @cascade.option(
        '--test', '-T', 'as_test', is_flag=True, help='As a test requirement.',
    )
    @cascade.argument('package')
    def add(self, CONAN, conanfile_path_, as_test, package):
        """Add a requirement."""
        # TODO: Support conanfile.txt.
        if conanfile_path_.name != 'conanfile.py':
            raise SystemExit('missing conanfile.py')
        results = Conan(CONAN).search(package)
        if len(results) < 1:
            raise SystemExit('no matches found')
        version = results[0].version
        # TODO: Add --upgrade option.
        with tempfile.NamedTemporaryFile(mode='w') as recipe_out:
            tree = cst.parse_module(conanfile_path_.read_bytes())
            tree = tree.visit(AddRequirement(
                'test_requires' if as_test else 'requires', package, version,
            ))
            recipe_out.write(tree.code)
            recipe_out.flush()
            shutil.copy(recipe_out.name, conanfile_path_)

    @cascade.command()
    @cascade.argument('package')
    def remove(self, conanfile_path_, package):
        """Remove a requirement."""
        # TODO: Support conanfile.txt.
        if conanfile_path_.name != 'conanfile.py':
            raise SystemExit('missing conanfile.py')
        with tempfile.NamedTemporaryFile(mode='w') as recipe_out:
            tree = cst.parse_module(conanfile_path_.read_bytes())
            tree = tree.visit(RemoveRequirement(package))
            recipe_out.write(tree.code)
            recipe_out.flush()
            shutil.copy(recipe_out.name, conanfile_path_)

    @cascade.command()
    def clean(self, build_dir_path_):
        """Remove the build directory."""
        shutil.rmtree(build_dir_path_, ignore_errors=True)

Cupcake()
