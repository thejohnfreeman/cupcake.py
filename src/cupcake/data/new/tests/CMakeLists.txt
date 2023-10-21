# imports
cupcake_find_package(doctest 2.4 PRIVATE)

target_link_libraries(${PROJECT_NAME}.dependencies.test INTERFACE
  doctest::doctest
)

cupcake_add_test_executable({{ name }} {{ name }}.cpp)
target_link_libraries(${this} PUBLIC
  ${PROJECT_NAME}.dependencies.test
  ${PROJECT_NAME}.lib{{ name }}
)
