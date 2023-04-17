# imports
cupcake_find_package(doctest 2.4 PRIVATE)

cupcake_add_test_executable({{ name }} {{ name }}.cpp)
target_link_libraries(${this}
  {{ name }}::lib{{ name }}
  doctest::doctest
)
