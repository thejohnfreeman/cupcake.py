cupcake_add_test_executable({{ name }} {{ name }}.cpp)
target_link_libraries(${this}
  {{ name }}::lib{{ name }}
  doctest::doctest
)
