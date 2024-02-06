import pytest

from cupcake import confee
from cupcake.expression import subject, match

@pytest.fixture(params=['toml', 'json'])
def config(request):
    """Return an empty config with a non-existent path."""
    return confee.read(f'/does/not/exist.{request.param}')

def test_empty(config):
    assert(config() == {})

def test_delete_recursive(config):
    config.a.b.c = 1
    assert(config.a.b.c)
    confee.delete(config.a.b.c)
    assert(not config.a.b.c)
    assert(not config.a.b)
    assert(not config.a)

def test_delete_op_recursive(config):
    config.a.b.c = 1
    assert(config.a.b.c)
    del config.a.b.c
    assert(not config.a.b.c)
    assert(not config.a.b)
    assert(not config.a)

def test_not_empty(config):
    config.a = 1
    assert(config() != {})

def test_no_default(config):
    with pytest.raises(KeyError):
        config.a()

def test_default(config):
    assert(config.a(1) == 1)

def test_set_keys_get_dict(config):
    config.a = 1
    config.b = 2
    assert(config() == {'a': 1, 'b': 2})

def test_merge_add(config):
    opts = confee.merge({'a': 1}, [], config.options, {})
    assert(opts == {'a': 1})
    assert(config.options() == {'a': 1})

def test_merge_remove(config):
    opts = confee.merge({}, ['a'], config.options, {'a': 1})
    assert(opts == {})
    assert(config.options() == {})

def test_merge_default(config):
    opts = confee.merge({}, [], config.options, {'a': 1})
    assert(opts == {'a': 1})
    with pytest.raises(KeyError):
        config.options()

def test_merge_reset(config):
    config.options.a = 1
    assert(config.options() == {'a': 1})
    opts = confee.merge({'b': 2}, ['a'], config.options, {'b': 2})
    assert(opts == {'b': 2})
    with pytest.raises(KeyError):
        config.options()

def test_proxy_equal(config):
    config.a = 1
    assert(config.a != 1)
    assert(config.a == config.a)

def test_add_library_to_empty(config):
    name = 'abc'
    assert(not config.groups)
    confee.add(
        config.groups.main.libraries,
        {'name': name, 'links': ['${PROJECT_NAME}.imports.main'] },
    )
    assert(match(subject['name'] == name) in config.groups.main.libraries())

def test_add_library_to_non_empty(config):
    config.groups.main.libraries = [
        {'name': 'xyz', 'links': ['${PROJECT_NAME}.imports.main'] },
    ]
    name = 'abc'
    confee.add(
        config.groups.main.libraries,
        {'name': name, 'links': ['${PROJECT_NAME}.imports.main'] },
    )
    assert(match(subject['name'] == name) in config.groups.main.libraries())

def test_remove_library(config):
    name = 'xyz'
    config.groups.main.libraries = [
        {'name': name, 'links': ['${PROJECT_NAME}.imports.main'] },
    ]
    assert(config.groups.main.libraries)
    confee.remove_if(config.groups.main.libraries, subject['name'] == name)
    assert(not config.groups.main.libraries)

def test_unlink_library(config):
    target = 'removed'
    config.groups.main.libraries = [
        {'name': 'abc', 'links': ['${PROJECT_NAME}.imports.main'] },
        {'name': 'def', 'links': ['abc', target] },
        {'name': 'xyz', 'links': [{ 'target': target, 'scope': 'PUBLIC' }] },
    ]
    config.groups.test.tests = [
        {'name': 'abc', 'links': ['${PROJECT_NAME}.imports.main'] },
        {'name': 'def', 'links': ['abc', target] },
        {'name': 'xyz', 'links': [{ 'target': target, 'scope': 'PUBLIC' }] },
    ]
    confee.remove_if(
        config.groups[:][{'libraries', 'executables', 'tests'}][:].links,
        (subject == target) | (subject['target'] == target),
    )
    assert(config.groups.main.libraries() == [
        {'name': 'abc', 'links': ['${PROJECT_NAME}.imports.main'] },
        {'name': 'def', 'links': ['abc'] },
        {'name': 'xyz' },
    ])
    assert(config.groups.test.tests() == [
        {'name': 'abc', 'links': ['${PROJECT_NAME}.imports.main'] },
        {'name': 'def', 'links': ['abc'] },
        {'name': 'xyz' },
    ])

@pytest.fixture()
def nested(config):
    config.scalar = 1
    config.array = [1, 2, 3]
    config.object = {'a': 1, 'b': 2, 'c': 3}
    return config

def test_iter_scalar(nested):
    assert(list(nested.scalar) == [nested.scalar])
    assert(list(iter(nested.scalar)) == [nested.scalar])

def test_slice(nested):
    assert(list(nested.array[:]) == [nested.array[0], nested.array[1], nested.array[2]])
    assert(list(nested.array[1:2]) == [nested.array[1]])

    assert(list(nested.array[[1,2]]) == [nested.array[1], nested.array[2]])
    assert(list(nested.array[(1,2)]) == [nested.array[1], nested.array[2]])
    assert( set(nested.array[{1,2}]) == {nested.array[1], nested.array[2]})

    # Respect insertion order.
    assert(list(nested.object[:]) == [nested.object.a, nested.object.b, nested.object.c])

    assert(list(nested.object[['a','b']]) == [nested.object.a, nested.object.b])
    assert(list(nested.object[('a','b')]) == [nested.object.a, nested.object.b])
    assert( set(nested.object[{'a','b'}]) == {nested.object.a, nested.object.b})

@pytest.fixture(params=[None, 0, 1, 2, 3, 100, -1, -100])
def start(request):
    return request.param

@pytest.fixture(params=[None, 0, 1, 2, 3, 100, -1, -100])
def stop(request):
    return request.param

@pytest.fixture(params=[None, 1, 2, 3, 100, -1, -100])
def step(request):
    return request.param

@pytest.fixture(params=[[], [0], [0, 1], [0, 1, 2]])
def indices(request):
    return request.param

def test_to_indices(start, stop, step, indices):
    s = slice(start, stop, step)
    assert(list(confee.to_indices(s, len(indices))) == indices[s])
