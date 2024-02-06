from cupcake.expression import subject, contains, expression, match

def test_identity():
    expr = subject
    assert(expr(1) == 1)

def test_subject_equal():
    pred = (subject == 1)
    assert(pred(1))
    assert(not pred(2))

def test_name_match():
    pred = (subject['id'] == 1)
    assert(pred({'id': 1}))
    assert(not pred({'id': 2}))
    assert(not pred(1))

def test_both():
    pred = (subject == 1) | (subject['id'] == 1)
    assert(pred(1))
    assert(not pred(2))
    assert(pred({'id': 1}))
    assert(not pred({'id': 2}))

def test_decorator():
    # We must test with an asymmetric operation
    # to be sure the argument order is correct.
    @expression()
    def subscript(subject, key):
        return subject[key]
    pred = subscript('id') == 1
    assert(pred({'id': 1}))
    assert(not pred({'id': 2}))
    assert(not pred(1))

def test_in():
    pred = (subject == 1)
    assert(match(pred) in [3, 2, 1])
    assert(match(pred) not in [4, 5, 6])
    assert(match(pred) not in [])

def test_contains():
    pred = contains([3, 2, 1], subject)
    assert(pred(2))
    assert(not pred(4))
