from conan import ConanFile

import json
import pathlib

class CMakeNames(ConanFile):

    options = {'requirement': ['ANY']}

    def requirements(self):
        self.requires(str(self.options.requirement))

    def generate(self):
        dep = self.dependencies[str(self.options.requirement)]
        cmake_file_name = dep.cpp_info.get_property('cmake_file_name')
        cmake_target_names = [dep.cpp_info.get_property('cmake_target_name')]
        for _, component in dep.cpp_info.get_sorted_components().items():
            cmake_target_names.append(component.get_property('cmake_target_name'))
        cmake_target_names = [x for x in set(cmake_target_names) if x]
        path = pathlib.Path(self.generators_folder) / 'output.json'
        # Conan can and will print other things to stdout,
        # so best for us to just stream to an output file.
        with path.open('w') as out:
            json.dump({
                'file': cmake_file_name,
                'targets': cmake_target_names,
            }, out)
