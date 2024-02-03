import pytest

from cupcake import confee

@pytest.fixture(params=['toml', 'json'])
def config(request):
    """Return an empty config with a non-existent path."""
    return confee.read(f'/does/not/exist.{request.param}')

def test_empty(config):
    assert(config() == {})

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
