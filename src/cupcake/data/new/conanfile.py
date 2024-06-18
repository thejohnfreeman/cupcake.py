from conan import ConanFile, conan_version
from conan.tools.cmake import CMake, cmake_layout
{% if special %}
from conan.tools.files import copy
{% endif %}

{% if special %}
from functools import cached_property
import json
import pathlib

{% endif %}
class {{ name | pascal }}(ConanFile):

    {% if special %}
    @cached_property
    def metadata(self):
        path = pathlib.Path(self.recipe_folder) / 'cupcake.json'
        with open(path, 'r') as file:
            return json.load(file)

    {% endif %}
    def set_name(self):
        if self.name is None:
            {% if special %}
            self.name = self.metadata['project']['name']
            {% else %}
            self.name = '{{ name }}'
            {% endif %}

    def set_version(self):
        if self.version is None:
            {% if special %}
            self.version = self.metadata['project']['version']
            {% else %}
            self.version = '0.1.0'
            {% endif %}

    {% if github %}
    user = 'github'
    channel = '{{ github }}'

    {% endif %}
    license = '{{ license }}'
    {% if author %}
    author = '{{ author }}'

    {% endif %}
    {% if url %}
    {% if special %}
    def configure(self):
        self.url = self.metadata['project']['url']
    {% else %}
    url = '{{ url }}'
    {% endif %}

    {% endif %}
    settings = 'os', 'compiler', 'build_type', 'arch'
    options = {'shared': [True, False], 'fPIC': [True, False]}
    default_options = {'shared': False, 'fPIC': True}

    requires = [
        # Available at https://conan.jfreeman.dev
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

    {% if special %}
    def export(self):
        copy(self, 'cupcake.json', self.recipe_folder, self.export_folder)

    {% endif %}
    # For out-of-source build.
    # https://docs.conan.io/en/latest/reference/build_helpers/cmake.html#configure
    no_copy_source = True

    def layout(self):
        cmake_layout(self)

    {% if special %}
    def requirements(self):
        methods = {
            'tool': 'tool_requires',
            'test': 'test_requires',
        } if conan_version.major.value == 2 else {}
        for requirement in self.metadata.get('imports', []):
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
