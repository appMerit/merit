"""Tests for merit.testing.sut module."""

import asyncio
import inspect
import json

import pytest

from merit.resources import ResourceResolver, Scope, clear_registry, get_registry, resource
from merit.testing.sut import sut
from merit.tracing import clear_traces, set_trace_output_path


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


@pytest.fixture(scope="module", autouse=True)
def setup_tracing_once(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("traces")
    set_trace_output_path(output_path=tmp_dir / "sut_traces.jsonl")


@pytest.fixture(autouse=True)
def clear_traces_each(tmp_path):
    set_trace_output_path(tmp_path / "traces.jsonl")
    clear_traces()
    yield
    clear_traces()


class TestSutDecorator:
    def test_rejects_classes(self):
        with pytest.raises(TypeError, match="only decorate functions"):
            sut(type("MySUT", (), {}))

    def test_registers_resource_with_case_scope_by_default(self):
        @sut
        def my_sut():
            return lambda x: x * 2

        registry = get_registry()
        assert "my_sut" in registry
        assert registry["my_sut"].scope == Scope.CASE

    def test_scope_is_user_defined(self):
        @sut(scope=Scope.SESSION)
        def my_session_sut():
            return lambda x: x

        registry = get_registry()
        assert registry["my_session_sut"].scope == Scope.SESSION

    def test_resource_dependencies_are_captured_from_factory_signature(self):
        @resource
        def dep():
            return 3

        @sut
        def my_sut(dep):
            return lambda x: x + dep

        registry = get_registry()
        assert registry["my_sut"].dependencies == ["dep"]

    def test_registry_key_is_factory_function_name(self):
        @sut
        def original_name():
            return lambda: "ok"

        registry = get_registry()
        assert "original_name" in registry


class TestSutResolution:
    @pytest.mark.asyncio
    async def test_wraps_returned_callable(self):
        @sut
        def adder():
            def run(x: int, y: int) -> int:
                return x + y

            return run

        resolver = ResourceResolver(get_registry())
        resolved = await resolver.resolve("adder")

        assert callable(resolved)
        assert resolved(2, 3) == 5
        assert inspect.signature(resolved) == inspect.signature(adder())

    @pytest.mark.asyncio
    async def test_wraps_returned_async_callable(self):
        @sut
        def async_adder():
            async def run(x: int, y: int) -> int:
                await asyncio.sleep(0.001)
                return x + y

            return run

        resolver = ResourceResolver(get_registry())
        resolved = await resolver.resolve("async_adder")
        assert await resolved(2, 3) == 5

    @pytest.mark.asyncio
    async def test_wraps_returned_instance_method_in_place(self):
        class Pipeline:
            def __init__(self) -> None:
                self.factor = 4

            def run(self, x: int) -> int:
                return x * self.factor

        @sut(method="run")
        def pipeline():
            return Pipeline()

        resolver = ResourceResolver(get_registry())
        resolved = await resolver.resolve("pipeline")

        assert isinstance(resolved, Pipeline)
        assert resolved.factor == 4
        assert resolved.run(3) == 12

    @pytest.mark.asyncio
    async def test_raises_on_none_return(self):
        @sut
        def bad_sut():
            return None

        resolver = ResourceResolver(get_registry())
        with pytest.raises(RuntimeError, match="Hook on_resolve failed"):
            await resolver.resolve("bad_sut")

    @pytest.mark.asyncio
    async def test_raises_when_method_missing_for_non_callable_instance(self):
        class NoRun:
            value = 1

        @sut(method="run")
        def no_run():
            return NoRun()

        resolver = ResourceResolver(get_registry())
        with pytest.raises(RuntimeError, match="resolved to unsupported type"):
            await resolver.resolve("no_run")


class TestSutTracing:
    @pytest.mark.asyncio
    async def test_callable_sut_creates_span(self):
        @sut
        def traced_sut():
            def run(x: int) -> int:
                return x * 2

            return run

        resolver = ResourceResolver(get_registry())
        resolved = await resolver.resolve("traced_sut")
        resolved(5)

        from merit.tracing.lifecycle import _exporter

        assert _exporter is not None
        lines = _exporter.output_path.read_text().strip().splitlines()
        span_names = [json.loads(line)["name"] for line in lines]
        assert "sut.traced_sut" in span_names

    @pytest.mark.asyncio
    async def test_instance_method_sut_creates_span(self):
        class Service:
            def run(self, value: str) -> str:
                return f"ok:{value}"

        @sut(method="run")
        def traced_service():
            return Service()

        resolver = ResourceResolver(get_registry())
        resolved = await resolver.resolve("traced_service")
        assert resolved.run("hello") == "ok:hello"

        from merit.tracing.lifecycle import _exporter

        assert _exporter is not None
        lines = _exporter.output_path.read_text().strip().splitlines()
        span_names = [json.loads(line)["name"] for line in lines]
        assert "sut.traced_service" in span_names

    @pytest.mark.asyncio
    async def test_sut_spans_have_merit_attributes(self):
        @sut
        def my_test_function():
            def run(x: int) -> int:
                return x

            return run

        resolver = ResourceResolver(get_registry())
        resolved = await resolver.resolve("my_test_function")
        resolved(1)

        from merit.tracing.lifecycle import _exporter

        assert _exporter is not None
        lines = _exporter.output_path.read_text().strip().splitlines()

        span = None
        for line in lines:
            parsed = json.loads(line)
            if parsed["name"] == "sut.my_test_function":
                span = parsed
                break

        assert span is not None
        assert span["attributes"].get("merit.sut") is True
        assert span["attributes"].get("merit.sut.name") == "my_test_function"
