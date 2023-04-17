from conan import ConanFile
from conan.tools.cmake import CMake

class CMakeFileName(ConanFile):
    name = 'CMakeFileName'
    version = '1.0.0'

    settings = 'os', 'compiler', 'build_type', 'arch'

    requires = ['{{ ref }}']

    def generate(self):
        deps = self.dependencies.direct_host.values()
        assert(len(deps)) == 1
        dep = next(iter(deps))
        name = dep.cpp_info.get_property("cmake_file_name") or dep.ref.name
        # Conan can and will print other things to stdout,
        # so best for us to just stream to an output file.
        with open('cmake_file_name.txt', 'w') as file:
            file.write(name)
