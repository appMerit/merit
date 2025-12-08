"""Simple example of using Merit testing framework."""

# NOTE: moved current example into comments until we figure out Case

# from merit import Case, PassRate, RawValue, Suite

# # 1. Define your system under test
# def simple_chatbot(prompt: str) -> str:
#     """A simple chatbot that adds 'Hello, ' prefix."""
#     return f"Hello, {prompt}!"


# # 2. Create test cases
# cases = [
#     Case(input="World", assertions=[RawValue("Hello, World!")]),
#     Case(input="Alice", assertions=[RawValue("Hello, Alice!")]),
#     Case(input="Bob", assertions=[RawValue("Hello, Bob!")]),
# ]

# # 3. Create suite with assertions
# suite = Suite(
#     name="Chatbot Tests",
#     cases=cases,
#     assertions=lambda actual: RawValue("Hello", ignore_case=True).starts_with(actual),
# )

# # 4. Run tests
# results = suite.run(simple_chatbot)

# # 5. Calculate metrics
# pass_rate = PassRate()
# score = pass_rate(results)

# # Show individual results
# print("\nDetailed Results:")
# for result in results:
#     status = "✓" if result.passed else "✗"
#     print(f"{status} {result.assertion_name}: {result.message or 'passed'}")
