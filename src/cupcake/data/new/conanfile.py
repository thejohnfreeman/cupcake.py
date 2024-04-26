import conan
from conan.tools.cmake import CMake, cmake_layout

class {{ name | pascal }}(conan.ConanFile):
    name = '{{ name }}'
    version = '0.1.0'
    {% if github %}
    user = 'github'
    channel = '{{ github }}'
    {% endif %}

    license = '{{ license }}'
    {% if author %}
    author = '{{ author }}'
    {% endif %}
    {% if github %}
    url = 'https://github.com/{{ github }}/{{ name }}'
    {% endif %}

    settings = 'os', 'compiler', 'build_type', 'arch'
    options = {'shared': [True, False], 'fPIC': [True, False]}
    default_options = {'shared': False, 'fPIC': True}

    requires = [
        'cupcake.cmake/{{ version }}@github/thejohnfreeman',
        {% if with_tests and not special %}
        'doctest/2.4.8',
        {% endif %}
    ]
    generators = ['CMakeDeps', 'CMakeToolchain']

    exports_sources = [
        'CMakeLists.txt',
        {% if special %}
        'cupcake.json',
        {% endif %}
        'cmake/*',
        'external/*',
        'include/*',
        'src/*',
    ]

    # For out-of-source build.
    # https://docs.conan.io/en/latest/reference/build_helpers/cmake.html#configure
    no_copy_source = True

    def layout(self):
        cmake_layout(self)

    {% if special %}
    def requirements(self):
        import json
        import pathlib
        path = pathlib.Path(self.recipe_folder) / 'cupcake.json'
        with path.open('r') as file:
            metadata = json.load(file)
        methods = {
            'tool': 'tool_requires',
            'test': 'test_requires',
        } if conan.conan_version.major.value == 2 else {}
        for requirement in metadata.get('imports', []):
            groups = requirement.get('groups', [])
            group = groups[0] if len(groups) == 1 else 'main'
            method = methods.get(group, 'requires')
            getattr(self, method)(requirement['reference'])

    {% endif %}
    def config_options(self):
        if self.settings.os == 'Windows':
            del self.options.fPIC

    def build(self):
        cmake = CMake(self)
        cmake.configure(variables={'BUILD_TESTING': 'NO'})
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        path = f'{self.package_folder}/share/{self.name}/cpp_info.py'
        with open(path, 'r') as file:
            exec(file.read(), {}, {'self': self.cpp_info})
