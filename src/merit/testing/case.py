"""Module for defining test cases and case sets."""

from __future__ import annotations

from _typeshed import SupportsTrunc
import inspect
import json
import logging
import re

from collections.abc import Callable
from typing import Any, TypeVar, cast, get_type_hints
from uuid import UUID, uuid4

import simdjson
from jsonpointer import JsonPointer
from jsonschema import Draft202012Validator, RefResolver
from merit.checkers import (
    Checker,
    CheckerResult,
    CHECKER_REGISTRY,
    make_lambda_checker
)

from pydantic import BaseModel, Field, Json, create_model, field_validator, model_validator

logger = logging.getLogger(__name__)

JSON_POINTER_PATTERN = re.compile(r"^(/([^~/]|~[01])*)*$")


class CaseAssertion(BaseModel):
    """
    A single assertion to be executed against SUT output.
    
    Uses a checker function to validate actual output against reference values.
    
    Attributes
    ----------
    checker : Checker
        Callable or string identifying the checker function to execute.
    reference : Any
        Expected value or reference data to compare against actual output.
    pointer_to_actual : str or None, optional
        JSON Pointer path to extract actual value from SUT output.
        If None, the entire SUT output is used.
    context : Any or None, optional
        Additional context data passed to the checker function.
    positive : bool, default=True
        If True, assertion succeeds when checker returns True.
        If False, assertion succeeds when checker returns False.
    strict : bool, default=True
        Whether to use strict comparison mode in the checker.
    metrics : list or None, optional
        List of metrics to collect during assertion execution.
    """
    model_config = {"arbitrary_types_allowed": True}
    
    checker: Checker
    reference: Any
    pointer_to_actual: str | None = None
    context: Any | None = None
    positive: bool = True
    strict: bool = True
    metrics: list | None = None

    @field_validator("checker", mode="before")
    @classmethod
    def resolve_checker_from_string(cls, v: Any) -> Checker:
        """
        Resolve checker from string name or lambda expression.
        
        This validator converts string representations to callable checkers.
        It supports three input formats: direct callables, lambda expressions,
        and registered checker names.
        
        Parameters
        ----------
        v : Any
            Input value to resolve into a Checker. Can be:
            - Callable: returned as-is
            - String starting with "lambda": compiled and wrapped
            - String (other): looked up in CHECKER_REGISTRY
        
        Returns
        -------
        Checker
            Resolved checker function ready for execution.
        """
        if callable(v):
            return cast(Checker, v)
        if isinstance(v, str):
            if v.startswith("lambda"):
                return make_lambda_checker(v)
            if v in CHECKER_REGISTRY:
                return CHECKER_REGISTRY[v]
            raise ValueError(f"Unknown checker: '{v}'. Available: {list(CHECKER_REGISTRY.keys())}")
        raise ValueError(f"checker must be callable or string, got {type(v)}")

    @field_validator("pointer_to_actual")
    @classmethod
    def validate_pointer_format(cls, v: str | None) -> str | None:
        """
        Validate JSON Pointer format compliance.
        
        Ensures the pointer_to_actual field conforms to RFC 6901 JSON Pointer
        specification. Valid pointers start with '/' and use '~0' and '~1'
        for escape sequences.
        
        Parameters
        ----------
        v : str or None
            JSON Pointer string to validate, or None.
        
        Returns
        -------
        str or None
            Validated JSON Pointer string, or None if input was None.
        
        Raises
        ------
        ValueError
            If the string does not match valid JSON Pointer syntax.
        """
        if v is None:
            return v
        if not JSON_POINTER_PATTERN.match(v):
            raise ValueError(f"Invalid JSON Pointer: '{v}'.")
        return v

    async def execute_assertion(self, case_id: UUID, actual: Any):
        """
        Execute the assertion by invoking the checker function.
        
        Calls the checker function with actual value, reference, context, 
        and other parameters. The result is validated against the positive 
        flag to determine pass/fail.
        
        Parameters
        ----------
        case_id : UUID
            Unique identifier of the test case executing this assertion.
        actual : Any
            Actual value extracted from SUT output to validate.
        
        Returns
        -------
        CheckerResult
            Result object containing pass/fail status and metadata.
        """
        if inspect.iscoroutinefunction(self.checker):
            checker_result = await self.checker(
                actual, self.reference, self.context, self.strict, self.metrics
            )
        elif inspect.isfunction(self.checker):
            checker_result = self.checker(
                actual, self.reference, self.context, self.strict, self.metrics
            )
        else:
            raise ValueError(f"Checker {self.checker} is not a coroutine or callable")

        checker_result.case_id = case_id

        if self.positive:
            assert checker_result
        else:
            assert not checker_result

        return checker_result


class Case(BaseModel):
    """
    A test case defining SUT inputs and output assertions.
    
    Attributes
    ----------
    id : UUID
        Unique identifier for this test case, auto-generated if not provided.
    tags : set of str
        Tags for categorizing and filtering test cases.
    metadata : dict
        Additional metadata for the test case (str, int, float, bool, or None values).
    sut_input_values : Any
        Input values to pass to the SUT function.
    sut_output_assertions : list of CaseAssertion
        List of assertions to execute against SUT output.
    """

    # Identifiers
    id: UUID = Field(default_factory=uuid4)
    tags: set[str] = Field(default_factory=set)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    
    # SUT data
    sut_input_values: Any
    sut_output_assertions: list[CaseAssertion] = Field(default_factory=list)

    async def assert_sut_output(self, serialized_sut_output: str, output_schema: dict[str, Any] | None = None) -> list[CheckerResult]:
        """
        Execute all output assertions against SUT output.
        
        Assertions with pointers are executed against the specific values
        extracted from the SUT output. Assertion without pointers are executed
        against the entire SUT output. If output_schema is provided, it is used 
        to validate the SUT output.
   
        Parameters
        ----------
        serialized_sut_output : str
            Serialized output from the SUT function execution.
        output_schema : dict or None, optional
            JSON Schema to validate output against before running assertions.
        
        Returns
        -------
        list of CheckerResult
            Results from all executed assertions.
        """
        try:
            deserialized_sut_output = json.loads(serialized_sut_output)
        except Exception as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        if output_schema is not None:
            for error in Draft202012Validator(output_schema).iter_errors(deserialized_sut_output):
                raise ValueError(error.message)

        doc = None
        checker_results = []

        for assertion in self.sut_output_assertions:
            if assertion.pointer_to_actual is None:
                actual_value = deserialized_sut_output
            else:
                if doc is None:
                    doc = simdjson.Parser().parse(serialized_sut_output.encode())
                actual_value = doc.at_pointer(assertion.pointer_to_actual)  # type: ignore[union-attr]
            if actual_value is None:
                logger.warning(
                    f"Path '{assertion.pointer_to_actual}' resolved to None for case {self.id}"
                )
                continue
            checker_result = await assertion.execute_assertion(self.id, actual_value)
            checker_results.append(checker_result)
        return checker_results

    async def assert_sut_trace(self, sut_trace: Any) -> list[CheckerResult]:
        raise NotImplementedError("Not implemented")

    async def assert_sut_environment(self, sut_environment: Any) -> list[CheckerResult]:
        raise NotImplementedError("Not implemented")



def _pointer_matches_schema(parts: list[str], schema: dict[str, Any], resolver: RefResolver) -> bool:
    """
    Validate that a JSON Pointer path can resolve through a JSON Schema.
    
    Recursively walks through JSON Schema structure following the pointer path
    segments to determine if the path is valid. Handles object properties,
    array indices, $ref resolution, and schema combiners (oneOf, anyOf, allOf).
    
    Parameters
    ----------
    parts : list of str
        JSON Pointer path segments (from JsonPointer.parts).
    schema : dict
        JSON Schema dictionary to validate against.
    resolver : RefResolver
        RefResolver instance for handling $ref resolution.
    
    Returns
    -------
    bool
        True if the path could theoretically resolve through the schema,
        False otherwise.
    """
    if not parts:
        return True

    part, *rest = parts

    if "$ref" in schema:
        _, resolved_schema = resolver.resolve(schema["$ref"])
        return _pointer_matches_schema(parts, resolved_schema, resolver)

    for combiner_key in ("oneOf", "anyOf", "allOf"):
        if combiner_key in schema:
            return any(
                _pointer_matches_schema(parts, subschema, resolver)
                for subschema in schema[combiner_key]
            )

    schema_type = schema.get("type")

    if schema_type == "object" or "properties" in schema:
        if part in schema.get("properties", {}):
            return _pointer_matches_schema(rest, schema["properties"][part], resolver)
        
        if "patternProperties" in schema:
            import re
            for pattern, pattern_schema in schema["patternProperties"].items():
                if re.search(pattern, part):
                    return _pointer_matches_schema(rest, pattern_schema, resolver)
        
        if schema.get("additionalProperties") is not False:
            if schema.get("additionalProperties") is True:
                return True if not rest else False
            if isinstance(schema.get("additionalProperties"), dict):
                return _pointer_matches_schema(rest, schema["additionalProperties"], resolver)
        
        return False

    if schema_type == "array" and part.isdigit():
        if "items" in schema:
            return _pointer_matches_schema(rest, schema["items"], resolver)
        return False

    return False


def build_io_json_schemas(func: Callable[..., Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Build JSON Schemas for function inputs and output.
    
    Parameters
    ----------
    func : Callable
        Function or method to introspect for schema generation.
    
    Returns
    -------
    tuple of (dict, dict)
        Two-element tuple containing:
        - inputs_schema : JSON Schema for function parameters
        - output_schema : JSON Schema for return value
    """
    if hasattr(func, "__merit_original_signature__"):
        sig = func.__merit_original_signature__
    else:
        sig = inspect.signature(func)
    if hasattr(func, "__merit_original_type_hints__"):
        hints = func.__merit_original_type_hints__
    else:
        hints = get_type_hints(func, include_extras=True)

    params = list(sig.parameters.values())

    if params and params[0].name in {"self", "cls"} and (
        inspect.ismethod(func) or "." in getattr(func, "__qualname__", "")
    ):
        params = params[1:]

    input_fields: dict[str, tuple[Any, Any]] = {}

    for p in params:
        name = p.name

        if p.kind is inspect.Parameter.VAR_POSITIONAL:
            annotation = hints.get(name, tuple[Any, ...])
            default = () if p.default is inspect._empty else p.default
        elif p.kind is inspect.Parameter.VAR_KEYWORD:
            annotation = hints.get(name, dict[str, Any])
            default = {} if p.default is inspect._empty else p.default
        else:
            annotation = hints.get(name, Any)
            default = ... if p.default is inspect._empty else p.default

        input_fields[name] = (annotation, default)

    return_annotation = hints.get("return", Any)

    InputsModel: type[BaseModel] = create_model(
        f"{getattr(func, '__name__', 'Callable')}Inputs",
        **input_fields, # type: ignore[arg-type]
    )  # type: ignore[call-overload]

    OutputModel: type[BaseModel] = create_model(
        f"{getattr(func, '__name__', 'Callable')}Output",
        result=(return_annotation, ...),
    )

    inputs_schema = InputsModel.model_json_schema()
    output_schema = OutputModel.model_json_schema()
    return inputs_schema, output_schema


class CaseDecorator:
    """Decorator for attaching test cases to merit functions."""
 
    def __init__(self, case_list: list[Case]):
        self.case_list = case_list
    
    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__merit_cases__ = self.case_list
        return fn

    @classmethod
    def from_csv(cls, csv_path: str) -> CaseDecorator:
        """Load test cases from a CSV file."""
 
        import csv

        parser = simdjson.Parser()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            case_list = []
            for row in reader:
                case_data = {}

                if "id" in row and row["id"].strip():
                    case_data["id"] = UUID(row["id"])

                if "tags" in row and row["tags"].strip():
                    case_data["tags"] = parser.parse(row["tags"].encode())

                if "metadata" in row and row["metadata"].strip():
                    case_data["metadata"] = parser.parse(row["metadata"].encode())

                if "sut_input_values" in row:
                    case_data["sut_input_values"] = parser.parse(
                        row["sut_input_values"].encode()
                    )
                else:
                    raise ValueError("CSV row missing required 'sut_input_values' column")

                if "sut_output_assertions" in row and row["sut_output_assertions"].strip():
                    case_data["sut_output_assertions"] = parser.parse(
                        row["sut_output_assertions"].encode()
                    )

                case = Case.model_validate(case_data)
                case_list.append(case)

        return cls(case_list)


    @classmethod
    def from_jsonl(cls, jsonl_path: str) -> CaseDecorator:
        """Load test cases from a JSONL (JSON Lines) file."""

        case_list = []
        parser = simdjson.Parser()

        with open(jsonl_path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                case_data = parser.parse(line)
                case = Case.model_validate(case_data)
                case_list.append(case)

        return cls(case_list)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> CaseDecorator:
        """Load test cases from a YAML file."""
 
        import yaml
        case_list = []

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return cls(case_list)

        if isinstance(data, list):
            for case_data in data:
                case = Case.model_validate(case_data)
                case_list.append(case)
        else:
            case = Case.model_validate(data)
            case_list.append(case)

        return cls(case_list)

    def where(self, f: Callable[[Case], bool]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Filter cases using a predicate function."""
 
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.case_list = [case for case in self.case_list if f(case)]
            return self.__call__(fn)
        return decorator
    
    def validate_for_sut(self, sut: Callable[..., Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Validate cases against SUT input/output schemas."""
 
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            input_schema, output_schema = build_io_json_schemas(sut)
            
            resolver = RefResolver.from_schema(output_schema)
            
            for case in self.case_list:
                for error in Draft202012Validator(input_schema).iter_errors(case.sut_input_values):
                    raise ValueError(f"Case {case.id}: {error.message}")
                
                for assertion in case.sut_output_assertions:
                    if assertion.pointer_to_actual is None:
                        continue
                    pointer = JsonPointer(assertion.pointer_to_actual)
                    if not _pointer_matches_schema(list(pointer.parts), output_schema, resolver):
                        raise ValueError(
                            f"Case {case.id}: Path '{assertion.pointer_to_actual}' does not match sut output schema structure"
                        )
            return self.__call__(fn)
        return decorator

def iter_cases(case_list: list[Case]) -> CaseDecorator:
    """Iterate over a list of cases."""
    return CaseDecorator(case_list)

# Some OOP abominations
iter_cases.from_csv = CaseDecorator.from_csv
iter_cases.from_jsonl = CaseDecorator.from_jsonl
iter_cases.from_yaml = CaseDecorator.from_yaml