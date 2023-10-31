cmake_minimum_required(VERSION 3.16)

project({{ name }}
  VERSION 0.1.0
  {% if github %}
  HOMEPAGE_URL https://github.com/{{ github }}/{{ name }}
  {% endif %}
  LANGUAGES CXX
)

find_package(cupcake 0.4.1 REQUIRED)

cupcake_project()

# imports
target_link_libraries(${PROJECT_NAME}.dependencies PUBLIC
)

{% if with_library %}
cupcake_add_library({{ name }})
target_link_libraries(${this} PUBLIC ${PROJECT_NAME}.dependencies)

{% endif %}
{% if with_executable %}
cupcake_add_executable({{ name }})
{% if with_library %}
target_link_libraries(${this} PRIVATE ${PROJECT_NAME}.lib{{ name }})
{% else %}
target_link_libraries(${this} PRIVATE ${PROJECT_NAME}.dependencies)
{% endif %}

{% endif %}
{% if with_tests %}
cupcake_add_tests()

{% endif %}
cupcake_install_project()
cupcake_install_cpp_info()
