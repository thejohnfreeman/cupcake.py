cmake_minimum_required(VERSION 3.7)

project({{ name }}
  VERSION 0.1.0
  HOMEPAGE_URL https://github.com/{{ github }}/{{ name }}
  LANGUAGES CXX
)

find_package(cupcake 0.1.0 REQUIRED)

cupcake_project()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED YES)
set(CMAKE_CXX_EXTENSIONS OFF)

cupcake_add_library({{ name }})

cupcake_add_executable({{ name }})
target_link_libraries(${this} PRIVATE {{ name }}::lib{{ name }})

cupcake_add_tests()

cupcake_install_project()
