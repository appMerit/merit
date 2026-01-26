from pydantic.experimental.arguments_schema import generate_arguments_schema
from pydantic_core import SchemaValidator, ArgsKwargs, ValidationError

class MyClass:
    @classmethod
    def s(cls, x: int, *args, **kwargs) -> int:
        return 1

schema = generate_arguments_schema(
    MyClass.s, 
    parameters_callback=(
        lambda index, name, annotation: 
        "skip" if name in {"self", "cls"} else None)
)
validator = SchemaValidator(schema)
args = ArgsKwargs(args=(), kwargs={"x": "not-an-int", "y": 2})

print(validator.validate_python(args))


