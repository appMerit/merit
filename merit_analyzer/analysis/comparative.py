"""Comparative analysis between passing and failing tests."""

import re
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
import difflib

from ..models.test_result import TestResult


class ComparativeAnalyzer:
    """Compare passing and failing tests to identify differences."""

    def __init__(self):
        """Initialize comparative analyzer."""
        self.similarity_threshold = 0.7

    def compare_tests(self, 
                     failing_tests: List[TestResult],
                     passing_tests: List[TestResult]) -> Dict[str, Any]:
        """
        Compare failing and passing tests to identify differences.

        Args:
            failing_tests: List of failing test results
            passing_tests: List of passing test results

        Returns:
            Dictionary with comparative analysis
        """
        print(f"  🔍 Comparing {len(failing_tests)} failing vs {len(passing_tests)} passing tests...")
        
        if not failing_tests:
            return {"error": "No failing tests to analyze"}
        
        if not passing_tests:
            return {"error": "No passing tests for comparison"}
        
        # Find similar test pairs
        similar_pairs = self._find_similar_pairs(failing_tests, passing_tests)
        
        # Analyze differences
        differences = self._analyze_differences(similar_pairs)
        
        # Analyze input patterns
        input_analysis = self._analyze_input_patterns(failing_tests, passing_tests)
        
        # Analyze output patterns
        output_analysis = self._analyze_output_patterns(failing_tests, passing_tests)
        
        # Analyze timing differences
        timing_analysis = self._analyze_timing_differences(failing_tests, passing_tests)
        
        return {
            "similar_pairs": similar_pairs,
            "differences": differences,
            "input_analysis": input_analysis,
            "output_analysis": output_analysis,
            "timing_analysis": timing_analysis,
            "insights": self._generate_insights(differences, input_analysis, output_analysis),
        }

    def _find_similar_pairs(self, 
                           failing_tests: List[TestResult],
                           passing_tests: List[TestResult]) -> List[Dict[str, Any]]:
        """Find similar pairs of failing and passing tests."""
        pairs = []
        
        for failing_test in failing_tests:
            best_match = None
            best_similarity = 0
            
            for passing_test in passing_tests:
                similarity = self._calculate_similarity(failing_test, passing_test)
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = passing_test
            
            if best_match:
                pairs.append({
                    "failing_test": failing_test,
                    "passing_test": best_match,
                    "similarity": best_similarity,
                    "differences": self._find_test_differences(failing_test, best_match)
                })
        
        return pairs

    def _calculate_similarity(self, test1: TestResult, test2: TestResult) -> float:
        """Calculate similarity between two tests."""
        # Compare inputs
        input_similarity = self._text_similarity(test1.input, test2.input)
        
        # Compare categories
        category_similarity = 1.0 if test1.category == test2.category else 0.0
        
        # Compare tags
        tags1 = set(test1.tags or [])
        tags2 = set(test2.tags or [])
        if tags1 or tags2:
            tag_similarity = len(tags1 & tags2) / len(tags1 | tags2)
        else:
            tag_similarity = 1.0
        
        # Weighted average
        return (input_similarity * 0.7 + category_similarity * 0.2 + tag_similarity * 0.1)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using difflib."""
        if not text1 or not text2:
            return 0.0
        
        return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _find_test_differences(self, failing_test: TestResult, passing_test: TestResult) -> Dict[str, Any]:
        """Find specific differences between two tests."""
        differences = {
            "input_differences": [],
            "output_differences": [],
            "execution_differences": [],
        }
        
        # Input differences
        if failing_test.input != passing_test.input:
            input_diff = self._generate_text_diff(failing_test.input, passing_test.input)
            differences["input_differences"] = input_diff
        
        # Output differences
        if failing_test.actual_output != passing_test.actual_output:
            output_diff = self._generate_text_diff(failing_test.actual_output, passing_test.actual_output)
            differences["output_differences"] = output_diff
        
        # Execution differences
        if failing_test.execution_time_ms != passing_test.execution_time_ms:
            differences["execution_differences"].append({
                "type": "execution_time",
                "failing": failing_test.execution_time_ms,
                "passing": passing_test.execution_time_ms,
                "difference": (failing_test.execution_time_ms or 0) - (passing_test.execution_time_ms or 0)
            })
        
        return differences

    def _generate_text_diff(self, text1: str, text2: str) -> List[Dict[str, str]]:
        """Generate a diff between two texts."""
        diff = difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile="failing",
            tofile="passing",
            lineterm=""
        )
        
        diff_lines = []
        for line in diff:
            if line.startswith('---') or line.startswith('+++'):
                continue
            elif line.startswith('@@'):
                diff_lines.append({"type": "header", "content": line})
            elif line.startswith('-'):
                diff_lines.append({"type": "removed", "content": line[1:]})
            elif line.startswith('+'):
                diff_lines.append({"type": "added", "content": line[1:]})
            else:
                diff_lines.append({"type": "context", "content": line})
        
        return diff_lines

    def _analyze_differences(self, similar_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in differences between similar pairs."""
        if not similar_pairs:
            return {"error": "No similar pairs found"}
        
        analysis = {
            "common_input_patterns": [],
            "common_output_patterns": [],
            "common_execution_patterns": [],
            "difference_frequency": {},
        }
        
        # Analyze input differences
        input_diffs = [pair["differences"]["input_differences"] for pair in similar_pairs if pair["differences"]["input_differences"]]
        if input_diffs:
            analysis["common_input_patterns"] = self._find_common_patterns(input_diffs)
        
        # Analyze output differences
        output_diffs = [pair["differences"]["output_differences"] for pair in similar_pairs if pair["differences"]["output_differences"]]
        if output_diffs:
            analysis["common_output_patterns"] = self._find_common_patterns(output_diffs)
        
        # Analyze execution differences
        exec_diffs = [pair["differences"]["execution_differences"] for pair in similar_pairs if pair["differences"]["execution_differences"]]
        if exec_diffs:
            analysis["common_execution_patterns"] = self._analyze_execution_patterns(exec_diffs)
        
        # Calculate difference frequency
        analysis["difference_frequency"] = self._calculate_difference_frequency(similar_pairs)
        
        return analysis

    def _find_common_patterns(self, diffs: List[List[Dict[str, str]]]) -> List[Dict[str, Any]]:
        """Find common patterns in text differences."""
        patterns = []
        
        # Extract common words from added/removed lines
        added_words = []
        removed_words = []
        
        for diff in diffs:
            for line in diff:
                if line["type"] == "added":
                    words = re.findall(r'\b[a-z]{3,}\b', line["content"].lower())
                    added_words.extend(words)
                elif line["type"] == "removed":
                    words = re.findall(r'\b[a-z]{3,}\b', line["content"].lower())
                    removed_words.extend(words)
        
        if added_words:
            added_counts = Counter(added_words)
            patterns.append({
                "type": "commonly_added",
                "words": [{"word": word, "count": count} for word, count in added_counts.most_common(5)]
            })
        
        if removed_words:
            removed_counts = Counter(removed_words)
            patterns.append({
                "type": "commonly_removed",
                "words": [{"word": word, "count": count} for word, count in removed_counts.most_common(5)]
            })
        
        return patterns

    def _analyze_execution_patterns(self, exec_diffs: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Analyze execution time patterns."""
        patterns = []
        
        time_diffs = []
        for diff_list in exec_diffs:
            for diff in diff_list:
                if diff["type"] == "execution_time":
                    time_diffs.append(diff["difference"])
        
        if time_diffs:
            patterns.append({
                "type": "execution_time_differences",
                "avg_difference": sum(time_diffs) / len(time_diffs),
                "min_difference": min(time_diffs),
                "max_difference": max(time_diffs),
                "failing_slower": sum(1 for diff in time_diffs if diff > 0),
                "failing_faster": sum(1 for diff in time_diffs if diff < 0),
            })
        
        return patterns

    def _calculate_difference_frequency(self, similar_pairs: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate frequency of different types of differences."""
        total_pairs = len(similar_pairs)
        if total_pairs == 0:
            return {}
        
        frequencies = {}
        
        # Input differences
        input_diff_count = sum(1 for pair in similar_pairs if pair["differences"]["input_differences"])
        frequencies["input_differences"] = input_diff_count / total_pairs
        
        # Output differences
        output_diff_count = sum(1 for pair in similar_pairs if pair["differences"]["output_differences"])
        frequencies["output_differences"] = output_diff_count / total_pairs
        
        # Execution differences
        exec_diff_count = sum(1 for pair in similar_pairs if pair["differences"]["execution_differences"])
        frequencies["execution_differences"] = exec_diff_count / total_pairs
        
        return frequencies

    def _analyze_input_patterns(self, 
                              failing_tests: List[TestResult],
                              passing_tests: List[TestResult]) -> Dict[str, Any]:
        """Analyze input patterns between failing and passing tests."""
        failing_inputs = [t.input for t in failing_tests if t.input]
        passing_inputs = [t.input for t in passing_tests if t.input]
        
        analysis = {
            "length_comparison": {},
            "word_patterns": {},
            "special_characters": {},
            "common_phrases": {},
        }
        
        if failing_inputs and passing_inputs:
            # Length comparison
            failing_lengths = [len(inp) for inp in failing_inputs]
            passing_lengths = [len(inp) for inp in passing_inputs]
            
            analysis["length_comparison"] = {
                "failing_avg": sum(failing_lengths) / len(failing_lengths),
                "passing_avg": sum(passing_lengths) / len(passing_lengths),
                "failing_min": min(failing_lengths),
                "passing_min": min(passing_lengths),
                "failing_max": max(failing_lengths),
                "passing_max": max(passing_lengths),
            }
            
            # Word patterns
            failing_words = []
            passing_words = []
            
            for inp in failing_inputs:
                words = re.findall(r'\b[a-z]{3,}\b', inp.lower())
                failing_words.extend(words)
            
            for inp in passing_inputs:
                words = re.findall(r'\b[a-z]{3,}\b', inp.lower())
                passing_words.extend(words)
            
            failing_word_counts = Counter(failing_words)
            passing_word_counts = Counter(passing_words)
            
            analysis["word_patterns"] = {
                "failing_common": [{"word": word, "count": count} for word, count in failing_word_counts.most_common(10)],
                "passing_common": [{"word": word, "count": count} for word, count in passing_word_counts.most_common(10)],
            }
        
        return analysis

    def _analyze_output_patterns(self, 
                               failing_tests: List[TestResult],
                               passing_tests: List[TestResult]) -> Dict[str, Any]:
        """Analyze output patterns between failing and passing tests."""
        failing_outputs = [t.actual_output for t in failing_tests if t.actual_output]
        passing_outputs = [t.actual_output for t in passing_tests if t.actual_output]
        
        analysis = {
            "error_patterns": {},
            "length_comparison": {},
            "response_types": {},
        }
        
        if failing_outputs and passing_outputs:
            # Error patterns
            error_keywords = ['error', 'exception', 'failed', 'invalid', 'timeout', 'unauthorized']
            
            failing_errors = defaultdict(int)
            passing_errors = defaultdict(int)
            
            for output in failing_outputs:
                for keyword in error_keywords:
                    if keyword in output.lower():
                        failing_errors[keyword] += 1
            
            for output in passing_outputs:
                for keyword in error_keywords:
                    if keyword in output.lower():
                        passing_errors[keyword] += 1
            
            analysis["error_patterns"] = {
                "failing_errors": dict(failing_errors),
                "passing_errors": dict(passing_errors),
            }
            
            # Length comparison
            failing_lengths = [len(output) for output in failing_outputs]
            passing_lengths = [len(output) for output in passing_outputs]
            
            analysis["length_comparison"] = {
                "failing_avg": sum(failing_lengths) / len(failing_lengths),
                "passing_avg": sum(passing_lengths) / len(passing_lengths),
            }
        
        return analysis

    def _analyze_timing_differences(self, 
                                  failing_tests: List[TestResult],
                                  passing_tests: List[TestResult]) -> Dict[str, Any]:
        """Analyze timing differences between failing and passing tests."""
        failing_times = [t.execution_time_ms for t in failing_tests if t.execution_time_ms is not None]
        passing_times = [t.execution_time_ms for t in passing_tests if t.execution_time_ms is not None]
        
        if not failing_times or not passing_times:
            return {"error": "Insufficient timing data"}
        
        analysis = {
            "failing_stats": {
                "avg": sum(failing_times) / len(failing_times),
                "min": min(failing_times),
                "max": max(failing_times),
                "median": sorted(failing_times)[len(failing_times) // 2],
            },
            "passing_stats": {
                "avg": sum(passing_times) / len(passing_times),
                "min": min(passing_times),
                "max": max(passing_times),
                "median": sorted(passing_times)[len(passing_times) // 2],
            },
            "comparison": {
                "avg_difference": (sum(failing_times) / len(failing_times)) - (sum(passing_times) / len(passing_times)),
                "failing_slower": sum(1 for t in failing_times if t > (sum(passing_times) / len(passing_times))),
                "timeout_threshold": 10000,  # 10 seconds
                "failing_timeouts": sum(1 for t in failing_times if t > 10000),
                "passing_timeouts": sum(1 for t in passing_times if t > 10000),
            }
        }
        
        return analysis

    def _generate_insights(self, 
                          differences: Dict[str, Any],
                          input_analysis: Dict[str, Any],
                          output_analysis: Dict[str, Any]) -> List[str]:
        """Generate insights from comparative analysis."""
        insights = []
        
        # Input insights
        if input_analysis.get("length_comparison"):
            failing_avg = input_analysis["length_comparison"]["failing_avg"]
            passing_avg = input_analysis["length_comparison"]["passing_avg"]
            
            if failing_avg > passing_avg * 1.5:
                insights.append("Failing tests tend to have longer inputs - may indicate input length limits")
            elif failing_avg < passing_avg * 0.5:
                insights.append("Failing tests tend to have shorter inputs - may indicate missing input validation")
        
        # Output insights
        if output_analysis.get("error_patterns"):
            failing_errors = output_analysis["error_patterns"]["failing_errors"]
            if failing_errors:
                most_common_error = max(failing_errors.items(), key=lambda x: x[1])
                insights.append(f"Most common error in failing tests: '{most_common_error[0]}' ({most_common_error[1]} occurrences)")
        
        # Timing insights
        if differences.get("common_execution_patterns"):
            for pattern in differences["common_execution_patterns"]:
                if pattern["type"] == "execution_time_differences":
                    if pattern["failing_slower"] > pattern["failing_faster"]:
                        insights.append("Failing tests tend to be slower - may indicate performance issues or timeouts")
        
        # Difference frequency insights
        if differences.get("difference_frequency"):
            freq = differences["difference_frequency"]
            if freq.get("input_differences", 0) > 0.8:
                insights.append("High frequency of input differences suggests input processing issues")
            if freq.get("output_differences", 0) > 0.8:
                insights.append("High frequency of output differences suggests output generation issues")
        
        return insights
