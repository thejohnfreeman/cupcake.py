from cupcake.expression import subject, expression

def test_identity():
    expr = subject
    assert(expr(1) == 1)

def test_subject_equal():
    expr = (subject == 1)
    assert(expr(1))
    assert(not expr(2))

def test_name_match():
    expr = (subject['id'] == 1)
    assert(expr({'id': 1}))
    assert(not expr({'id': 2}))
    assert(not expr(1))

def test_both():
    expr = (subject == 1) | (subject['id'] == 1)
    assert(expr(1))
    assert(not expr(2))
    assert(expr({'id': 1}))
    assert(not expr({'id': 2}))

def test_decorator():
    # We must test with an asymmetric operation
    # to be sure the argument order is correct.
    @expression()
    def subscript(subject, key):
        return subject[key]
    expr = subscript('id') == 1
    assert(expr({'id': 1}))
    assert(not expr({'id': 2}))
    assert(not expr(1))
