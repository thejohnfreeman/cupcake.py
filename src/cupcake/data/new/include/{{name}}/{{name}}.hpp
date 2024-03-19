#ifndef {{ namespaces | map('snake') | join('_') | upper }}_{{ name | snake | upper }}_HPP
#define {{ namespaces | map('snake') | join('_') | upper }}_{{ name | snake | upper }}_HPP

#include <{{ namespaces[0] }}/export.hpp>

{% for namespace in namespaces %}
namespace {{ namespace | snake }} {
{% endfor %}

{{ namespaces[0] | snake | upper }}_EXPORT void {{ name | snake }}();

{% for namespace in namespaces %}
}
{% endfor %}

#endif
