"""Test result parsing and validation."""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from ..models.test_result import TestResult, TestResultBatch


class TestParser:
    """Parse test results from various formats."""

    def __init__(self):
        """Initialize test parser."""
        self.supported_formats = ["json", "csv", "pytest_json", "junit_xml"]

    def parse(self, data: Union[str, Path, List[Dict], List[TestResult]], format: Optional[str] = None) -> TestResultBatch:
        """
        Parse test results from various sources.

        Args:
            data: Test results data (file path, JSON string, or list of dicts/TestResult objects)
            format: Format hint (json, csv, pytest_json, junit_xml, auto)

        Returns:
            TestResultBatch containing parsed test results
        """
        if isinstance(data, list):
            return self._parse_from_list(data)
        
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.exists():
                return self._parse_from_file(path, format)
            else:
                # Assume it's JSON string
                return self._parse_from_json_string(data)
        
        raise ValueError(f"Unsupported data type: {type(data)}")

    def _parse_from_list(self, data: List[Union[Dict, TestResult]]) -> TestResultBatch:
        """Parse from list of dictionaries or TestResult objects."""
        results = []
        for item in data:
            if isinstance(item, TestResult):
                results.append(item)
            elif isinstance(item, dict):
                results.append(TestResult(**item))
            else:
                raise ValueError(f"Unsupported item type in list: {type(item)}")
        
        return TestResultBatch(results=results)

    def _parse_from_file(self, file_path: Path, format: Optional[str] = None) -> TestResultBatch:
        """Parse from file."""
        if format is None:
            format = self._detect_format(file_path)
        
        if format == "json":
            return self._parse_json_file(file_path)
        elif format == "csv":
            return self._parse_csv_file(file_path)
        elif format == "pytest_json":
            return self._parse_pytest_json_file(file_path)
        elif format == "junit_xml":
            return self._parse_junit_xml_file(file_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _parse_from_json_string(self, json_string: str) -> TestResultBatch:
        """Parse from JSON string."""
        try:
            data = json.loads(json_string)
            if isinstance(data, list):
                return self._parse_from_list(data)
            elif isinstance(data, dict) and "results" in data:
                return TestResultBatch(**data)
            else:
                raise ValueError("Invalid JSON structure")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def _detect_format(self, file_path: Path) -> str:
        """Detect file format from extension and content."""
        suffix = file_path.suffix.lower()
        
        if suffix == ".json":
            # Try to detect pytest JSON format
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "report" in data:
                        return "pytest_json"
            except:
                pass
            return "json"
        elif suffix == ".csv":
            return "csv"
        elif suffix == ".xml":
            return "junit_xml"
        else:
            # Default to JSON
            return "json"

    def _parse_json_file(self, file_path: Path) -> TestResultBatch:
        """Parse JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return self._parse_from_list(data)
        elif isinstance(data, dict) and "results" in data:
            return TestResultBatch(**data)
        else:
            raise ValueError("Invalid JSON structure for test results")

    def _parse_csv_file(self, file_path: Path) -> TestResultBatch:
        """Parse CSV file."""
        results = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map CSV columns to TestResult fields
                test_result = TestResult(
                    test_id=row.get('test_id', ''),
                    test_name=row.get('test_name'),
                    input=row.get('input', ''),
                    expected_output=row.get('expected_output'),
                    actual_output=row.get('actual_output', ''),
                    status=row.get('status', 'failed'),
                    failure_reason=row.get('failure_reason'),
                    category=row.get('category'),
                    tags=row.get('tags', '').split(',') if row.get('tags') else [],
                    execution_time_ms=int(row['execution_time_ms']) if row.get('execution_time_ms') else None,
                    timestamp=row.get('timestamp'),
                    metadata={k: v for k, v in row.items() if k not in [
                        'test_id', 'test_name', 'input', 'expected_output', 'actual_output',
                        'status', 'failure_reason', 'category', 'tags', 'execution_time_ms', 'timestamp'
                    ]}
                )
                results.append(test_result)
        
        return TestResultBatch(results=results)

    def _parse_pytest_json_file(self, file_path: Path) -> TestResultBatch:
        """Parse pytest JSON report file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        results = []
        test_reports = data.get('report', {}).get('tests', [])
        
        for test in test_reports:
            # Extract test information
            test_id = test.get('nodeid', '')
            test_name = test.get('name', '')
            status = 'passed' if test.get('outcome') == 'passed' else 'failed'
            
            # Extract input/output from test metadata or call args
            input_data = ''
            expected_output = ''
            actual_output = ''
            failure_reason = None
            
            if 'call' in test:
                call_data = test['call']
                if 'longrepr' in call_data:
                    failure_reason = call_data['longrepr']
                
                # Try to extract input/output from test metadata
                if 'metadata' in call_data:
                    metadata = call_data['metadata']
                    input_data = metadata.get('input', '')
                    expected_output = metadata.get('expected_output', '')
                    actual_output = metadata.get('actual_output', '')
            
            test_result = TestResult(
                test_id=test_id,
                test_name=test_name,
                input=input_data,
                expected_output=expected_output,
                actual_output=actual_output,
                status=status,
                failure_reason=failure_reason,
                execution_time_ms=test.get('duration', 0) * 1000,  # Convert to milliseconds
                trace=test
            )
            results.append(test_result)
        
        return TestResultBatch(results=results)

    def _parse_junit_xml_file(self, file_path: Path) -> TestResultBatch:
        """Parse JUnit XML file."""
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        results = []
        
        for testcase in root.findall('.//testcase'):
            test_name = testcase.get('name', '')
            class_name = testcase.get('classname', '')
            test_id = f"{class_name}::{test_name}" if class_name else test_name
            
            # Check for failure or error
            failure = testcase.find('failure')
            error = testcase.find('error')
            
            if failure is not None:
                status = 'failed'
                failure_reason = failure.get('message', '')
                actual_output = failure.text or ''
            elif error is not None:
                status = 'error'
                failure_reason = error.get('message', '')
                actual_output = error.text or ''
            else:
                status = 'passed'
                failure_reason = None
                actual_output = ''
            
            test_result = TestResult(
                test_id=test_id,
                test_name=test_name,
                input='',  # JUnit XML doesn't typically contain input/output
                expected_output='',
                actual_output=actual_output,
                status=status,
                failure_reason=failure_reason,
                execution_time_ms=float(testcase.get('time', 0)) * 1000,  # Convert to milliseconds
            )
            results.append(test_result)
        
        return TestResultBatch(results=results)

    def validate_test_results(self, test_batch: TestResultBatch) -> List[str]:
        """
        Validate test results and return list of issues.

        Args:
            test_batch: Test results to validate

        Returns:
            List of validation issues (empty if all valid)
        """
        issues = []
        
        if not test_batch.results:
            issues.append("No test results provided")
            return issues
        
        # Check for required fields
        for i, test in enumerate(test_batch.results):
            if not test.test_id:
                issues.append(f"Test {i}: Missing test_id")
            
            if not test.input:
                issues.append(f"Test {i}: Missing input")
            
            if not test.actual_output:
                issues.append(f"Test {i}: Missing actual_output")
            
            if test.status not in ["passed", "failed", "error", "skipped"]:
                issues.append(f"Test {i}: Invalid status '{test.status}'")
        
        # Check for duplicate test IDs
        test_ids = [t.test_id for t in test_batch.results]
        if len(test_ids) != len(set(test_ids)):
            issues.append("Duplicate test IDs found")
        
        return issues

    def get_summary_stats(self, test_batch: TestResultBatch) -> Dict[str, Any]:
        """Get summary statistics for test results."""
        summary = test_batch.get_summary()
        
        # Add additional statistics
        if summary['total'] > 0:
            summary['pass_rate'] = summary['passed'] / summary['total']
            summary['failure_rate'] = summary['failed'] / summary['total']
            summary['error_rate'] = summary['error'] / summary['total']
        else:
            summary['pass_rate'] = 0.0
            summary['failure_rate'] = 0.0
            summary['error_rate'] = 0.0
        
        # Calculate average execution time
        times = [t.execution_time_ms for t in test_batch.results if t.execution_time_ms is not None]
        summary['avg_execution_time_ms'] = sum(times) / len(times) if times else 0
        
        return summary
