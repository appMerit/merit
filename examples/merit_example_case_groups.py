"""Examples for `CaseGroup` and `iter_case_groups`."""

from __future__ import annotations

from pydantic import BaseModel

import merit
from merit import Case, CaseGroup


# =============================== Define SUT ===============================


def simple_chatbot(prompt: str) -> str:
    if "verbose" in prompt:
        answer = "What an excellent question! The answer is: "
    else:
        answer = ""
    if "France" in prompt:
        return answer + "Paris"
    if "Germany" in prompt:
        return answer + "Berlin"
    if "rock" in prompt:
        return answer + "Metallica"
    if "pop" in prompt:
        return answer + "Lady Gaga"
    raise ValueError(f"Unknown query: {prompt}")


# =============================== Prepare grouped cases ===============================

# Models for references


class ExampleCaseReferences(BaseModel):
    expected: str
    max_len: int
    min_len: int


class ExampleGroupReferences(BaseModel):
    stop_keywords: list[str]


# Case groups

geography_group = CaseGroup[ExampleCaseReferences, ExampleGroupReferences](
    name="geography",
    references=ExampleGroupReferences(
        stop_keywords=["Lol", "Kek"],
    ),
    cases=[
        Case[ExampleCaseReferences](
            tags={"geography"},
            metadata={"verbose": False},
            references=ExampleCaseReferences(expected="Paris", max_len=10, min_len=1),
            sut_input_values={"prompt": "What is the capital of France? Be concise."},
        ),
        Case[ExampleCaseReferences](
            tags={"geography"},
            metadata={"verbose": True},
            references=ExampleCaseReferences(expected="Berlin", max_len=10000, min_len=20),
            sut_input_values={"prompt": "What is the capital of Germany? Be verbose."},
        ),
    ],
    min_passes=2,  # strict: both geography cases must pass
)

music_group = CaseGroup[ExampleCaseReferences, ExampleGroupReferences](
    name="music",
    references=ExampleGroupReferences(
        stop_keywords=["Lol", "Kek"],
    ),
    cases=[
        Case[ExampleCaseReferences](
            tags={"music"},
            metadata={"verbose": True},
            references=ExampleCaseReferences(expected="Metallica", max_len=10000, min_len=20),
            sut_input_values={"prompt": "What is the best rock band? Be verbose."},
        ),
        Case[ExampleCaseReferences](
            tags={"music"},
            metadata={"verbose": False},
            references=ExampleCaseReferences(expected="Lady Gaga", max_len=10, min_len=1),
            sut_input_values={"prompt": "What is the best pop band? Be concise."},
        ),
    ],
    min_passes=1,  # tolerant: only one music case must pass for this group to pass
)

all_groups = [geography_group, music_group]

# =============================== Run tests ===============================


@merit.sut(validate_cases=[case for group in all_groups for case in group.cases])
def chatbot():
    return simple_chatbot


@merit.iter_case_groups(*all_groups)
def merit_iter_case_groups_with_validation(
    group: CaseGroup[ExampleCaseReferences, ExampleGroupReferences],
    case: Case[ExampleCaseReferences],
    chatbot,
):
    response = chatbot(**case.sut_input_values)

    # case-level references
    assert case.references.expected in response
    assert len(response) <= case.references.max_len
    assert len(response) >= case.references.min_len

    # group-level references
    assert not any(keyword in response for keyword in group.references.stop_keywords)
