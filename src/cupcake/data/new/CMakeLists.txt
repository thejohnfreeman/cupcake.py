cmake_minimum_required(VERSION 3.16)

project({{ name }}
  VERSION 0.1.0
  {% if github %}
  HOMEPAGE_URL https://github.com/{{ github }}/{{ name }}
  {% endif %}
  LANGUAGES CXX
)

find_package(cupcake 0.4.0 REQUIRED)

cupcake_project()

# imports
target_link_libraries(${PROJECT_NAME}.dependencies PUBLIC
)

cupcake_add_library({{ name }})
target_link_libraries(${this} PUBLIC ${PROJECT_NAME}.dependencies)

cupcake_add_executable({{ name }})
target_link_libraries(${this} PRIVATE ${PROJECT_NAME}.lib{{ name }})

cupcake_add_tests()

cupcake_install_project()
cupcake_install_cpp_info()
