cmake_minimum_required(VERSION 3.21)

{% if special %}
file(READ cupcake.json metadata)
string(JSON name GET "${metadata}" project name)
string(JSON version GET "${metadata}" project version)
string(JSON url ERROR_VARIABLE ignored GET "${metadata}" project url)
{% else %}
set(name {{ name }})
set(version 0.1.0)
{% if url %}
set(url {{ url }})
{% endif %}
{% endif %}

project(
  ${name}
  VERSION ${version}
  {% if special or url %}
  HOMEPAGE_URL ${url}
  {% endif %}
  LANGUAGES CXX
)

find_package(cupcake.cmake REQUIRED)

cupcake_project()

{% if special %}
cupcake_find_packages(main)
cupcake_link_libraries(${PROJECT_NAME}.imports.main INTERFACE main)
cupcake_find_packages(tool PRIVATE)

{% endif %}
{% if with_library %}
{% if special %}
cupcake_add_libraries()
{% else %}
cupcake_add_library({{ name }})
target_link_libraries(${this} PUBLIC ${PROJECT_NAME}.imports.main)
{% endif %}

{% endif %}
{% if with_executable %}
{% if special %}
cupcake_add_executables()
{% else %}
cupcake_add_executable({{ name }})
{% if with_library %}
target_link_libraries(${this} PRIVATE ${PROJECT_NAME}.l.{{ name }})
{% else %}
target_link_libraries(${this} PRIVATE ${PROJECT_NAME}.imports.main)
{% endif %}
{% endif %}

{% endif %}
{% if with_tests %}
cupcake_enable_testing()

{% endif %}
cupcake_install_project()
cupcake_install_cpp_info()
