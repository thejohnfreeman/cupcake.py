cupcake_find_packages(test PRIVATE)
cupcake_link_libraries(${PROJECT_NAME}.dependencies.test INTERFACE test)

cupcake_add_test_executable({{ name }} {{ name }}.cpp)
target_link_libraries(${this} PUBLIC
  ${PROJECT_NAME}.dependencies.test
  ${PROJECT_NAME}.lib{{ name }}
)
