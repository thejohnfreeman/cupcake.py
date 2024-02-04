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

class Expression(AbstractExpression):
    def __init__(self, function):
        self.function = function
    def __call__(self, subject):
        return self.function(subject)

class BinaryExpression(AbstractExpression):
    def __init__(self, op, lhs, rhs):
        self.op = op
        self.lhs = lhs
        self.rhs = rhs
    def __call__(self, subject):
        return self.op(
            evaluate(self.lhs, subject), evaluate(self.rhs, subject)
        )

class Subject(AbstractExpression):
    def __repr__(self):
        return 'subject'

def evaluate(expr, subject):
    try:
        return expr(subject) if isinstance(expr, AbstractExpression) else expr
    except BaseException as error:
        return error

def expression():
    def decorator(fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            return Expression(lambda subject: fn(subject, *args, **kwargs))
        return decorated
    return decorator

subject = Subject()
