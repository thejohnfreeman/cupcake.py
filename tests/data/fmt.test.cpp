#include <vector>

#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include <doctest/doctest.h>
#include <fmt/ranges.h>

TEST_CASE("range format") {
    std::vector<int> v = {1, 2, 3};
    CHECK(fmt::format("{}", v) == "[1, 2, 3]");
}
