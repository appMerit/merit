"""System-Under-Test (SUT) decorator for traced test targets.

The @sut decorator registers a callable as a traced resource that can be
injected into Merit tests. All invocations are wrapped in OpenTelemetry spans,
and any LLM calls made within are automatically captured as child spans.
"""

import types
import functools
import inspect
import os
from collections.abc import Callable, Sequence
from typing import Any, ParamSpec, TypeVar

from merit.resources import Scope, resource
from merit.testing.models.case import Case
from merit.tracing import get_tracer
from pydantic.experimental.arguments_schema import generate_arguments_schema
from pydantic_core import ArgsKwargs, SchemaValidator, ValidationError


P = ParamSpec("P")
T = TypeVar("T")


def sut(
    fn: Callable[..., Any] | None = None,
    *,
    scope: Scope | str = Scope.CASE,
    method: str = "__call__",
    validate_cases: list[Case[Any]] | None = None,
) -> Any:
    """Register a callable as a traced system-under-test resource.

    Supports function factories only. The decorated function is treated as a
    resource factory and should return (or yield) either:
    - a FunctionType, MethodType, or partial to trace, or
    - an instance whose method should be traced.

    Args:
        fn: The factory function to register as SUT.
        scope: Resource scope for the factory.
        method: The method to trace for non-callable instance values.
        validate_cases: Optional test cases to validate against resolved SUT signature.

    Example:
        @sut
        def my_agent_factory(client):
            def my_agent(prompt: str) -> str:
                return client.generate(prompt)
            return my_agent

        def merit_test(my_agent_factory):
            result = my_agent("Hello")
    """
    normalized_validate_cases = list(validate_cases) if validate_cases else []

    if fn is None:
        return lambda factory: sut(
            factory,
            scope=scope,
            method=method,
            validate_cases=normalized_validate_cases,
        )

    if not isinstance(fn, types.FunctionType):
        raise TypeError(f"""@sut can only decorate functions.
        Got: {type(fn).__name__}
        Expected: FunctionType
        """)

    factory_name = fn.__name__

    def on_resolve(sut_instance: Any) -> Any:
        match sut_instance:
            case types.FunctionType() | types.MethodType() | functools.partial():
                if normalized_validate_cases:
                    _validate_cases(normalized_validate_cases, sut_instance)
                return _trace_callable(sut_instance, sut_name=factory_name)

            case _ if isinstance(getattr(sut_instance, method, None), types.MethodType):
                if normalized_validate_cases:
                    _validate_cases(normalized_validate_cases, getattr(sut_instance, method))
                return _trace_instance_method(sut_instance, sut_name=factory_name, method=method)

            case _:
                msg = f"""SUT '{factory_name}' resolved to unsupported type:
                {type(sut_instance).__name__}
                Expected a FunctionType, MethodType, or an instance with a MethodType.
                """
                raise TypeError(msg)

    return resource(
        fn,
        scope=scope,
        on_resolve=on_resolve,
    )


def _validate_cases(cases: Sequence[Case[Any]], sut: Callable[..., Any]):
    schema = generate_arguments_schema(
        sut,
        parameters_callback=(
            lambda index, name, annotation: "skip" if name in {"self", "cls"} else None
        ),
    )
    validator = SchemaValidator(schema)
    for case in cases:
        input_values = case.sut_input_values or {}
        parsed_args = ArgsKwargs(args=(), kwargs=input_values)
        validator.validate_python(parsed_args)


def _trace_callable(fn: Callable[..., Any], *, sut_name: str) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def traced_async(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(f"sut.{sut_name}") as span:
                span.set_attribute("merit.sut", True)
                span.set_attribute("merit.sut.name", sut_name)
                _set_input_attrs(span, args, kwargs)
                result = await fn(*args, **kwargs)
                _set_output_attrs(span, result)
                return result

        return traced_async

    @functools.wraps(fn)
    def traced(*args: Any, **kwargs: Any) -> Any:
        tracer = get_tracer()
        with tracer.start_as_current_span(f"sut.{sut_name}") as span:
            span.set_attribute("merit.sut", True)
            span.set_attribute("merit.sut.name", sut_name)
            _set_input_attrs(span, args, kwargs)
            result = fn(*args, **kwargs)
            _set_output_attrs(span, result)
            return result

    return traced


def _trace_instance_method(instance: Any, *, sut_name: str, method: str) -> Any:
    original_method = getattr(instance, method)

    if inspect.iscoroutinefunction(original_method):

        @functools.wraps(original_method)
        async def traced_async(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(f"sut.{sut_name}") as span:
                span.set_attribute("merit.sut", True)
                span.set_attribute("merit.sut.name", sut_name)
                _set_input_attrs(span, args, kwargs)
                result = await original_method(*args, **kwargs)
                _set_output_attrs(span, result)
                return result

        setattr(instance, method, traced_async)
        return instance

    @functools.wraps(original_method)
    def traced(*args: Any, **kwargs: Any) -> Any:
        tracer = get_tracer()
        with tracer.start_as_current_span(f"sut.{sut_name}") as span:
            span.set_attribute("merit.sut", True)
            span.set_attribute("merit.sut.name", sut_name)
            _set_input_attrs(span, args, kwargs)
            result = original_method(*args, **kwargs)
            _set_output_attrs(span, result)
            return result

    setattr(instance, method, traced)
    return instance


def _set_input_attrs(span: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    """Set input attributes on span, respecting trace content settings."""
    if os.environ.get("MERIT_TRACE_CONTENT", "true").lower() != "true":
        span.set_attribute("sut.input.count", len(args) + len(kwargs))
        return

    if args:
        span.set_attribute("sut.input.args", _truncate_repr(args))
    if kwargs:
        span.set_attribute("sut.input.kwargs", _truncate_repr(kwargs))


def _set_output_attrs(span: Any, result: Any) -> None:
    """Set output attributes on span, respecting trace content settings."""
    if os.environ.get("MERIT_TRACE_CONTENT", "true").lower() != "true":
        span.set_attribute("sut.output.type", type(result).__name__)
        return

    span.set_attribute("sut.output", _truncate_repr(result))


def _truncate_repr(value: Any, max_len: int = 1000) -> str:
    """Truncate a repr string if too long."""
    try:
        s = repr(value)
        if len(s) <= max_len:
            return s
        return s[: max_len - 3] + "..."
    except Exception:
        return "<repr-failed>"
