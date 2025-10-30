"""Code mapping and pattern-to-code correlation."""

import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict, Counter

from ..models.test_result import TestResult
from ..models.pattern import Pattern


class CodeMapper:
    """Map failure patterns to relevant code locations."""

    def __init__(self, project_path: str):
        """
        Initialize code mapper.

        Args:
            project_path: Path to the project being analyzed
        """
        self.project_path = Path(project_path)
        self.file_contents: Dict[str, str] = {}
        self.function_mappings: Dict[str, List[str]] = {}
        self.class_mappings: Dict[str, List[str]] = {}
        self.import_mappings: Dict[str, List[str]] = {}

    def map_pattern_to_code(self, 
                           pattern_name: str,
                           pattern_tests: List[TestResult],
                           project_structure: Dict[str, Any],
                           frameworks: List[str]) -> List[str]:
        """
        Map a failure pattern to relevant code locations.

        Args:
            pattern_name: Name of the failure pattern
            pattern_tests: Test results that match this pattern
            project_structure: Project structure information
            frameworks: Detected frameworks

        Returns:
            List of file paths that likely relate to this pattern
        """
        print(f"  🗺️  Mapping pattern '{pattern_name}' to code...")
        
        # Extract keywords from pattern
        keywords = self._extract_pattern_keywords(pattern_tests)
        
        # Find files by content matching
        content_matches = self._find_files_by_content(keywords)
        
        # Find files by framework relevance
        framework_matches = self._find_files_by_framework(frameworks)
        
        # Find files by test input/output analysis
        test_matches = self._find_files_by_test_analysis(pattern_tests)
        
        # Combine and score matches
        all_matches = self._combine_matches(content_matches, framework_matches, test_matches)
        
        # Score and rank matches
        scored_matches = self._score_matches(all_matches, pattern_tests, keywords)
        
        # Return top matches
        top_matches = sorted(scored_matches.items(), key=lambda x: x[1], reverse=True)
        return [file_path for file_path, score in top_matches[:10] if score > 0.1]

    def _extract_pattern_keywords(self, pattern_tests: List[TestResult]) -> List[str]:
        """Extract keywords from pattern tests."""
        keywords = set()
        
        for test in pattern_tests:
            # Extract from input
            if test.input:
                words = re.findall(r'\b[a-z]{3,}\b', test.input.lower())
                keywords.update(words)
            
            # Extract from failure reason
            if test.failure_reason:
                words = re.findall(r'\b[a-z]{3,}\b', test.failure_reason.lower())
                keywords.update(words)
            
            # Extract from actual output
            if test.actual_output:
                words = re.findall(r'\b[a-z]{3,}\b', test.actual_output.lower())
                keywords.update(words)
        
        # Filter out common words
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her',
            'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its',
            'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'man',
            'men', 'put', 'say', 'she', 'too', 'use', 'test', 'tests', 'testing', 'result',
            'results', 'input', 'output', 'expected', 'actual', 'failure', 'failed',
            'error', 'exception', 'message', 'string', 'value', 'values', 'data'
        }
        
        return [word for word in keywords if word not in stop_words]

    def _find_files_by_content(self, keywords: List[str]) -> Dict[str, float]:
        """Find files that contain the keywords."""
        matches = defaultdict(float)
        
        # Get all Python files
        python_files = list(self.project_path.rglob("*.py"))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                
                score = 0.0
                for keyword in keywords:
                    # Count occurrences
                    count = content.count(keyword)
                    if count > 0:
                        # Weight by keyword frequency and file length
                        weight = count / len(content.split())
                        score += weight
                
                if score > 0:
                    matches[str(file_path)] = score
            except Exception:
                continue
        
        return dict(matches)

    def _find_files_by_framework(self, frameworks: List[str]) -> Dict[str, float]:
        """Find files that use the detected frameworks."""
        matches = defaultdict(float)
        
        if not frameworks:
            return {}
        
        # Framework-specific file patterns
        framework_patterns = {
            "langchain": ["agent", "chain", "tool", "prompt", "memory", "vector"],
            "llamaindex": ["index", "query", "retriever", "vector", "document"],
            "anthropic": ["claude", "anthropic", "message", "completion"],
            "openai": ["openai", "gpt", "chat", "completion", "embedding"],
            "fastapi": ["api", "endpoint", "route", "request", "response"],
            "flask": ["app", "route", "request", "response", "blueprint"],
            "streamlit": ["streamlit", "app", "widget", "component"],
            "gradio": ["gradio", "interface", "component", "demo"]
        }
        
        python_files = list(self.project_path.rglob("*.py"))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                
                score = 0.0
                for framework in frameworks:
                    if framework in framework_patterns:
                        patterns = framework_patterns[framework]
                        for pattern in patterns:
                            if pattern in content:
                                score += 0.1
                
                if score > 0:
                    matches[str(file_path)] = score
            except Exception:
                continue
        
        return dict(matches)

    def _find_files_by_test_analysis(self, pattern_tests: List[TestResult]) -> Dict[str, float]:
        """Find files based on test input/output analysis."""
        matches = defaultdict(float)
        
        # Extract common patterns from test inputs/outputs
        input_patterns = []
        output_patterns = []
        
        for test in pattern_tests:
            if test.input:
                # Look for function calls, class names, etc.
                patterns = re.findall(r'\b[A-Z][a-zA-Z]*\b|\b[a-z_][a-zA-Z0-9_]*\(', test.input)
                input_patterns.extend(patterns)
            
            if test.actual_output:
                # Look for error messages, class names, etc.
                patterns = re.findall(r'\b[A-Z][a-zA-Z]*\b|\b[a-z_][a-zA-Z0-9_]*\b', test.actual_output)
                output_patterns.extend(patterns)
        
        # Find files containing these patterns
        python_files = list(self.project_path.rglob("*.py"))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                score = 0.0
                
                # Check for input patterns
                for pattern in input_patterns:
                    if pattern in content:
                        score += 0.05
                
                # Check for output patterns
                for pattern in output_patterns:
                    if pattern in content:
                        score += 0.05
                
                if score > 0:
                    matches[str(file_path)] = score
            except Exception:
                continue
        
        return dict(matches)

    def _combine_matches(self, 
                        content_matches: Dict[str, float],
                        framework_matches: Dict[str, float],
                        test_matches: Dict[str, float]) -> Dict[str, float]:
        """Combine different types of matches."""
        all_matches = defaultdict(float)
        
        # Add content matches
        for file_path, score in content_matches.items():
            all_matches[file_path] += score * 0.4
        
        # Add framework matches
        for file_path, score in framework_matches.items():
            all_matches[file_path] += score * 0.3
        
        # Add test matches
        for file_path, score in test_matches.items():
            all_matches[file_path] += score * 0.3
        
        return dict(all_matches)

    def _score_matches(self, 
                      matches: Dict[str, float],
                      pattern_tests: List[TestResult],
                      keywords: List[str]) -> Dict[str, float]:
        """Score and rank file matches."""
        scored = {}
        
        for file_path, base_score in matches.items():
            score = base_score
            
            # Boost score for files with more keyword matches
            keyword_count = sum(1 for keyword in keywords if keyword in file_path.lower())
            score += keyword_count * 0.1
            
            # Boost score for files that are likely entry points
            if any(name in file_path.lower() for name in ['main', 'app', 'run', 'agent', 'server']):
                score += 0.2
            
            # Boost score for files with test-related patterns
            if any(pattern in file_path.lower() for pattern in ['test', 'spec', 'example']):
                score += 0.1
            
            scored[file_path] = score
        
        return scored

    def get_file_relevance_score(self, file_path: str, pattern_tests: List[TestResult]) -> float:
        """Get relevance score for a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().lower()
        except Exception:
            return 0.0
        
        score = 0.0
        
        # Check for test input patterns
        for test in pattern_tests:
            if test.input:
                input_words = re.findall(r'\b[a-z]{3,}\b', test.input.lower())
                for word in input_words:
                    if word in content:
                        score += 0.01
        
        # Check for failure reason patterns
        for test in pattern_tests:
            if test.failure_reason:
                reason_words = re.findall(r'\b[a-z]{3,}\b', test.failure_reason.lower())
                for word in reason_words:
                    if word in content:
                        score += 0.02
        
        # Check for function/class definitions that might be relevant
        for test in pattern_tests:
            if test.input:
                # Look for function calls
                func_calls = re.findall(r'\b[a-z_][a-zA-Z0-9_]*\(', test.input)
                for func_call in func_calls:
                    func_name = func_call[:-1]  # Remove parentheses
                    if f"def {func_name}" in content:
                        score += 0.1
        
        return min(score, 1.0)

    def find_related_functions(self, pattern_tests: List[TestResult]) -> List[Tuple[str, str, float]]:
        """Find functions that might be related to the pattern."""
        related_functions = []
        
        # Extract function calls from test inputs
        function_calls = set()
        for test in pattern_tests:
            if test.input:
                calls = re.findall(r'\b[a-z_][a-zA-Z0-9_]*\(', test.input)
                function_calls.update(calls)
        
        # Find function definitions
        python_files = list(self.project_path.rglob("*.py"))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find function definitions
                func_defs = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', content)
                
                for func_name in func_defs:
                    # Check if this function is called in tests
                    for func_call in function_calls:
                        if func_call.startswith(func_name + '('):
                            relevance = self.get_file_relevance_score(str(file_path), pattern_tests)
                            related_functions.append((str(file_path), func_name, relevance))
            except Exception:
                continue
        
        # Sort by relevance
        return sorted(related_functions, key=lambda x: x[2], reverse=True)

    def find_related_classes(self, pattern_tests: List[TestResult]) -> List[Tuple[str, str, float]]:
        """Find classes that might be related to the pattern."""
        related_classes = []
        
        # Extract class names from test inputs/outputs
        class_names = set()
        for test in pattern_tests:
            if test.input:
                names = re.findall(r'\b[A-Z][a-zA-Z0-9_]*\b', test.input)
                class_names.update(names)
            
            if test.actual_output:
                names = re.findall(r'\b[A-Z][a-zA-Z0-9_]*\b', test.actual_output)
                class_names.update(names)
        
        # Find class definitions
        python_files = list(self.project_path.rglob("*.py"))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find class definitions
                class_defs = re.findall(r'class\s+([A-Z][a-zA-Z0-9_]*)\s*[\(:]', content)
                
                for class_name in class_defs:
                    if class_name in class_names:
                        relevance = self.get_file_relevance_score(str(file_path), pattern_tests)
                        related_classes.append((str(file_path), class_name, relevance))
            except Exception:
                continue
        
        # Sort by relevance
        return sorted(related_classes, key=lambda x: x[2], reverse=True)

    def get_code_snippets(self, file_path: str, pattern_tests: List[TestResult], 
                         context_lines: int = 5) -> List[Dict[str, Any]]:
        """Get relevant code snippets from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return []
        
        snippets = []
        
        # Find lines that contain keywords from tests
        keywords = self._extract_pattern_keywords(pattern_tests)
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                # Get context around this line
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                
                snippet = {
                    "line_number": i + 1,
                    "content": line.strip(),
                    "context": [l.strip() for l in lines[start:end]],
                    "context_start": start + 1,
                    "context_end": end,
                    "matched_keywords": [kw for kw in keywords if kw in line_lower]
                }
                snippets.append(snippet)
        
        return snippets
