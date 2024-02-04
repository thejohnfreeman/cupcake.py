def identity(x):
    return x

# TODO: Consider taking this function from package `toolz`.
def compose(*callables):
    def apply(x):
        for c in reversed(callables):
            x = c(x)
        return x
    return apply
