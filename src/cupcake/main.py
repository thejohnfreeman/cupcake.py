import click
from click_option_group import optgroup
from contextlib import contextmanager
import functools
import hashlib
from importlib import resources
import json
import os
import pathlib
import psutil
import re
import shlex
import shutil
import subprocess
import tempfile
import tomlkit
import toolz

from cupcake import cascade, confee

def run(command, *args, **kwargs):
    # TODO: Print this in a special color.
    print(' '.join(shlex.quote(str(arg)) for arg in command))
    return subprocess.run(command, *args, **kwargs)

def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

# TODO: Make these proper command line > environment > configuration file
# settings.
CONAN = os.environ.get('CONAN', 'conan')
CMAKE = os.environ.get('CMAKE', 'cmake')

# Build flavor is selected at build time.
# Configuration commands take a set of possible flavors.

# Map from friendly Cupcake name to Conan/CMake name.
FLAVORS = {
    'release': 'Release',
    'debug': 'Debug',
}

class CMake:
    @staticmethod
    def is_multi_config(generator):
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
                CMake.configure(cmake_dir, source_dir, generator)
            reply_dir = api_dir / 'reply'
            # TODO: Handle 0 or >1 matches.
            # TODO: Use regex to match file name.
            index_file = next(
                f for f in reply_dir.iterdir() if f.name.startswith('index-')
            )
            index = json.loads(index_file.read_text())
            multiConfig = index['cmake']['generator']['multiConfig']
            return multiConfig

    @staticmethod
    def configure(build_dir, source_dir, generator, variables={}):
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
        run([CMAKE, *args], cwd=build_dir)


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
    @cascade.option('--source-dir', '-S', default='.')
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
    @cascade.option('--build-dir', '-B')
    def build_dir_path_(self, source_dir_, config_, build_dir) -> pathlib.Path:
        """
        :param build_dir: pretty format of build directory
        """
        # This value is separate from `build_dir_` so that `clean` can use the
        # path without creating the directory.
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
    @cascade.option('--profile')
    # TODO: Add option to configure shared linkage.
    def conan(self, source_dir_, build_dir_, config_, state_, flavor_, profile):
        """Configure Conan."""
        # TODO: Resolve `flavor` against `selection` in config,
        # but only once and shared by all methods.
        # Requires cached method for selection, where methods do not have to
        # worry about passing parameters to dependencies.
        # TODO: Respect `conan config get general.default_profile`.
        profile = confee.resolve(profile, config_.conan.profile, 'default')
        # TODO: Accept parameter to override settings.
        # TODO: Find path to profile.
        profile_path = pathlib.Path.home() / '.conan/profiles' / profile
        conanfile_path = source_dir_ / 'conanfile.py'
        if not conanfile_path.exists():
            conanfile_path = source_dir_ / 'conanfile.txt'
        if not conanfile_path.exists():
            return
        m = hashlib.sha256()
        m.update(profile_path.read_bytes())
        m.update(conanfile_path.read_bytes())
        id = m.hexdigest()
        # TODO: Parse and format flavor names between Conan and .cupcake.toml.
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
        # TODO: Find layout.
        state_.conan.id = id
        state_.conan.flavors = new_flavors
        state_.conan.toolchain = str(conan_dir / 'conan_toolchain.cmake')
        config_.flavors = new_flavors
        confee.write(config_)
        confee.write(state_)
        return state_.conan

    @cascade.command()
    @cascade.option('--generator', '-G', help='Name of CMake generator.')
    def cmake(
            self,
            source_dir_,
            config_,
            build_dir_,
            state_,
            flavor_,
            conan,
            generator,
    ):
        """Configure CMake."""
        generator = confee.resolve(generator, config_.cmake.generator, None)
        # TODO: Convenience API for hashing identities.
        m = hashlib.sha256()
        m.update(conan.id().encode())
        # TODO: Calculate ID from all files read during configuration.
        m.update(pathlib.Path('CMakeLists.txt').read_bytes())
        if generator is not None:
            m.update(generator.encode())
        id = m.hexdigest()
        old_flavors = state_.cmake.flavors([])
        cmake_dir = build_dir_ / 'cmake'
        if state_.cmake:
            if state_.cmake.id() == id:
                if flavor_ in old_flavors:
                    return state_.cmake
                print('here')
                if not state_.cmake.multiConfig():
                    cmake_dir = cmake_dir / flavor_
                    cmake_dir.mkdir()
                    CMake.configure(cmake_dir, source_dir_, generator, {
                        'CMAKE_TOOLCHAIN_FILE:FILEPATH': conan.toolchain(),
                        'CMAKE_BUILD_TYPE': FLAVORS[flavor_],
                    })
                    state_.cmake.flavors = [*old_flavors, flavor_]
                    confee.write(state_)
                    return state_.cmake
        # Once CMake is configured, its binary directory cannot be moved, but
        # our choice of binary directory depends on whether the generator is
        # multi-config. We first configure a tiny project in a temporary
        # directory to find out whether the generator is multi-config. 
        multiConfig = CMake.is_multi_config(generator)
        if not multiConfig:
            cmake_dir /= flavor_
        shutil.rmtree(cmake_dir, ignore_errors=True)
        # This directory should not yet exist.
        cmake_dir.mkdir(parents=True)
        CMake.configure(cmake_dir, source_dir_, generator, {
            'CMAKE_TOOLCHAIN_FILE:FILEPATH': conan.toolchain(),
            'CMAKE_BUILD_TYPE': FLAVORS[flavor_],
            'CMAKE_CONFIGURATION_TYPES': ';'.join(conan.flavors()),
        })
        state_.cmake.id = id
        state_.cmake.multiConfig = multiConfig
        state_.cmake.flavors = conan.flavors() if multiConfig else [flavor_]
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
    @cascade.option('--jobs', '-j')
    def build(self, cmake_dir_, flavor_, cmake, jobs):
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
    def test(self, cmake_dir_, flavor_, cmake):
        """Test the selected flavor."""
        args = []
        if cmake.multiConfig():
            target = 'RUN_TESTS'
            args.extend(['--config', FLAVORS[flavor_]])
        else:
            target = 'test'
        run([CMAKE, '--build', cmake_dir_, *args, '--target', target])

    @cascade.command()
    @cascade.argument('query')
    def search(self, query):
        """Search for packages."""
        run([CONAN, 'search', '--remote', 'all', query])

    @cascade.command()
    def clean(self, build_dir_path_):
        """Remove the build directory."""
        shutil.rmtree(build_dir_path_, ignore_errors=True)

Cupcake()
