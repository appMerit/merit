import merit
from pydantic import BaseModel
from merit.testing.case import Case, CaseAssertion

# Checkers


@merit.checker
def equals(actual: str | list | dict | set, reference: str | list | dict | set) -> bool:
    return actual == reference


@merit.checker
def greater_than(actual: int | float, reference: int | float) -> bool:
    return actual > reference


@merit.sut
def agent(prompt: str) -> str:
    if "France" in prompt:
        return "Paris"
    elif "Germany" in prompt:
        return "Berlin"
    elif "Metallica" in prompt:
        return "Metallica"
    else:
        return "Unknown"


# Simple test cases


simple_cases = [
    Case(
        sut_input_values={"prompt": "What's the capital of France?"},
        tags={"geography"},
        sut_output_assertions=[
            CaseAssertion(checker=equals, reference="Paris")
            ]
        ),
    Case(
        sut_input_values={"prompt": "What's the capital of Germany?"}, 
        tags={"geography"},
        sut_output_assertions=[
            CaseAssertion(checker=equals, reference="Berlin"),
            ]
        ),
    Case(
        sut_input_values={"prompt": "Best rock band in the world?"}, 
        tags={"music"},
        sut_output_assertions=[
            CaseAssertion(checker=equals, reference="Metallica"),
            ]
        )
    ]


@merit.iter_cases(simple_cases) # Runs merit_simple_cases once for each case in simple_cases
async def merit_simple_cases(case: Case):
    """Call agent with case input values and assert output directly."""
    prompt = case.sut_input_values["prompt"]
    result = agent(prompt)
    assert result is not None

    if "geography" in case.tags:
        if "France" in prompt:
            assert equals(result, "Paris")
        elif "Germany" in prompt:
            assert equals(result, "Berlin")
        else:
            raise ValueError("Unknown prompt")
 
    elif "music" in case.tags:
        assert equals(result, "Metallica")
    else:
        raise ValueError("Unknown tag")


@merit.iter_cases(simple_cases)
async def merit_simple_cases_1(case: Case):
    """Call agent with case input values and loop through output assertions."""
    result = agent(**case.sut_input_values)
    assert result is not None

    for assertion in case.sut_output_assertions:
        await assertion.execute_assertion(case.id, result)


@merit.iter_cases(simple_cases)
async def merit_simple_cases_2(case: Case):
    """Call agent with case input values and run output assertions using case.assert_sut_output."""
    result = agent(**case.sut_input_values)
    assert result is not None
    await case.assert_sut_output(result)


@merit.iter_cases(simple_cases).where(lambda case: "geography" in case.tags)
async def merit_simple_cases_3(case: Case):
    """Filter cases by tags and assert output directly."""
    result = agent(**case.sut_input_values)
    assert result in ["Paris", "Berlin"]


@merit.iter_cases(simple_cases).where(lambda case: "music" in case.tags).validate_for_sut(agent)
async def merit_simple_cases_4(case: Case):
    """Filter cases by tags and validate input values match SUT signature."""
    result = agent(**case.sut_input_values)
    assert result == "Metallica"


# Cases with pointers to actual values


class CapitalInfo(BaseModel):
    capital: str
    population: int | None
    area: float | None

class RockBandInfo(BaseModel):
    band_name: str
    members: list[str]


@merit.sut
def agent_with_complex_output(prompt: str) -> CapitalInfo | RockBandInfo:
    if "France" in prompt:
        return CapitalInfo(capital="Paris", population=5000000, area=100)
    elif "Germany" in prompt:
        return CapitalInfo(capital="Berlin", population=10000000, area=200)
    elif "Metallica" in prompt:
        return RockBandInfo(band_name="Metallica", members=["James Hetfield", "Lars Ulrich", "Kirk Hammett", "Robert Trujillo"])
    else:
        raise ValueError("Unknown query")


pointer_cases = [
    Case(
        sut_input_values={"prompt": "Tell me about the capital of France"},
        tags={"geography"},
        sut_output_assertions=[
            CaseAssertion(checker=equals, reference="Paris", pointer_to_actual="/capital"),
            CaseAssertion(checker=greater_than, reference=4999999, pointer_to_actual="/population"),
            CaseAssertion(checker=greater_than, reference=199, pointer_to_actual="/area"),
            ]
        ),
    Case(
        sut_input_values={"prompt": "Tell me about the rock band Metallica"},
        tags={"music"},
        sut_output_assertions=[
            CaseAssertion(checker=equals, reference="Metallica", pointer_to_actual="/band_name"),
            CaseAssertion(checker=equals, reference=4, pointer_to_actual="/members"),
            ]
        )
    ]


@merit.iter_cases(pointer_cases).validate_for_sut(agent_with_complex_output)
async def merit_pointer_cases(case: Case):
    """Validate input values match SUT signature and assert output using pointers to actual values."""
    result = agent_with_complex_output(**case.sut_input_values)

    if "geography" in case.tags:
        assert isinstance(result, CapitalInfo)
    elif "music" in case.tags:
        assert isinstance(result, RockBandInfo)
    else:
        raise ValueError("Unknown tag")

    serialized_result = result.model_dump_json()
    await case.assert_sut_output(serialized_result)


@merit.iter_cases(pointer_cases).where(lambda case: "geography" in case.tags).validate_for_sut(agent_with_complex_output)
async def merit_pointer_cases_1(case: Case):
    """Filter cases by tags and validate input values match SUT signature and assert directly."""
    result = agent_with_complex_output(**case.sut_input_values)
    
    if result.capital == "Paris":
        assert equals(result.population, 5000000)
        assert greater_than(result.area, 199)
    elif result.capital == "Berlin":
        assert equals(result.population, 10000000)
        assert greater_than(result.area, 199)
    else:
        raise ValueError("Unknown capital")


# Parsing cases from external files with built-in parsers


@merit.iter_cases.from_csv("valid_file.csv")
async def merit_parsed_cases_from_csv(case: Case):
    """Parse cases from CSV file."""
    result = agent(**case.sut_input_values)
    await case.assert_sut_output(result)


@merit.iter_cases.from_csv("invalid_file.csv")
async def merit_parsed_cases_from_csv_1(case: Case):
    """Parse cases from CSV file."""
    result = agent(**case.sut_input_values) # Will raise ValueError here because CSV is invalid
    await case.assert_sut_output(result)


@merit.iter_cases.from_csv("invalid_file.csv").validate_for_sut(agent) # Will raise ValueError here
async def merit_parsed_cases_from_csv_2(case: Case):
    """Parse cases from CSV file."""
    result = agent(**case.sut_input_values)
    await case.assert_sut_output(result)


# Parsing cases with custom parsers


def parse_cases_from_csv(path_to_csv: str) -> list[Case]:
    """Parse cases from CSV file."""
    import csv
    with open(path_to_csv, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        return [Case(
            sut_input_values={"prompt": row["prompt"]}, 
            sut_output_assertions=[CaseAssertion(checker=equals, reference=row["reference"])]
            ) for row in reader
            ]


@merit.iter_cases(parse_cases_from_csv("valid_file.csv"))
async def merit_parsed_cases_from_csv_3(case: Case):
    """Parse cases from CSV file."""
    result = agent(**case.sut_input_values)
    await case.assert_sut_output(result)