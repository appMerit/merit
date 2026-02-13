import merit

def func(a: int, b: int) -> int:
    return a + b

@merit.resource
def some_sut():
    return func

def merit_sut(some_sut):
    assert some_sut(1, 2) == 3