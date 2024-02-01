{% if special %}
cupcake_find_packages(test PRIVATE)
cupcake_link_libraries(${PROJECT_NAME}.imports.test INTERFACE test)
cupcake_add_tests()
{% else %}
cupcake_find_package(doctest 2.4 PRIVATE)

target_link_libraries(${PROJECT_NAME}.imports.test INTERFACE
  doctest::doctest
)

cupcake_add_test({{ name }} {{ name }}.cpp)
target_link_libraries(${this} PUBLIC
  ${PROJECT_NAME}.imports.test
{% if with_library %}
  ${PROJECT_NAME}.lib{{ name }}
{% endif %}
)
{% endif %}
