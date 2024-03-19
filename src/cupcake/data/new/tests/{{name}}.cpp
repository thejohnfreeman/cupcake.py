#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include <doctest/doctest.h>

{% if with_library %}
#include <{{ name }}/{{ name }}.hpp>

{% endif %}
TEST_CASE("test case please ignore") {
    CHECK(true);
}
