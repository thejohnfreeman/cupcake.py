import functools
import operator

class AbstractExpression:
    def __call__(self, subject):
        return subject
    def __eq__(self, rhs):
        return BinaryExpression(operator.eq, self, rhs)
    def __getitem__(self, key):
        # This lambda is technically `operator.itemgetter(key)`.
        return Expression(lambda subject: subject[key])
    def __or__(self, rhs):
        return BinaryExpression(operator.or_, self, rhs)
    def __contains__(self, item):
        return BinaryExpression(operator.contains, self, item)

class Expression(AbstractExpression):
    def __init__(self, function):
        self.function = function
    def __call__(self, subject):
        try:
            return self.function(subject)
        except BaseException as error:
            return error

class BinaryExpression(AbstractExpression):
    def __init__(self, op, lhs, rhs):
        self.op = op
        self.lhs = lhs
        self.rhs = rhs
    def __call__(self, subject):
        return self.op(
            evaluate(self.lhs, subject), evaluate(self.rhs, subject)
        )

def contains(container, item):
    return BinaryExpression(operator.contains, container, item)

class Subject(AbstractExpression):
    def __repr__(self):
        return 'subject'

def evaluate(expr, subject):
    return expr(subject) if callable(expr) else expr

class Matcher:
    def __init__(self, expr):
        self.expr = expr
    def __eq__(self, subject):
        return evaluate(self.expr, subject)

match = Matcher

def expression():
    def decorator(fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            return Expression(lambda subject: fn(subject, *args, **kwargs))
        return decorated
    return decorator

subject = Subject()
