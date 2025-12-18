"""Unit tests for CaseAssertion and Case abstractions."""

import pytest
from uuid import uuid4
from typing import Any
from pydantic import BaseModel

from merit.testing.case import Case, CaseAssertion, CaseDecorator, iter_cases
from merit.checkers.base import CheckerResult, CheckerMetadata


# Simple checker function that follows the Checker Protocol
def simple_equality_checker(
    actual: Any,
    reference: Any,
    context: str | None = None,
    strict: bool = True,
    metrics: list | None = None,
) -> CheckerResult:
    """A simple checker that returns True if actual equals reference."""
    is_equal = actual == reference
    return CheckerResult(
        checker_metadata=CheckerMetadata(
            actual=str(actual),
            reference=str(reference),
            context=context,
            strict=strict,
        ),
        value=is_equal,
        message="Values match" if is_equal else "Values do not match",
    )


class TestCaseDecorator:
    def test_basic_decoration(self):
        case1 = Case(sut_input_values={"input": "test1"})
        case2 = Case(sut_input_values={"input": "test2"})

        @iter_cases([case1, case2])
        def sample_function(input: str) -> str:
            return f"output_{input}"

        assert hasattr(sample_function, "__merit_cases__")
        assert sample_function.__merit_cases__ == [case1, case2]
        assert len(sample_function.__merit_cases__) == 2

    def test_from_csv(self, tmp_path):
        csv_file = tmp_path / "test_cases.csv"
        csv_content = "id,tags,metadata,sut_input_values,sut_output_assertions\n"
        csv_content += ',"[""tag1"",""tag2""]","{""key"":""value""}","{""input"":""test1""}","[{""checker"":""lambda actual, reference, context=None, strict=True, metrics=None: actual == reference"",""reference"":""expected""}]"\n'
        csv_content += ',"[""tag3""]","{""priority"":1}","{""input"":""test2""}",""\n'

        csv_file.write_text(csv_content)

        @iter_cases.from_csv(str(csv_file))
        def sample_function(input: str) -> str:
            return f"output_{input}"

        assert len(sample_function.__merit_cases__) == 2
        assert sample_function.__merit_cases__[0].tags == {"tag1", "tag2"}
        assert sample_function.__merit_cases__[0].metadata == {"key": "value"}
        assert sample_function.__merit_cases__[0].sut_input_values == {"input": "test1"}
        assert len(sample_function.__merit_cases__[0].sut_output_assertions) == 1
        assert sample_function.__merit_cases__[1].tags == {"tag3"}
        assert sample_function.__merit_cases__[1].metadata == {"priority": 1}
        assert sample_function.__merit_cases__[1].sut_input_values == {"input": "test2"}
        assert len(sample_function.__merit_cases__[1].sut_output_assertions) == 0

    def test_from_jsonl(self, tmp_path):
        import json

        jsonl_file = tmp_path / "test_cases.jsonl"

        # JSONL format: each JSON object on a single line
        case1 = {
            "tags": ["tag1", "tag2"],
            "metadata": {"key": "value"},
            "sut_input_values": {"input": "test1"},
            "sut_output_assertions": [
                {
                    "checker": "lambda actual, reference, context=None, strict=True, metrics=None: actual == reference",
                    "reference": "expected",
                }
            ],
        }
        case2 = {
            "tags": ["tag3"],
            "metadata": {"priority": 1},
            "sut_input_values": {"input": "test2"},
            "sut_output_assertions": [],
        }

        jsonl_content = json.dumps(case1) + "\n" + json.dumps(case2) + "\n"
        jsonl_file.write_text(jsonl_content)

        @iter_cases.from_jsonl(str(jsonl_file))
        def sample_function(input: str) -> str:
            return f"output_{input}"

        assert len(sample_function.__merit_cases__) == 2
        assert sample_function.__merit_cases__[0].tags == {"tag1", "tag2"}
        assert sample_function.__merit_cases__[0].metadata == {"key": "value"}
        assert sample_function.__merit_cases__[0].sut_input_values == {"input": "test1"}
        assert len(sample_function.__merit_cases__[0].sut_output_assertions) == 1
        assert sample_function.__merit_cases__[1].tags == {"tag3"}
        assert sample_function.__merit_cases__[1].sut_input_values == {"input": "test2"}

    def test_from_yaml_single_case(self, tmp_path):
        yaml_file = tmp_path / "single_case.yaml"
        yaml_content = """tags:
  - tag1
metadata:
  key: value
sut_input_values:
  input: test1
sut_output_assertions: []
"""
        yaml_file.write_text(yaml_content)

        @iter_cases.from_yaml(str(yaml_file))
        def sample_function(input: str) -> str:
            return f"output_{input}"

        assert len(sample_function.__merit_cases__) == 1
        assert sample_function.__merit_cases__[0].tags == {"tag1"}
        assert sample_function.__merit_cases__[0].sut_input_values == {"input": "test1"}

    def test_where_filter(self):
        case1 = Case(sut_input_values={"input": "test1"}, tags={"important"})
        case2 = Case(sut_input_values={"input": "test2"}, tags={"optional"})
        case3 = Case(sut_input_values={"input": "test3"}, tags={"important"})

        @iter_cases([case1, case2, case3]).where(lambda case: "important" in case.tags)
        def sample_function(input: str) -> str:
            return f"output_{input}"

        assert len(sample_function.__merit_cases__) == 2
        assert sample_function.__merit_cases__[0].id == case1.id
        assert sample_function.__merit_cases__[1].id == case3.id

    def test_validation_works_with_sut(self):
        from merit.testing.sut import sut

        class PydanticModel(BaseModel):
            prompt: str
            temperature: float = 0.7

        @sut
        def my_agent(prompt: str, temperature: float = 0.7) -> PydanticModel:
            return PydanticModel(prompt=prompt, temperature=temperature)

        valid_case = Case(
            sut_input_values={"prompt": "test prompt", "temperature": 0.5},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="test prompt",
                    pointer_to_actual="/prompt",
                )
            ],
        )

        @iter_cases([valid_case]).validate_for_sut(my_agent)
        def merit_test_agent_valid():
            pass

        assert merit_test_agent_valid.__merit_cases__ == [valid_case]

        invalid_case_wrong_input = Case(
            sut_input_values={"text": "test prompt", "temperature": 0.5},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="Response to: test prompt",
                    pointer_to_actual="/response",
                )
            ],
        )

        invalid_case_wrong_pointer = Case(
            sut_input_values={"prompt": "test prompt", "temperature": 0.5},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="Response to: test prompt",
                    pointer_to_actual="/answer",
                )
            ],
        )

        with pytest.raises(ValueError, match="Case"):

            @iter_cases([invalid_case_wrong_input]).validate_for_sut(my_agent)
            def merit_test_agent_invalid_wrong_input():
                pass

        with pytest.raises(ValueError, match="does not match sut output schema structure"):

            @iter_cases([invalid_case_wrong_pointer]).validate_for_sut(my_agent)
            def merit_test_agent_invalid_wrong_pointer():
                pass

    def test_validation_works_with_no_sut(self):
        from merit.testing.sut import sut

        class PydanticModel(BaseModel):
            prompt: str
            temperature: float = 0.7

        def my_agent(prompt: str, temperature: float = 0.7) -> PydanticModel:
            return PydanticModel(prompt=prompt, temperature=temperature)

        valid_case = Case(
            sut_input_values={"prompt": "test prompt", "temperature": 0.5},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="test prompt",
                    pointer_to_actual="/prompt",
                )
            ],
        )

        @iter_cases([valid_case]).validate_for_sut(my_agent)
        def merit_test_agent_valid():
            pass

        assert merit_test_agent_valid.__merit_cases__ == [valid_case]

        invalid_case_wrong_input = Case(
            sut_input_values={"text": "test prompt", "temperature": 0.5},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="Response to: test prompt",
                    pointer_to_actual="/response",
                )
            ],
        )

        invalid_case_wrong_pointer = Case(
            sut_input_values={"prompt": "test prompt", "temperature": 0.5},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="Response to: test prompt",
                    pointer_to_actual="/answer",
                )
            ],
        )

        with pytest.raises(ValueError, match="Case"):

            @iter_cases([invalid_case_wrong_input]).validate_for_sut(my_agent)
            def merit_test_agent_invalid_wrong_input():
                pass

        with pytest.raises(ValueError, match="does not match sut output schema structure"):

            @iter_cases([invalid_case_wrong_pointer]).validate_for_sut(my_agent)
            def merit_test_agent_invalid_wrong_pointer():
                pass

    def test_chaining_works(self, tmp_path):
        from merit.testing.sut import sut

        class PydanticModel(BaseModel):
            prompt: str
            temperature: float = 0.7

        @sut
        def my_agent(prompt: str, temperature: float = 0.7) -> PydanticModel:
            return PydanticModel(prompt=prompt, temperature=temperature)

        csv_file = tmp_path / "test_cases.csv"
        csv_content = "id,tags,metadata,sut_input_values,sut_output_assertions\n"
        csv_content += ',"[""important""]","{}","{""prompt"":""test prompt"",""temperature"":0.5}","[{""checker"":""lambda actual, reference, context=None, strict=True, metrics=None: actual == reference"",""reference"":""Response to: test prompt"",""pointer_to_actual"":""/prompt""}]"\n'
        csv_content += ',"[""optional""]","{}","{""prompt"":""test prompt"",""temperature"":0.5}","[{""checker"":""lambda actual, reference, context=None, strict=True, metrics=None: actual == reference"",""reference"":""Response to: test prompt"",""pointer_to_actual"":""/prompt""}]"\n'
        csv_content += ',"[""important""]","{}","{""prompt"":""test prompt"",""temperature"":0.5}","[{""checker"":""lambda actual, reference, context=None, strict=True, metrics=None: actual == reference"",""reference"":""Response to: test prompt"",""pointer_to_actual"":""/prompt""}]"\n'
        csv_file.write_text(csv_content)

        @(
            iter_cases.from_csv(str(csv_file))
            .where(lambda case: "important" in case.tags)
            .validate_for_sut(my_agent)
        )
        def merit_test_agent_chaining(input: str) -> str:
            return f"output_{input}"

        assert len(merit_test_agent_chaining.__merit_cases__) == 2
        assert merit_test_agent_chaining.__merit_cases__[0].tags == {"important"}
        assert merit_test_agent_chaining.__merit_cases__[1].tags == {"important"}


class TestCaseAssertion:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "positive,actual_value,should_pass,expected_result",
        [
            (True, "expected", True, True),  # positive=True, checker returns True → pass
            (True, "different", False, False),  # positive=True, checker returns False → fail
            (False, "different", True, False),  # positive=False, checker returns False → pass
            (False, "expected", False, True),  # positive=False, checker returns True → fail
        ],
    )
    async def test_assertion_positive_negative_logic(
        self, positive, actual_value, should_pass, expected_result
    ):
        assertion = CaseAssertion(
            checker=simple_equality_checker,
            reference="expected",
            positive=positive,
        )
        case_id = uuid4()

        if should_pass:
            result = await assertion.execute_assertion(case_id, actual_value)
            assert result.value is expected_result
            assert result.case_id == case_id
        else:
            with pytest.raises(AssertionError):
                await assertion.execute_assertion(case_id, actual_value)

    @pytest.mark.parametrize(
        "pointer,should_pass",
        [
            ("/path/to/value", True),
            ("invalid_pointer_no_slash", False),
        ],
    )
    def test_json_pointer_validation(self, pointer, should_pass):
        if should_pass:
            assertion = CaseAssertion(
                checker=simple_equality_checker,
                reference="value",
                pointer_to_actual=pointer,
            )
            assert assertion.pointer_to_actual == pointer
        else:
            with pytest.raises(ValueError, match="Invalid JSON Pointer"):
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="value",
                    pointer_to_actual=pointer,
                )

    @pytest.mark.asyncio
    async def test_lambda_checker_string(self):
        assertion = CaseAssertion(
            checker="lambda actual, reference, context=None, strict=True, metrics=None: actual == reference",  # type: ignore[arg-type]
            reference="expected_value",
            positive=True,
        )
        case_id = uuid4()

        from merit.checkers.base import CheckerResult as CR

        assert callable(assertion.checker)

        result = await assertion.execute_assertion(case_id, "expected_value")
        assert isinstance(result, CR)
        assert result.value is True

    def test_registry_checker_string(self):
        """CaseAssertion should resolve checker from CHECKER_REGISTRY by name."""
        from unittest.mock import patch
        from merit.checkers.base import CheckerResult, CheckerMetadata

        def mock_checker(actual, reference, context=None, strict=True, metrics=None):
            return CheckerResult(
                checker_metadata=CheckerMetadata(
                    actual=str(actual),
                    reference=str(reference),
                    context=context,
                    strict=strict,
                ),
                value=actual == reference,
                message="Mock checker result",
            )

        with patch("merit.testing.case.CHECKER_REGISTRY", {"mock_checker": mock_checker}):
            assertion = CaseAssertion(
                checker="mock_checker",  # type: ignore[arg-type]
                reference="test_value",
                positive=True,
            )

            # Verify the checker was resolved from registry
            assert callable(assertion.checker)
            assert assertion.checker == mock_checker


class TestCase:
    @pytest.mark.asyncio
    async def test_case_assert_sut_output_with_passing_assertion(self):
        case = Case(
            sut_input_values={"input": "test"},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="expected_value",
                )
            ],
        )

        import json

        sut_output = "expected_value"
        results = await case.assert_sut_output(sut_output)

        assert len(results) == 1
        assert results[0].value is True
        assert results[0].case_id == case.id

    @pytest.mark.asyncio
    async def test_case_assert_sut_output_with_failing_assertion(self):
        case = Case(
            sut_input_values={"input": "test"},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="expected_value",
                    pointer_to_actual="",
                )
            ],
        )

        sut_output = '{"result": "wrong_value"}'

        with pytest.raises(AssertionError):
            await case.assert_sut_output(sut_output)

    @pytest.mark.asyncio
    async def test_case_assert_sut_output_without_pointer(self):
        case = Case(
            sut_input_values={"input": "test"},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference={"key": "value"},
                )
            ],
        )

        sut_output = '{"key": "value"}'
        results = await case.assert_sut_output(sut_output)

        assert len(results) == 1
        assert results[0].value is True

    @pytest.mark.asyncio
    async def test_case_assert_sut_output_with_multiple_assertions(self):
        case = Case(
            sut_input_values={"input": "test"},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="value1",
                    pointer_to_actual="/field1",
                ),
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="value2",
                    pointer_to_actual="/field2",
                ),
            ],
        )

        sut_output = '{"field1": "value1", "field2": "value2"}'
        results = await case.assert_sut_output(sut_output)

        assert len(results) == 2
        assert all(r.value is True for r in results)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sut_output,schema,should_pass",
        [
            (
                '{"result": "value"}',
                {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                },
                True,
            ),
            (
                '{"other_field": "value"}',
                {
                    "type": "object",
                    "properties": {"required_field": {"type": "string"}},
                    "required": ["required_field"],
                },
                False,
            ),
        ],
    )
    async def test_case_assert_sut_output_with_schema_validation(
        self, sut_output, schema, should_pass
    ):
        case = Case(
            sut_input_values={"input": "test"},
            sut_output_assertions=[
                CaseAssertion(
                    checker=simple_equality_checker,
                    reference="value",
                    pointer_to_actual="/result" if should_pass else None,
                )
            ],
        )

        if should_pass:
            results = await case.assert_sut_output(sut_output, schema)
            assert len(results) == 1
        else:
            with pytest.raises(ValueError):
                await case.assert_sut_output(sut_output, schema)
