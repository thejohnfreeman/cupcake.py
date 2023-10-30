import pytest

from cupcake import confee

@pytest.fixture()
def config():
    return confee.read('/does/not/exist')

def test_empty(config):
    assert(config() == {})

def test_not_empty(config):
    config.a = 1
    assert(config() != {})

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
    assert(config.options() is None)

def test_merge_reset(config):
    config.options.a = 1
    assert(config.options() == {'a': 1})
    opts = confee.merge({'b': 2}, ['a'], config.options, {'b': 2})
    assert(opts == {'b': 2})
    assert(config.options() is None)
