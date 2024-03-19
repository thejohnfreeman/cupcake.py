#ifndef {{ name | snake | upper }}_{{ name | snake | upper }}_HPP
#define {{ name | snake | upper }}_{{ name | snake | upper }}_HPP

#include <{{ name }}/export.hpp>

namespace {{ name | snake }} {

{{ name | snake | upper }}_EXPORT void {{ name | snake }}();

}

#endif
