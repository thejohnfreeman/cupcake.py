"""A configuration for Cupcake.

All build system abstractions interpret one shared Cupcake configuration in
the context of their own semantics.
"""

from enum import Enum
from pathlib import Path
import typing as t

from cached_property import cached_property
import pydantic
import toml


class Flavor(str, Enum):
    DEBUG = 'Debug'
    RELEASE = 'Release'


FLAVOR_ALIASES = {
    'debug': Flavor.DEBUG,
    'release': Flavor.RELEASE,
}


class Generator(str, Enum):
    MAKE = 'Unix Makefiles'
    NINJA = 'Ninja'


# CMake generator names are case-sensitive, but we want to be friendlier.
GENERATOR_ALIASES = {
    'make': Generator.MAKE,
    'ninja': Generator.NINJA,
}


class AbsolutePath(Path):

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, pathlike):
        return Path(pathlike).resolve()


class Configuration(pydantic.BaseModel):
    source_directory: AbsolutePath = '.'
    build_directory: AbsolutePath = '.build'
    generator: Generator = Generator.NINJA
    flavor: Flavor = Flavor.DEBUG
    shared: bool = False
    definitions: t.Mapping[str, str] = {}

    class Config:
        arbitrary_types_allowed = True
        keep_untouched = (cached_property,)
        allow_mutation = False
        validate_all = True

    @pydantic.validator('flavor', pre=True)
    def canonical_flavor(cls, flavor):
        flavor = FLAVOR_ALIASES.get(flavor, flavor)
        return Flavor(flavor)

    @pydantic.validator('generator', pre=True)
    def canonical_generator(cls, generator):
        generator = GENERATOR_ALIASES.get(generator, generator)
        return Generator(generator)

    @cached_property
    def primary_key(self):
        return {
            'generator': self.generator.value,
            'shared': self.shared,
            'definitions': self.definitions,
        }

    def override(self, overrides: 'Configuration') -> 'Configuration':
        # A source might provide only a subset of settings to override.
        # We can distinguish overrides in a model with the property
        # `__fields_set__`.
        fields = self.dict()
        for field in overrides.__fields_set__:
            fields[field] = getattr(overrides, field)
        return Configuration.parse_obj(fields)

    @staticmethod
    def from_file(path):
        with open(path, 'r') as file:
            return Configuration.parse_obj(toml.load(file))

    @staticmethod
    def from_all(**kwargs):
        args = Configuration.parse_obj(kwargs)
        config = Configuration()
        try:
            config = config.override(
                Configuration.from_file(
                    args.source_directory / '.cupcake.toml'
                )
            )
        except FileNotFoundError:
            pass
        config = config.override(args)
        return config
