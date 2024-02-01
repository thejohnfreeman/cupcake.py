#include <cstdio>

{% if with_library %}
#include <{{ name }}/{{ name }}.hpp>
{% endif %}

int main(int argc, const char** argv) {
{% if with_library %}
    {{ name_snake_lower }}::{{ name_snake_lower }}();
{% endif %}
    return 0;
}
