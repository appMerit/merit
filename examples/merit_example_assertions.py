"""Medium-depth probabilistic assertion examples with deterministic LLM stubs.

Run with:

    merit test examples/merit_example_assertions.py
"""

# NOTE: as LLM is not implemented yet, the probabilistic examples don't work.

from merit.assertions import (
    Facts,
    Instruction,
    PythonArray,
    PythonNumber,
    PythonObject,
    PythonString,
    Style,
    Behavior,
)


def merit_facts_explicit_and_implicit() -> None:
    """Facts assertion across explicit and implicit matches."""
    facts = Facts("The capital of France is Paris.")
    facts.explicit_in("Paris is the capital of France. It is a popular destination.") # Pass
    facts.implicit_in("France's capital city is known for the Eiffel Tower. The tower is in Paris.") # Pass
    facts.exactly_match_facts_in("Paris is the capital of France. It is a popular destination.") # Fail


def merit_facts_not_contradicted() -> None:
    """Facts assertion that guards against contradictions."""
    facts = Facts("Mike has three apples.")
    facts.not_contradicted_by("Alex has four apples.") # Pass
    facts.not_contradicted_by("Mike recently got three apples.") # Pass
    facts.not_contradicted_by("Mike sold all his apples to John.") # Fail

def merit_instruction_following() -> None:
    """Instruction assertion using deterministic pass criteria."""
    instruction = Instruction("Please respond in a formal tone with salutations.")
    instruction.is_followed_in("Dear Sir or Madam, I am writing to you today to inquire about your product.") # Pass
    instruction.is_followed_in("Hello, I am writing to you today to inquire about your product.") # Fail


def merit_style_similarity() -> None:
    """Style assertion focused on rhythm and brevity."""
    style = Style("Yo dawg how is it goin?")
    style.equals("Doing good ma man") # Pass
    style.equals("I'm doing great, thanks for asking.") # Fail


def merit_number_assertions() -> None:
    """Deterministic numeric comparisons."""
    number = PythonNumber(10)
    number.equals(10) # Pass
    number.gt(5) # Pass (10 > 5)
    number.lt(12) # Pass (10 < 12)


def merit_string_assertions() -> None:
    """Deterministic string comparisons."""
    greeting = PythonString("hello", ignore_case=True)
    greeting.equals("HELLO") # Pass
    greeting.is_prefix_of("Hello there!") # Pass
    greeting.is_suffix_of("well, hello") # Pass


def merit_array_assertions() -> None:
    """Deterministic list comparisons."""
    items = PythonArray([1, 2, 3])
    items.equals([3, 2, 1], ignore_order=True) # Pass
    items.is_subset_of([0, 1, 2, 3, 4]) # Pass
    items.has_same_length_as([10, 20, 30]) # Pass


def merit_object_assertions() -> None:
    """Deterministic dictionary comparisons."""
    user = PythonObject({"name": "Ada", "role": "engineer"})
    user.equals({"name": "Ada", "role": "engineer"}) # Pass


def merit_behavior_assertions() -> None:
    """Deterministic behavior comparisons."""
    behavior = Behavior("The agent asks if the user has any change.")
    behavior.appears_in("Hey, do you have any change?") # Pass
    behavior.absent_in("Hey, check out how much money I have.") # Fail