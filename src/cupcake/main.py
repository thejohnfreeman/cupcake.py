import click
from click_option_group import optgroup
from contextlib import contextmanager
import functools
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

from cupcake import confee

# TODO: Make these proper command line > environment > configuration file
# settings.
CONAN = os.environ.get('CONAN', 'conan')
CMAKE = os.environ.get('CMAKE', 'cmake')


def run(command, *args, **kwargs):
    print(' '.join(str(arg) for arg in command))
    return subprocess.run(command, *args, **kwargs)

def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

# We want commands to call dependencies,
# and want them to be able to pass options.
# That means dependent command must accept all the options of all its
# dependencies.

class Cupcake:
    def __init__(self):
        self.source_dir = pathlib.Path('.').resolve()

    @functools.cache
    def config(self, name='.cupcake.toml'):
        path = self.source_dir / name
        return confee.read(path)

    @functools.cache
    def build_dir(self, build_dir=None) -> pathlib.Path:
        """
        :param build_dir: pretty format of build directory
        """
        build_dir = confee.resolve(build_dir, self.config().directory, '.build')
        build_dir = self.source_dir / build_dir
        build_dir.mkdir(parents=True, exist_ok=True)
        return build_dir

    @functools.cache
    def cache(self, build_dir=None):
        path = self.build_dir(build_dir) / 'cupcake.toml'
        return confee.read(path)

    def conan(self, flavor, profile, build_dir=None):
        """Configure Conan for the given flavor."""
        # TODO: Accept parameter to choose config.
        config = self.config()
        # TODO: Respect `conan config get general.default_profile`.
        profile = confee.resolve(profile, config.conan.profile, 'default')
        # TODO: Accept parameter to override settings.
        # TODO: Find path to profile.
        profile_path = pathlib.Path.home() / '.conan/profiles' / profile
        conanfile_path = self.source_dir / 'conanfile.py'
        if not conanfile_path.exists():
            conanfile_path = self.source_dir / 'conanfile.txt'
        if not conanfile_path.exists():
            return
        m = hashlib.sha256()
        m.update(profile_path.read_bytes())
        m.update(conanfile_path.read_bytes())
        id = m.hexdigest()
        cache = self.cache(build_dir)
        # TODO: Parse and format flavor names between Conan and .cupcake.toml.
        old_flavors = cache.conan.flavors([])
        new_flavors = list(set([*config.flavors([]), flavor]))
        diff_flavors = [f for f in new_flavors if f not in old_flavors]
        conan_dir = self.build_dir(build_dir) / 'conan'
        # TODO: Find layout.
        toolchain_path = conan_dir / 'conan_toolchain.cmake'
        if cache.conan:
            if cache.conan.id() == id:
                if not diff_flavors:
                    return toolchain_path
            else:
                shutil.rmtree(conan_dir, ignore_errors=True)
        conan_dir.mkdir(parents=True, exist_ok=True)
        base_command = [
            CONAN, 'install', self.source_dir, '--build', 'missing',
            '--output-folder', conan_dir,
            '--profile:build', profile, '--profile:host', profile,
        ]
        for flavor in diff_flavors:
            run(
                [*base_command, '--settings', f'build_type={flavor}'],
                cwd=conan_dir,
            )
        cache.conan.id = id
        cache.conan.flavors = new_flavors
        config.flavors = new_flavors
        confee.write(config)
        confee.write(cache)
        return toolchain_path

    def clean(self, build_dir=None):
        # TODO: Separate construction of build directory from its name
        # calculation.
        shutil.rmtree(self.build_dir(build_dir), ignore_errors=True)


cupcake = Cupcake()


@click.group(context_settings={
    'help_option_names': ('--help', '-h'),
    'auto_envvar_prefix': 'CUPCAKE',
})
def main():
    pass


# Build flavor is selected at build time.
# Configuration commands take a set of possible flavors.

# Map from friendly Cupcake name to Conan/CMake name.
FLAVORS = {
    'release': 'Release',
    'debug': 'Debug',
}

# TODO: Take a settings parameter.
# TODO: Take a conanfile parameter?
@main.command()
@click.option(
    '--flavor',
    type=click.Choice(FLAVORS.keys()),
    default='release',
    show_default=True,
    callback=lambda ctx, param, value: FLAVORS[value],
)
def conan(flavor, profile=None):
    cupcake.conan(flavor, profile)

@main.command()
def clean():
    cupcake.clean()
