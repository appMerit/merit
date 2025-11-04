"""Calculator module with intentional bugs for testing."""


def divide(a, b):
    """Divide two numbers - BUG: No zero check!"""
    return a / b


def calculate_average(numbers):
    """Calculate average - BUG: Doesn't handle empty list!"""
    total = sum(numbers)
    return total / len(numbers)


def safe_divide(numerator, denominator):
    """Supposedly safe division - BUG: Returns wrong type on error!"""
    if denominator == 0:
        return "Error"  # Should raise exception or return None
    return numerator / denominator


def get_percentage(value, total):
    """Calculate percentage - BUG: No validation!"""
    return (value / total) * 100

