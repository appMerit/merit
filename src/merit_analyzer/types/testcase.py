from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class TestCase:
    input_value: Any
    expected: Any
    actual: Any
    passed: bool
    error_message: Optional[str] = None
    additional_context: Optional[str] = None