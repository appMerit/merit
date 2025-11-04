import csv
from typing import List

from ..types import TestCase, TestCaseValues, TestFailed, TestPassed

def parse_test_cases_from_csv(path_to_csv: str) -> List[TestCase]:
    """Parse CSV into test cases"""

    with open(path_to_csv, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        required = {
            "case_input", 
            "reference_value", 
            "output_for_assertions", 
            "passed", 
            "error_message"
            }
        missing = required.difference(reader.fieldnames or {})
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")
        
        test_cases: List[TestCase] = []

        for row in reader:
            passed_flag = row["passed"].strip().lower()
            if passed_flag not in {"true", "false"}:
                raise ValueError(f"Invalid passed flag: {row['passed']}")
            
            result = TestPassed() if passed_flag == "true" else TestFailed(errors=row["error_message"])
            test_cases.append(TestCase(
                test_case_values=TestCaseValues(
                    case_input=row["case_input"],
                    reference_value=row["reference_value"],
                ),
                output_for_assertions=row["output_for_assertions"],
                test_case_result=result,
            ))

        return test_cases