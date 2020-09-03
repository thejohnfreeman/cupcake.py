from cached_property import cached_property
import logging
import os
import shutil

import toml
from typeclasses.hash import fhash


class Cupcake:

    def __init__(self, configuration, force: bool = False):
        self.configuration = configuration
        self.force = force

    @cached_property
    def cupcake_cache_file(self):
        return self.configuration.build_directory / 'cupcake.toml'

    def cupcake_configuration_changed(self):
        try:
            with self.cupcake_cache_file.open('r') as file:
                prev_configuration = toml.load(file)
        except FileNotFoundError:
            logging.debug('missing Cupcake configuration file')
            return True
        next_configuration = self.configuration.primary_key
        prev_configuration_id = fhash(prev_configuration).hexdigest()
        next_configuration_id = fhash(next_configuration).hexdigest()
        # TODO: Calculate difference.
        if prev_configuration_id != next_configuration_id:
            logging.debug(
                f'changed Cupcake configuration: {prev_configuration} != {next_configuration}'
            )
            return True
        return False

    @cached_property
    def build_directory(self):
        if self.force or self.cupcake_configuration_changed():
            try:
                shutil.rmtree(self.configuration.build_directory)
            except FileNotFoundError:
                # Do not ignore other errors, like a failure to remove a file
                # because of permissions. Only ignore the error when the
                # build directory does not already exist.
                pass
            os.makedirs(self.configuration.build_directory)
            with self.cupcake_cache_file.open('w') as file:
                toml.dump(self.configuration.primary_key, file)
        return self.configuration.build_directory
