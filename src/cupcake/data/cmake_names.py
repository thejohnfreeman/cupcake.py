from conan import ConanFile

import json
import pathlib

class CMakeNames(ConanFile):

    options = {'requirement': ['ANY']}

    def requirements(self):
        self.requires(str(self.options.requirement))

    def generate(self):
        dependency = self.dependencies[str(self.options.requirement)]
        info = dependency.cpp_info
        name = dependency.ref.name

        targets = []
        defaults = []
        def make_component(name, info):
            component = { 'name': name }
            target = info.get_property('cmake_target_name')
            if target is None:
                target = name
            # All components should have unique targets,
            # except that the root component might conflict.
            if target in targets:
                return None
            component['target'] = target
            targets.append(target)
            if info.get_property('default_export'):
                defaults.append(target)
            aliases = info.get_property('cmake_target_aliases')
            if aliases is not None:
                component['aliases'] = aliases
            return component

        components = [
            make_component(f'{name}::{subname}', subinfo)
            for subname, subinfo in info.get_sorted_components().items()
        ]
        # The root component must come after
        # reading all the component target names.
        root = make_component(f'{name}::{name}', info)

        output = {
            'file': info.get_property('cmake_file_name'),
            'targets': defaults or targets,
        }
        if root:
            output['root'] = root
        if components:
            output['components'] = components

        path = pathlib.Path(self.generators_folder) / 'output.json'
        # Conan can and will print other things to stdout,
        # so best for us to just stream to an output file.
        with path.open('w') as out:
            json.dump(output, out)
