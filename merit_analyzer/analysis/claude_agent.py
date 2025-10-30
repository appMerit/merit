"""AI analysis engine integration for Merit Analyzer."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import anthropic  # type: ignore
import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

from ..models.test_result import TestResult
from ..core.config import MeritConfig


class MeritClaudeAgent:
    """Wrapper around Claude API for Merit Analyzer."""

    def __init__(self, config: MeritConfig):
        """
        Initialize Claude agent.

        Args:
            config: Merit Analyzer configuration
        """
        self.config = config
        self.project_path = Path(config.project_path)
        self.api_key = config.api_key
        self.provider = config.provider
        self.model = config.model
        
        # Initialize client based on provider
        if config.provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=config.api_key)
        elif config.provider == "bedrock":
            self.bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")
        
        # Cache for responses
        self._response_cache: Dict[str, str] = {}

    def discover_system_architecture(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ask Claude to discover and map system architecture.

        Args:
            scan_results: Results from project scanning

        Returns:
            Dict with agents, prompts, entry points, control flow
        """
        cache_key = f"architecture_{hash(str(scan_results))}"
        if cache_key in self._response_cache:
            return json.loads(self._response_cache[cache_key])
        
        prompt = self._build_architecture_prompt(scan_results)
        response = self._call_claude(prompt)
        
        architecture = self._parse_architecture_response(response)
        
        # Cache the result
        self._response_cache[cache_key] = json.dumps(architecture)
        
        return architecture

    def analyze_pattern(self, 
                       pattern_name: str,
                       failing_tests: List[TestResult],
                       passing_tests: List[TestResult],
                       code_locations: List[str]) -> Dict[str, Any]:
        """
        Analyze a specific failure pattern.

        Args:
            pattern_name: Name of the failure pattern
            failing_tests: Tests that are failing
            passing_tests: Similar tests that are passing
            code_locations: Relevant code file paths

        Returns:
            Dict with root cause and recommendations
        """
        cache_key = f"pattern_{pattern_name}_{len(failing_tests)}_{len(passing_tests)}"
        if cache_key in self._response_cache:
            return json.loads(self._response_cache[cache_key])
        
        prompt = self._build_pattern_analysis_prompt(
            pattern_name, failing_tests, passing_tests, code_locations
        )
        response = self._call_claude(prompt)
        
        analysis = self._parse_pattern_analysis_response(response)
        
        # Cache the result
        self._response_cache[cache_key] = json.dumps(analysis)
        
        return analysis

    def map_pattern_to_code(self, 
                           pattern_name: str,
                           test_examples: List[TestResult],
                           architecture: Dict[str, Any]) -> List[str]:
        """
        Map a failure pattern to relevant code locations.

        Args:
            pattern_name: Name of the failure pattern
            test_examples: Example test cases
            architecture: System architecture information

        Returns:
            List of file paths that likely relate to this pattern
        """
        cache_key = f"mapping_{pattern_name}_{len(test_examples)}"
        if cache_key in self._response_cache:
            return json.loads(self._response_cache[cache_key])
        
        prompt = self._build_code_mapping_prompt(pattern_name, test_examples, architecture)
        response = self._call_claude(prompt)
        
        file_paths = self._parse_file_list_response(response)
        
        # Cache the result
        self._response_cache[cache_key] = json.dumps(file_paths)
        
        return file_paths

    def generate_recommendations(self,
                               pattern_name: str,
                               root_cause: str,
                               code_context: Dict[str, str],
                               failing_tests: List[TestResult]) -> List[Dict[str, Any]]:
        """
        Generate specific recommendations for fixing a pattern.

        Args:
            pattern_name: Name of the failure pattern
            root_cause: Identified root cause
            code_context: Relevant code snippets
            failing_tests: Failing test cases

        Returns:
            List of recommendation dictionaries
        """
        prompt = self._build_recommendation_prompt(
            pattern_name, root_cause, code_context, failing_tests
        )
        response = self._call_claude(prompt)
        
        recommendations = self._parse_recommendations_response(response)
        
        return recommendations

    def _get_bedrock_model_id(self) -> str:
        """Map config model name to Bedrock model ID."""
        model_mapping = {
            "claude-sonnet-4-5": "anthropic.claude-3-5-sonnet-20241022-v1:0",
            "claude-3-5-sonnet-20241022": "anthropic.claude-3-5-sonnet-20241022-v1:0",
            "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v1:0",
            "claude-3-sonnet-20240229": "anthropic.claude-3-sonnet-20240229-v1:0",
            "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        # Default to 3.5 Sonnet if model not found
        return model_mapping.get(self.model, "anthropic.claude-3-5-sonnet-20241022-v1:0")

    def _call_claude(self, prompt: str) -> str:
        """Call Claude API with the given prompt."""
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            elif self.provider == "bedrock":
                # Bedrock implementation
                body = json.dumps({
                    "prompt": prompt,
                    "max_tokens_to_sample": self.config.max_tokens,
                    "temperature": self.config.temperature,
                })
                
                # Map config model to Bedrock model ID
                bedrock_model_id = self._get_bedrock_model_id()
                response = self.bedrock_client.invoke_model(
                    modelId=bedrock_model_id,
                    body=body
                )
                
                response_body = json.loads(response['body'].read())
                return response_body['completion']
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as e:
            print(f"Error calling Claude: {e}")
            return ""

    def _build_architecture_prompt(self, scan_results: Dict[str, Any]) -> str:
        """Build prompt for architecture discovery."""
        return f"""
I need you to analyze this AI system codebase and discover its architecture.

Project Information:
- Python files: {len(scan_results.get('python_files', []))}
- Entry points: {scan_results.get('entry_points', [])}
- Detected frameworks: {', '.join(scan_results.get('frameworks', {}).keys())}
- Estimated LOC: {scan_results.get('estimated_loc', 0)}

Please analyze the codebase and provide a structured summary of:

1. **Agents/Components**: Identify all AI agents, components, or main classes
   - Name and purpose of each component
   - File location
   - Key methods/functions

2. **Prompts/Templates**: Find all prompt templates or system messages
   - Location of prompt files
   - Purpose of each prompt
   - Which component uses each prompt

3. **Control Flow**: Map how requests flow through the system
   - Entry points and their responsibilities
   - Data flow between components
   - Key decision points

4. **Configuration**: Identify key configuration files and settings
   - API keys and endpoints
   - Model configurations
   - System parameters

5. **Dependencies**: Key external dependencies and integrations
   - API services used
   - Database connections
   - External libraries

Please provide your analysis in JSON format with the following structure:
{{
    "agents": [
        {{
            "name": "agent_name",
            "file": "path/to/file.py",
            "purpose": "description",
            "key_methods": ["method1", "method2"]
        }}
    ],
    "prompts": [
        {{
            "name": "prompt_name",
            "file": "path/to/prompt.txt",
            "purpose": "description",
            "used_by": "agent_name"
        }}
    ],
    "control_flow": {{
        "entry_points": ["main.py", "app.py"],
        "flow": "description of data flow",
        "decision_points": ["point1", "point2"]
    }},
    "configuration": {{
        "api_keys": ["key1", "key2"],
        "models": ["model1", "model2"],
        "settings": ["setting1", "setting2"]
    }},
    "dependencies": [
        {{
            "name": "dependency_name",
            "type": "api|database|library",
            "purpose": "description"
        }}
    ]
}}
"""

    def _build_pattern_analysis_prompt(self,
                                     pattern_name: str,
                                     failing_tests: List[TestResult],
                                     passing_tests: List[TestResult],
                                     code_locations: List[str]) -> str:
        """Build prompt for pattern analysis."""
        fail_examples = self._format_test_examples(failing_tests[:3])
        pass_examples = self._format_test_examples(passing_tests[:3]) if passing_tests else "None"
        
        return f"""
I need you to analyze a pattern of test failures in this AI system.

PATTERN: {pattern_name}
FAILURE COUNT: {len(failing_tests)}
PASSING SIMILAR TESTS: {len(passing_tests)}

FAILING TEST EXAMPLES:
{fail_examples}

PASSING TEST EXAMPLES:
{pass_examples}

RELEVANT CODE LOCATIONS:
{chr(10).join(f"- {loc}" for loc in code_locations)}

Please analyze this pattern and provide:

1. **Root Cause Analysis**: What is causing these failures?
   - Identify the specific issue
   - Explain why it's happening
   - Consider both code and prompt issues

2. **Pattern Characteristics**: What do these failures have in common?
   - Common input patterns
   - Common failure modes
   - Timing or context issues

3. **Code Review**: Review the relevant code files
   - Identify problematic code sections
   - Look for logic errors, edge cases, or missing validations
   - Check prompt quality and consistency

4. **Recommendations**: Provide 3-5 specific, actionable recommendations
   - What exactly needs to be changed
   - Where to make the changes (file and line numbers)
   - How to implement the fix
   - Expected impact on test results

Please provide your analysis in JSON format:
{{
    "root_cause": "detailed explanation of the root cause",
    "pattern_characteristics": {{
        "common_inputs": ["pattern1", "pattern2"],
        "common_failures": ["failure1", "failure2"],
        "timing_issues": "description if any"
    }},
    "code_issues": [
        {{
            "file": "path/to/file.py",
            "line": 123,
            "issue": "description of the issue",
            "severity": "high|medium|low"
        }}
    ],
    "recommendations": [
        {{
            "title": "Fix specific issue",
            "description": "What to change",
            "location": "file.py:line_number",
            "implementation": "Specific code changes",
            "expected_impact": "Which tests this will fix",
            "effort": "Time estimate",
            "priority": "high|medium|low"
        }}
    ]
}}
"""

    def _build_code_mapping_prompt(self,
                                 pattern_name: str,
                                 test_examples: List[TestResult],
                                 architecture: Dict[str, Any]) -> str:
        """Build prompt for code mapping."""
        examples = self._format_test_examples(test_examples[:2])
        
        return f"""
Given this failure pattern and system architecture, identify which code files are most likely involved.

PATTERN: {pattern_name}

EXAMPLES:
{examples}

SYSTEM ARCHITECTURE:
{json.dumps(architecture, indent=2)}

Please identify the 3-5 most relevant files to investigate for this pattern.

Consider:
- What part of the system handles these inputs?
- What prompts or agents are involved?
- Where might the failure be occurring?
- Which components are responsible for the expected behavior?

Return just the file paths, one per line, in order of relevance.
"""

    def _build_recommendation_prompt(self,
                                   pattern_name: str,
                                   root_cause: str,
                                   code_context: Dict[str, str],
                                   failing_tests: List[TestResult]) -> str:
        """Build prompt for generating recommendations."""
        test_examples = self._format_test_examples(failing_tests[:2])
        
        return f"""
Generate specific, actionable recommendations to fix this failure pattern.

PATTERN: {pattern_name}
ROOT CAUSE: {root_cause}

FAILING TESTS:
{test_examples}

CODE CONTEXT:
{json.dumps(code_context, indent=2)}

Please provide 3-5 specific recommendations that will fix this pattern. Each recommendation should include:

1. **Title**: Clear, concise title
2. **Description**: What needs to be changed
3. **Location**: Exact file and line numbers
4. **Implementation**: Specific code or prompt changes
5. **Expected Impact**: Which tests this will fix
6. **Effort Estimate**: Time to implement (e.g., "5 minutes", "2 hours")
7. **Priority**: High, Medium, or Low
8. **Type**: Code, Prompt, Architecture, or Configuration

Provide your response in JSON format:
{{
    "recommendations": [
        {{
            "title": "Fix validation logic",
            "description": "Add input validation for edge cases",
            "location": "src/validator.py:45",
            "implementation": "Add if statement to check for None values",
            "expected_impact": "Fixes 8 tests in validation_error pattern",
            "effort_estimate": "15 minutes",
            "priority": "high",
            "type": "code"
        }}
    ]
}}
"""

    def _format_test_examples(self, tests: List[TestResult]) -> str:
        """Format test examples for prompts."""
        formatted = []
        for i, test in enumerate(tests, 1):
            formatted.append(f"""
Example {i}:
  Input: {test.input}
  Expected: {test.expected_output or 'N/A'}
  Actual: {test.actual_output}
  Issue: {test.failure_reason or 'N/A'}
""")
        return "\n".join(formatted)

    def _parse_architecture_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's architecture analysis into structured format."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        # Fallback: return basic structure
        return {
            "agents": [],
            "prompts": [],
            "control_flow": {"entry_points": [], "flow": "", "decision_points": []},
            "configuration": {"api_keys": [], "models": [], "settings": []},
            "dependencies": []
        }

    def _parse_pattern_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's pattern analysis into structured format."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        # Fallback: return basic structure
        return {
            "root_cause": "Unable to determine root cause",
            "pattern_characteristics": {"common_inputs": [], "common_failures": [], "timing_issues": ""},
            "code_issues": [],
            "recommendations": []
        }

    def _parse_file_list_response(self, response: str) -> List[str]:
        """Parse file paths from Claude's response."""
        lines = response.strip().split('\n')
        file_paths = []
        
        for line in lines:
            line = line.strip()
            if line and (line.endswith('.py') or line.endswith('.txt') or line.endswith('.md')):
                # Convert to absolute path if relative
                if not Path(line).is_absolute():
                    file_path = self.project_path / line
                    if file_path.exists():
                        file_paths.append(str(file_path))
                else:
                    file_paths.append(line)
        
        return file_paths[:5]  # Limit to 5 files

    def _parse_recommendations_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse recommendations from Claude's response."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get('recommendations', [])
        except Exception:
            pass
        
        # Fallback: return empty list
        return []

    def clear_cache(self):
        """Clear the response cache."""
        self._response_cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cached_responses": len(self._response_cache),
            "cache_size_mb": sum(len(v) for v in self._response_cache.values()) / (1024 * 1024)
        }
