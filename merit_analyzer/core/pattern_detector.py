"""Pattern detection and clustering for test failures."""

import re
from collections import Counter
from typing import List, Dict, Any, Tuple
import numpy as np  # type: ignore
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
from sklearn.cluster import DBSCAN  # type: ignore
from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

from ..models.test_result import TestResult
from ..models.pattern import Pattern


class PatternDetector:
    """Automatically detect patterns in test failures using clustering."""

    def __init__(self, 
                 min_cluster_size: int = 2,
                 similarity_threshold: float = 0.2,  # Lower threshold for better clustering
                 max_patterns: int = 10,
                 claude_agent=None):
        """
        Initialize pattern detector.

        Args:
            min_cluster_size: Minimum number of tests in a cluster
            similarity_threshold: Threshold for clustering similarity
            max_patterns: Maximum number of patterns to return
            claude_agent: Optional Claude agent for AI-powered pattern naming
        """
        self.min_cluster_size = min_cluster_size
        self.similarity_threshold = similarity_threshold
        self.max_patterns = max_patterns
        self.claude_agent = claude_agent
        
        # Initialize vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.8
        )
        
        # Cache for patterns
        self._patterns_cache: Dict[str, List[Pattern]] = {}

    def detect_patterns(self, test_results: List[TestResult]) -> Dict[str, List[TestResult]]:
        """
        Cluster failures by similarity and return patterns.

        Args:
            test_results: List of test results to analyze

        Returns:
            Dict mapping pattern names to test results
        """
        failures = [t for t in test_results if t.status == "failed"]
        
        if len(failures) < self.min_cluster_size:
            return {"uncategorized": failures}
        
        # Extract features for clustering
        features = self._extract_features(failures)
        
        if features.shape[0] < self.min_cluster_size:
            return {"uncategorized": failures}
        
        # Perform clustering
        patterns = self._cluster_failures(failures, features)
        
        # Limit number of patterns
        if len(patterns) > self.max_patterns:
            # Sort by cluster size and take top patterns
            sorted_patterns = sorted(patterns.items(), key=lambda x: len(x[1]), reverse=True)
            patterns = dict(sorted_patterns[:self.max_patterns])
        
        return patterns

    def _extract_features(self, test_results: List[TestResult]) -> np.ndarray:
        """Extract features for clustering."""
        texts = []
        
        for test in test_results:
            # Combine input, failure reason, and actual output
            combined_text = self._combine_test_text(test)
            texts.append(combined_text)
        
        # Vectorize texts
        try:
            features = self.vectorizer.fit_transform(texts).toarray()
            return features
        except Exception:
            # Fallback to simple word count if TF-IDF fails
            return self._extract_simple_features(texts)

    def _combine_test_text(self, test: TestResult) -> str:
        """Combine relevant text from test result for clustering."""
        parts = []
        
        # Always include input and output (core test data)
        if test.input:
            parts.append(f"input: {test.input}")
        
        if test.actual_output:
            output = test.actual_output[:500]  # Truncate long outputs
            parts.append(f"output: {output}")
        
        # Add expected output if available (helps with comparison)
        if test.expected_output:
            expected = test.expected_output[:200]  # Truncate for clustering
            parts.append(f"expected: {expected}")
        
        # Add failure reason if available (most important for clustering)
        if test.failure_reason:
            parts.append(f"reason: {test.failure_reason}")
        else:
            # Generate basic failure context when reason is missing
            failure_context = self._generate_failure_context(test)
            parts.append(f"context: {failure_context}")
        
        # Add category and tags for additional context
        if test.category:
            parts.append(f"category: {test.category}")
        
        if test.tags:
            parts.append(f"tags: {' '.join(test.tags)}")
        
        # Add test name if available (often contains useful info)
        if test.test_name:
            parts.append(f"test_name: {test.test_name}")
        
        return " ".join(parts)

    def _generate_failure_context(self, test: TestResult) -> str:
        """Generate failure context when failure_reason is missing."""
        context_parts = []
        
        # Add status information
        context_parts.append(f"status: {test.status}")
        
        # Try to infer failure type from input/output comparison
        if test.expected_output and test.actual_output:
            # Simple heuristic: check if outputs are very different
            if len(test.actual_output) < len(test.expected_output) * 0.5:
                context_parts.append("output_too_short")
            elif len(test.actual_output) > len(test.expected_output) * 2:
                context_parts.append("output_too_long")
            elif test.expected_output.lower() not in test.actual_output.lower():
                context_parts.append("output_mismatch")
        
        # Check for common failure patterns in output
        output_lower = test.actual_output.lower()
        if any(word in output_lower for word in ['error', 'exception', 'failed', 'invalid']):
            context_parts.append("contains_error_keywords")
        if any(word in output_lower for word in ['sorry', 'cannot', 'unable', 'not found']):
            context_parts.append("contains_apology_keywords")
        if any(word in output_lower for word in ['hello', 'hi', 'greeting']):
            context_parts.append("contains_greeting")
        if any(word in output_lower for word in ['goodbye', 'bye', 'thanks', 'signature']):
            context_parts.append("contains_signoff")
        
        # Check input patterns
        input_lower = test.input.lower()
        if any(word in input_lower for word in ['price', 'cost', 'pricing']):
            context_parts.append("pricing_related")
        if any(word in input_lower for word in ['greeting', 'hello', 'hi']):
            context_parts.append("greeting_related")
        if any(word in input_lower for word in ['product', 'feature', 'service']):
            context_parts.append("product_related")
        
        return " ".join(context_parts) if context_parts else "unknown_failure"

    def _extract_simple_features(self, texts: List[str]) -> np.ndarray:
        """Extract simple word count features as fallback."""
        # Simple word frequency features
        all_words = []
        for text in texts:
            words = re.findall(r'\b[a-z]{3,}\b', text.lower())
            all_words.extend(words)
        
        # Get most common words
        word_counts = Counter(all_words)
        common_words = [word for word, count in word_counts.most_common(100)]
        
        # Create feature matrix
        features = np.zeros((len(texts), len(common_words)))
        for i, text in enumerate(texts):
            text_words = re.findall(r'\b[a-z]{3,}\b', text.lower())
            for j, word in enumerate(common_words):
                features[i, j] = text_words.count(word)
        
        return features

    def _cluster_failures(self, failures: List[TestResult], features: np.ndarray) -> Dict[str, List[TestResult]]:
        """Cluster failures using DBSCAN."""
        # Calculate optimal eps based on similarity threshold
        if features.shape[0] > 1:
            # Calculate pairwise similarities
            similarities = cosine_similarity(features)
            # Use 1 - similarity as distance
            distances = 1 - similarities
            # Set eps based on similarity threshold
            eps = 1 - self.similarity_threshold
        else:
            eps = 0.5
        
        # Perform DBSCAN clustering
        clustering = DBSCAN(
            eps=eps,
            min_samples=self.min_cluster_size,
            metric='cosine' if features.shape[0] > 1 else 'euclidean'
        )
        
        labels = clustering.fit_predict(features)
        
        # Group by cluster
        patterns = {}
        noise_points = []
        
        for idx, label in enumerate(labels):
            if label == -1:  # Noise points
                noise_points.append(failures[idx])
            else:
                pattern_name = self._generate_pattern_name(failures, label, labels)
                
                if pattern_name not in patterns:
                    patterns[pattern_name] = []
                patterns[pattern_name].append(failures[idx])
        
        # Try to group noise points into meaningful patterns
        if noise_points:
            # Use AI to analyze noise points and create better patterns
            noise_patterns = self._analyze_noise_points(noise_points)
            patterns.update(noise_patterns)
        
        return patterns

    def _analyze_noise_points(self, noise_points: List[TestResult]) -> Dict[str, List[TestResult]]:
        """Analyze noise points and try to group them into meaningful patterns."""
        if not noise_points:
            return {}
        
        # If we have a Claude agent, use it to analyze noise points
        if self.claude_agent and len(noise_points) > 1:
            try:
                # Group noise points by similarity using AI
                noise_summary = self._create_failure_summary(noise_points)
                
                prompt = f"""
Analyze these test failures that couldn't be automatically clustered and group them into meaningful patterns.

Failures:
{noise_summary}

Group these failures into 1-3 meaningful patterns based on their root causes. For each group, provide:
1. A descriptive pattern name (snake_case, 2-4 words)
2. The test IDs that belong to this pattern

Format your response as:
Pattern 1: pattern_name
Tests: test_id1, test_id2, test_id3

Pattern 2: pattern_name  
Tests: test_id4, test_id5

If all failures are truly unique and can't be grouped, respond with:
Pattern 1: unique_failures
Tests: all_test_ids
"""

                response = self.claude_agent._call_claude(prompt)
                if response and response.strip():
                    return self._parse_noise_patterns(response, noise_points)
            except Exception as e:
                print(f"Warning: AI noise analysis failed: {e}")
        
        # Fallback: create a single "miscellaneous" pattern
        return {"miscellaneous_failures": noise_points}

    def _parse_noise_patterns(self, response: str, noise_points: List[TestResult]) -> Dict[str, List[TestResult]]:
        """Parse AI response to group noise points into patterns."""
        patterns = {}
        
        # Create a mapping from test_id to TestResult
        test_map = {test.test_id: test for test in noise_points}
        
        # Parse the response
        lines = response.strip().split('\n')
        current_pattern = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('Pattern'):
                # Extract pattern name
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_pattern = parts[1].strip().lower()
                    patterns[current_pattern] = []
            elif line.startswith('Tests:') and current_pattern:
                # Extract test IDs
                test_ids = [tid.strip() for tid in line.split(':', 1)[1].split(',')]
                for test_id in test_ids:
                    if test_id in test_map:
                        patterns[current_pattern].append(test_map[test_id])
        
        # Remove empty patterns
        return {k: v for k, v in patterns.items() if v}

    def _generate_pattern_name(self, failures: List[TestResult], 
                              label: int, all_labels: np.ndarray) -> str:
        """Generate intelligent pattern name using AI analysis."""
        cluster_tests = [t for t, l in zip(failures, all_labels) if l == label]
        
        if not cluster_tests:
            return f"pattern_{label}"
        
        # Use AI to generate intelligent pattern name
        pattern_name = self._generate_ai_pattern_name(cluster_tests)
        if pattern_name:
            return pattern_name
        
        # Fallback to simple naming
        common_words = self._extract_common_words(cluster_tests)
        if common_words:
            pattern_name = "_".join(common_words[:3])
            pattern_name = re.sub(r'[^a-z0-9_]', '', pattern_name.lower())
            if not pattern_name:
                pattern_name = f"pattern_{label}"
        else:
            pattern_name = f"pattern_{label}"
        
        return pattern_name

    def _generate_ai_pattern_name(self, cluster_tests: List[TestResult]) -> str:
        """Generate intelligent pattern name using AI analysis of the failures."""
        if not cluster_tests:
            return ""
        
        # If we have a Claude agent, use it for intelligent naming
        if self.claude_agent:
            try:
                failure_summary = self._create_failure_summary(cluster_tests)
                
                prompt = f"""
Analyze these test failures and generate a concise, descriptive pattern name that captures the root cause.

Failures:
{failure_summary}

Generate a short, descriptive pattern name (2-4 words, snake_case) that describes what's going wrong.
Be specific and avoid generic names like "uncategorized" or "general_failure".

Examples: "missing_greeting", "validation_error", "timeout_issue", "data_format_problem", "incomplete_research", "poor_quality_output"

Pattern name:"""

                # Use Claude to generate the pattern name
                response = self.claude_agent._call_claude(prompt)
                if response and response.strip():
                    # Clean up the response
                    pattern_name = response.strip().lower()
                    # Remove any extra text and keep only the pattern name
                    pattern_name = re.sub(r'[^a-z0-9_]', '', pattern_name)
                    if pattern_name and len(pattern_name) > 2:
                        return pattern_name
            except Exception as e:
                print(f"Warning: AI pattern naming failed: {e}")
        
        # Fallback to heuristic analysis
        return self._analyze_failures_heuristic(cluster_tests)

    def _create_failure_summary(self, cluster_tests: List[TestResult]) -> str:
        """Create a summary of failures for AI analysis."""
        summary_parts = []
        
        # Sample a few representative failures
        sample_size = min(3, len(cluster_tests))
        for i, test in enumerate(cluster_tests[:sample_size]):
            summary_parts.append(f"Failure {i+1}:")
            summary_parts.append(f"  Input: {test.input[:200]}...")
            summary_parts.append(f"  Expected: {test.expected_output[:200]}...")
            summary_parts.append(f"  Actual: {test.actual_output[:200]}...")
            if test.failure_reason:
                summary_parts.append(f"  Reason: {test.failure_reason}")
            summary_parts.append("")
        
        return "\n".join(summary_parts)

    def _analyze_failures_heuristic(self, cluster_tests: List[TestResult]) -> str:
        """Heuristic analysis to generate pattern names (fallback when LLM not available)."""
        if not cluster_tests:
            return ""
        
        # Analyze failure reasons
        failure_reasons = [t.failure_reason for t in cluster_tests if t.failure_reason]
        inputs = [t.input for t in cluster_tests if t.input]
        outputs = [t.actual_output for t in cluster_tests if t.actual_output]
        
        # Check for common patterns
        all_text = " ".join(failure_reasons + inputs + outputs).lower()
        
        # Greeting/signature issues
        if any(word in all_text for word in ['greeting', 'hello', 'hi', 'goodbye', 'bye', 'sign', 'signature']):
            return "missing_greeting_signature"
        
        # Validation issues
        if any(word in all_text for word in ['validation', 'invalid', 'required', 'missing', 'format', 'type']):
            return "validation_error"
        
        # Timeout issues
        if any(word in all_text for word in ['timeout', 'timed out', 'slow', 'performance']):
            return "timeout_issue"
        
        # API issues
        if any(word in all_text for word in ['api', 'endpoint', 'request', 'response', 'http', 'status']):
            return "api_error"
        
        # Data format issues
        if any(word in all_text for word in ['json', 'xml', 'format', 'parse', 'decode', 'encode']):
            return "data_format_error"
        
        # Authentication issues
        if any(word in all_text for word in ['auth', 'login', 'token', 'credential', 'permission', 'access']):
            return "authentication_error"
        
        # Check for specific error patterns
        if any('not found' in reason.lower() for reason in failure_reasons if reason):
            return "resource_not_found"
        
        if any('permission' in reason.lower() for reason in failure_reasons if reason):
            return "permission_denied"
        
        if any('network' in reason.lower() for reason in failure_reasons if reason):
            return "network_error"
        
        # Default based on common words
        common_words = self._extract_common_words(cluster_tests)
        if common_words:
            return "_".join(common_words[:2])
        
        # Try to extract meaningful info from test names or categories
        test_names = [t.test_name for t in cluster_tests if t.test_name]
        if test_names:
            # Extract common words from test names
            name_words = []
            for name in test_names:
                words = re.findall(r'\b[a-z]{3,}\b', name.lower())
                name_words.extend(words)
            
            if name_words:
                word_counts = Counter(name_words)
                common_name_words = [word for word, count in word_counts.most_common(2)]
                if common_name_words:
                    return "_".join(common_name_words)
        
        return "test_failures"

    def _identify_failure_type(self, cluster_tests: List[TestResult]) -> str:
        """Identify specific failure types based on common patterns."""
        if not cluster_tests:
            return ""
        
        # Check for common failure patterns
        failure_reasons = [t.failure_reason for t in cluster_tests if t.failure_reason]
        inputs = [t.input for t in cluster_tests if t.input]
        
        # Check for validation errors
        validation_keywords = ['validation', 'invalid', 'required', 'missing', 'format', 'type']
        if any(any(keyword in (fr or "").lower() for keyword in validation_keywords) for fr in failure_reasons):
            return "validation_error"
        
        # Check for greeting/sign-off issues
        greeting_keywords = ['greeting', 'hello', 'hi', 'goodbye', 'bye', 'sign', 'signature']
        if any(any(keyword in (inp or "").lower() for keyword in greeting_keywords) for inp in inputs):
            return "greeting_signature_issue"
        
        # Check for timeout issues
        timeout_keywords = ['timeout', 'timed out', 'slow', 'performance']
        if any(any(keyword in (fr or "").lower() for keyword in timeout_keywords) for fr in failure_reasons):
            return "timeout_issue"
        
        # Check for API errors
        api_keywords = ['api', 'endpoint', 'request', 'response', 'http', 'status']
        if any(any(keyword in (fr or "").lower() for keyword in api_keywords) for fr in failure_reasons):
            return "api_error"
        
        # Check for data format issues
        format_keywords = ['json', 'xml', 'format', 'parse', 'decode', 'encode']
        if any(any(keyword in (fr or "").lower() for keyword in format_keywords) for fr in failure_reasons):
            return "data_format_error"
        
        # Check for authentication issues
        auth_keywords = ['auth', 'login', 'token', 'credential', 'permission', 'access']
        if any(any(keyword in (fr or "").lower() for keyword in auth_keywords) for fr in failure_reasons):
            return "authentication_error"
        
        return ""

    def _extract_common_words(self, tests: List[TestResult]) -> List[str]:
        """Find most common meaningful words in a cluster."""
        all_words = []
        
        for test in tests:
            text = self._combine_test_text(test)
            words = re.findall(r'\b[a-z]{4,}\b', text.lower())
            all_words.extend(words)
        
        # Filter stop words and common technical terms
        stop_words = {
            'this', 'that', 'with', 'from', 'have', 'been', 'what', 'when', 'where',
            'will', 'would', 'could', 'should', 'test', 'tests', 'testing', 'result',
            'results', 'input', 'output', 'expected', 'actual', 'failure', 'failed',
            'error', 'exception', 'message', 'string', 'value', 'values', 'data',
            'function', 'method', 'class', 'object', 'variable', 'parameter'
        }
        
        filtered_words = [w for w in all_words if w not in stop_words]
        
        # Get most common words
        word_counts = Counter(filtered_words)
        return [word for word, count in word_counts.most_common(5)]

    def analyze_pattern_similarity(self, pattern1: List[TestResult], 
                                  pattern2: List[TestResult]) -> float:
        """Calculate similarity between two patterns."""
        if not pattern1 or not pattern2:
            return 0.0
        
        # Extract features for both patterns
        features1 = self._extract_features(pattern1)
        features2 = self._extract_features(pattern2)
        
        if features1.shape[0] == 0 or features2.shape[0] == 0:
            return 0.0
        
        # Calculate average similarity
        similarities = []
        for f1 in features1:
            for f2 in features2:
                sim = cosine_similarity([f1], [f2])[0][0]
                similarities.append(sim)
        
        return np.mean(similarities) if similarities else 0.0

    def merge_similar_patterns(self, patterns: Dict[str, List[TestResult]], 
                              similarity_threshold: float = 0.7) -> Dict[str, List[TestResult]]:
        """Merge patterns that are too similar."""
        if len(patterns) <= 1:
            return patterns
        
        pattern_names = list(patterns.keys())
        merged = {}
        merged_indices = set()
        
        for i, name1 in enumerate(pattern_names):
            if i in merged_indices:
                continue
            
            current_pattern = patterns[name1]
            merged_name = name1
            
            for j, name2 in enumerate(pattern_names[i+1:], i+1):
                if j in merged_indices:
                    continue
                
                pattern2 = patterns[name2]
                similarity = self.analyze_pattern_similarity(current_pattern, pattern2)
                
                if similarity >= similarity_threshold:
                    # Merge patterns
                    current_pattern.extend(pattern2)
                    merged_name = f"{merged_name}_merged_{name2}"
                    merged_indices.add(j)
            
            merged[merged_name] = current_pattern
        
        return merged

    def get_pattern_insights(self, pattern_name: str, 
                           pattern_tests: List[TestResult]) -> Dict[str, Any]:
        """Get insights about a specific pattern."""
        if not pattern_tests:
            return {}
        
        insights = {
            "name": pattern_name,
            "test_count": len(pattern_tests),
            "common_failure_reasons": [],
            "common_input_patterns": [],
            "common_output_patterns": [],
            "categories": [],
            "tags": [],
            "avg_execution_time": 0.0,
        }
        
        # Analyze failure reasons
        failure_reasons = [t.failure_reason for t in pattern_tests if t.failure_reason]
        if failure_reasons:
            reason_counts = Counter(failure_reasons)
            insights["common_failure_reasons"] = [
                {"reason": reason, "count": count} 
                for reason, count in reason_counts.most_common(5)
            ]
        
        # Analyze input patterns
        inputs = [t.input for t in pattern_tests if t.input]
        if inputs:
            input_words = []
            for inp in inputs:
                words = re.findall(r'\b[a-z]{3,}\b', inp.lower())
                input_words.extend(words)
            
            word_counts = Counter(input_words)
            insights["common_input_patterns"] = [
                {"word": word, "count": count}
                for word, count in word_counts.most_common(10)
            ]
        
        # Analyze output patterns
        outputs = [t.actual_output for t in pattern_tests if t.actual_output]
        if outputs:
            output_words = []
            for out in outputs:
                words = re.findall(r'\b[a-z]{3,}\b', out.lower())
                output_words.extend(words)
            
            word_counts = Counter(output_words)
            insights["common_output_patterns"] = [
                {"word": word, "count": count}
                for word, count in word_counts.most_common(10)
            ]
        
        # Analyze categories and tags
        categories = [t.category for t in pattern_tests if t.category]
        if categories:
            category_counts = Counter(categories)
            insights["categories"] = [
                {"category": cat, "count": count}
                for cat, count in category_counts.most_common()
            ]
        
        all_tags = []
        for t in pattern_tests:
            if t.tags:
                all_tags.extend(t.tags)
        if all_tags:
            tag_counts = Counter(all_tags)
            insights["tags"] = [
                {"tag": tag, "count": count}
                for tag, count in tag_counts.most_common()
            ]
        
        # Calculate average execution time
        times = [t.execution_time_ms for t in pattern_tests if t.execution_time_ms is not None]
        if times:
            insights["avg_execution_time"] = sum(times) / len(times)
        
        return insights
