#include <cstdio>

{% if with_library %}
#include <{{ name }}/{{ name }}.hpp>

{% endif %}
int main(int argc, const char** argv) {
{% if with_library %}
    {{ name | snake }}::{{ name | snake }}();
{% endif %}
    return 0;
}
