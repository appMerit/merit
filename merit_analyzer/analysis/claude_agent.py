"""AI analysis engine integration for Merit Analyzer.

Architecture:
- Standard Anthropic API: schema discovery, architecture inference, pattern mapping (fast, scalable)
- Claude Agent SDK: pattern analysis ONLY (reads actual code for deep root cause analysis)
"""

import json
import re
import os
import asyncio
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Any

# Suppress asyncio event loop warnings from Claude Agent SDK
warnings.filterwarnings('ignore', message='.*Loop.*is closed.*')
warnings.filterwarnings('ignore', category=ResourceWarning)

# Anthropic API for fast standard LLM calls
from anthropic import Anthropic  # type: ignore

# Claude Agent SDK - imported lazily to avoid hanging on module import
# We only need it for pattern analysis, so we'll import it when needed
ClaudeSDKClient = None
ClaudeAgentOptions = None
CLINotFoundError = None
ProcessError = None
AssistantMessage = None

from ..models.test_result import TestResult
from ..core.config import MeritConfig


def _lazy_import_claude_sdk():
    """Lazy import of Claude Agent SDK to avoid hanging on module import."""
    global ClaudeSDKClient, ClaudeAgentOptions, CLINotFoundError, ProcessError, AssistantMessage
    if ClaudeSDKClient is None:
        try:
            from claude_agent_sdk import (  # type: ignore
                ClaudeSDKClient as _ClaudeSDKClient,
                ClaudeAgentOptions as _ClaudeAgentOptions,
                CLINotFoundError as _CLINotFoundError,
                ProcessError as _ProcessError,
                AssistantMessage as _AssistantMessage,
            )
            ClaudeSDKClient = _ClaudeSDKClient
            ClaudeAgentOptions = _ClaudeAgentOptions
            CLINotFoundError = _CLINotFoundError
            ProcessError = _ProcessError
            AssistantMessage = _AssistantMessage
        except Exception as e:
            raise RuntimeError(f"Failed to import Claude Agent SDK: {e}")


def _run_async(coro):
    """
    Run an async coroutine safely, avoiding nested event loop issues.
    
    Creates a new event loop to avoid conflicts.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(asyncio.sleep(0))  # Let pending tasks finish
        loop.close()


class MeritClaudeAgent:
    """
    Merit's AI analysis engine.
    
    Uses standard Anthropic API for fast inference tasks (schema, architecture, mapping).
    Uses Claude Agent SDK ONLY for pattern analysis (reading actual code files).
    """

    def __init__(self, config: MeritConfig):
        """
        Initialize Merit AI analysis engine.

        Args:
            config: Merit Analyzer configuration
        """
        self.config = config
        self.project_path = Path(config.project_path)
        self.api_key = config.api_key
        self.model = config.model
        self.provider = config.provider
        
        # Initialize Anthropic client for standard LLM calls
        # Used for: schema discovery, architecture discovery, pattern mapping
        self.anthropic_client = Anthropic(api_key=self.api_key)
        
        # Configure environment for Claude Agent SDK (used later for pattern analysis)
        if self.provider == "bedrock":
            os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
            aws_region = getattr(config, 'aws_region', None) or os.environ.get("AWS_REGION") or "us-east-1"
            os.environ["AWS_REGION"] = aws_region
        else:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                os.environ["ANTHROPIC_API_KEY"] = self.api_key
        
        # DON'T create ClaudeAgentOptions here - it hangs!
        # We'll create it lazily when we actually need pattern analysis
        
        # Cache for responses
        self._response_cache: Dict[str, str] = {}

    def _call_anthropic_direct(self, prompt: str, max_tokens: int = 4096) -> tuple[str, Dict[str, int]]:
        """
        Fast standard Anthropic API call (no agent, no tools).
        
        Used for: schema discovery, architecture inference, pattern mapping.
        These tasks don't need code access - just intelligent analysis.
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            
        Returns:
            Tuple of (response_text, token_usage_dict)
        """
        try:
            message = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract text from response
            response_text = ""
            for block in message.content:
                if hasattr(block, 'text'):
                    response_text += block.text
            
            # Extract token usage
            token_usage = {
                'input_tokens': message.usage.input_tokens if hasattr(message, 'usage') else 0,
                'output_tokens': message.usage.output_tokens if hasattr(message, 'usage') else 0
            }
            
            return response_text, token_usage
        except Exception as e:
            return f"Error: {str(e)}", {'input_tokens': 0, 'output_tokens': 0}

    # =======================
    # ARCHITECTURE DISCOVERY (Standard API)
    # =======================
    
    def discover_system_architecture(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Discover system architecture using standard LLM inference.
        
        Analyzes project scan results (files, imports, frameworks) to infer
        the system architecture WITHOUT reading actual code files.

        Args:
            scan_results: Results from project scanning (file list, imports, entry points)

        Returns:
            Dict with agents, prompts, entry points, control flow
        """
        cache_key = f"architecture_{hash(str(scan_results))}"
        if cache_key in self._response_cache:
            return json.loads(self._response_cache[cache_key])
        
        # Build minimal prompt - summarize scan results instead of dumping everything
        files_summary = f"{len(scan_results.get('python_files', []))} Python files"
        frameworks = ', '.join(scan_results.get('frameworks', []))
        entry_points = ', '.join(scan_results.get('entry_points', []))
        
        prompt = f"""AI system architecture:
Files: {files_summary}
Frameworks: {frameworks}
Entry: {entry_points}

Return JSON with: system_type, agents[], prompts[], control_flow, config, dependencies
Keep it concise."""

        response, token_usage = self._call_anthropic_direct(prompt)
        architecture = self._parse_architecture_response(response)
        
        # Add token tracking
        architecture['_token_usage'] = token_usage
        
        # Cache the result
        self._response_cache[cache_key] = json.dumps(architecture)
        
        return architecture

    # =======================
    # PATTERN MAPPING (Standard API)
    # =======================
    
    def map_pattern_to_code(self, 
                           pattern_name: str,
                           test_examples: List[TestResult],
                           architecture: Dict[str, Any],
                           available_files: Optional[List[str]] = None) -> List[str]:
        """
        Map a failure pattern to relevant code locations using standard LLM inference.
        
        Intelligently selects which ACTUAL files from the codebase are relevant.

        Args:
            pattern_name: Name of the failure pattern
            test_examples: Example test cases
            architecture: System architecture information
            available_files: List of actual files in the project (from scan)

        Returns:
            List of file paths that likely relate to this pattern
        """
        cache_key = f"mapping_{pattern_name}_{len(test_examples)}"
        if cache_key in self._response_cache:
            return json.loads(self._response_cache[cache_key])
        
        # If no available files provided, return empty list (can't hallucinate files)
        if not available_files:
            return []
        
        # Build prompt for file mapping with ACTUAL file list
        examples = self._format_test_examples(test_examples[:2])
        files_list = "\n".join([f"  - {f}" for f in available_files[:50]])  # Limit to 50 files
        
        prompt = f"""Map this failure pattern to relevant code files from the ACTUAL project files.

PATTERN: {pattern_name}

FAILING TEST EXAMPLES:
{examples}

SYSTEM ARCHITECTURE:
{json.dumps(architecture, indent=2)}

ACTUAL PROJECT FILES (you MUST choose from this list):
{files_list}

Based on:
- The pattern name and failure characteristics
- The test inputs/outputs
- The known system architecture
- The ACTUAL files available in the project

Which 3-5 files from the ACTUAL PROJECT FILES list are most relevant to this failure?

Return ONLY the file paths from the list above, one per line.
Do NOT make up or hallucinate filenames.
Limit to 3-5 most relevant files."""

        response, token_usage = self._call_anthropic_direct(prompt, max_tokens=500)
        
        # Parse and validate file paths (must be in available_files)
        suggested_paths = self._parse_file_list_response(response)
        valid_paths = [p for p in suggested_paths if p in available_files]
        
        # If LLM didn't return valid paths, do simple keyword matching
        if not valid_paths:
            valid_paths = self._fallback_file_matching(pattern_name, test_examples, available_files)
        
        # Cache the result
        self._response_cache[cache_key] = json.dumps(valid_paths[:5])
        
        return valid_paths[:5]
    
    def _fallback_file_matching(self, pattern_name: str, test_examples: List[TestResult], available_files: List[str]) -> List[str]:
        """Fallback: Simple keyword matching between pattern and filenames."""
        # Extract keywords from pattern name
        keywords = pattern_name.lower().replace('_', ' ').split()
        
        # Score each file based on keyword matches
        scored_files = []
        for file_path in available_files:
            filename = file_path.lower()
            score = sum(1 for keyword in keywords if keyword in filename)
            if score > 0:
                scored_files.append((score, file_path))
        
        # Return top scored files
        scored_files.sort(reverse=True, key=lambda x: x[0])
        return [f for _, f in scored_files[:5]]

    # =======================
    # PATTERN ANALYSIS (Claude Agent SDK - Code Reading)
    # =======================
    
    def analyze_pattern(self, 
                       pattern_name: str,
                       failing_tests: List[TestResult],
                       passing_tests: List[TestResult],
                       source_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze a failure pattern using Agent SDK with directive prompt.
        
        Agent gets:
        - The problem (test failures + errors)
        - The map (file structure)
        - The tools (Read, Grep, Glob)
        
        Agent investigates and returns root cause + recommendations.

        Args:
            pattern_name: Name of the failure pattern
            failing_tests: Failed test cases
            passing_tests: Similar tests that are passing
            source_files: Available source files (as context)

        Returns:
            Dict with root_cause, recommendations, and token usage
        """
        cache_key = f"pattern_{pattern_name}_{len(failing_tests)}_{len(passing_tests)}"
        if cache_key in self._response_cache:
            return json.loads(self._response_cache[cache_key])
        
        # Use Agent SDK with directive prompt
        analysis = _run_async(self._analyze_pattern_with_agent(
            pattern_name, failing_tests, passing_tests, source_files or []
        ))
        
        # Cache the result
        self._response_cache[cache_key] = json.dumps(analysis)
        
        return analysis

    async def _analyze_pattern_with_agent(self,
                                          pattern_name: str,
                                          failing_tests: List[TestResult],
                                          passing_tests: List[TestResult],
                                          source_files: List[str]) -> Dict[str, Any]:
        """
        Analyze pattern using Agent SDK with directive prompt.
        
        Agent gets problem + file structure, uses Read/Grep/Glob to investigate.
        """
        try:
            # Lazy import Claude SDK
            _lazy_import_claude_sdk()
            
            # Ultra-minimal prompt - let Claude Agent SDK do the work
            # Show just 1 example error (not full test data)
            sample_error = failing_tests[0].failure_reason if failing_tests else "Unknown"
            if len(sample_error) > 200:
                sample_error = sample_error[:200] + "..."
            
            prompt = f"""Pattern: {pattern_name}
Failures: {len(failing_tests)} tests failing with error like: {sample_error}

Find root cause in code and return JSON with:
- root_cause (file:line)
- recommendations (type, title, description, priority, effort)

Use Grep/Read to investigate. Return ONLY valid JSON."""
            
            # Configure Agent SDK
            from claude_agent_sdk import query as claude_query, ClaudeAgentOptions
            
            options = ClaudeAgentOptions(
                cwd=str(self.project_path),
                allowed_tools=["Read", "Grep", "Glob"],  # Let agent investigate
                max_turns=6,  # Minimal turns to keep costs down (was 15!)
                model=self.model,
                stderr=lambda msg: None  # Suppress subprocess stderr noise (loop cleanup messages)
            )
            
            # Run analysis with query()
            full_response = ""
            total_input_tokens = 0
            total_output_tokens = 0
            total_cost_usd = 0.0
            
            async for message in claude_query(prompt=prompt, options=options):
                # Collect text responses
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            full_response += block.text
                
                # Accumulate tokens/cost from EVERY message (not just final)
                if hasattr(message, 'usage'):
                    usage = message.usage
                    if isinstance(usage, dict):
                        total_input_tokens += usage.get('input_tokens', 0)
                        total_output_tokens += usage.get('output_tokens', 0)
                
                # Check for cost on final message
                if hasattr(message, 'total_cost_usd'):
                    total_cost_usd = getattr(message, 'total_cost_usd', 0)
                
                # Break on final result
                if hasattr(message, 'subtype') and message.subtype in ['success', 'error']:
                    break
            
            # Build token usage dict
            token_usage = {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'total_cost_usd': total_cost_usd
            }
            
            # Parse analysis
            analysis = self._parse_pattern_analysis_response(full_response, pattern_name)
            
            # Add cost tracking
            analysis['_cost_info'] = token_usage
            
            return analysis
                
        except Exception as e:
            import traceback
            print(f"\n❌ Error in _analyze_pattern_with_agent for {pattern_name}:")
            print(f"   {str(e)}")
            traceback.print_exc()
            return {
                "root_cause": f"Error analyzing pattern: {str(e)}",
                "pattern_characteristics": {"common_inputs": [], "common_failures": []},
                "code_issues": [],
                "recommendations": [],
                "_cost_info": {"error": str(e)}
            }

    def _extract_error_keywords(self, tests: List[TestResult]) -> str:
        """Extract key error terms for targeted Grep searches."""
        keywords = set()
        for test in tests[:5]:  # Sample first 5 tests
            if test.failure_reason:
                # Extract meaningful words (not common words)
                words = test.failure_reason.lower().split()
                keywords.update(w for w in words if len(w) > 4 and w not in {
                    'should', 'expected', 'actual', 'value', 'error', 'failed'
                })
            if test.actual_output:
                output_str = str(test.actual_output)[:200]  # First 200 chars
                words = output_str.lower().split()
                keywords.update(w for w in words if len(w) > 5)
        
        # Return top 3 keywords
        return ", ".join(list(keywords)[:3]) if keywords else "error, failure, issue"
    
    # =======================
    # HELPER METHODS
    # =======================

    def _format_test_examples(self, tests: List[TestResult]) -> str:
        """Format test examples for prompts - MINIMAL to save tokens."""
        formatted = []
        for i, test in enumerate(tests, 1):
            # Only include test name and error - NOT full input/output
            test_name = getattr(test, 'test_name', f'test_{i}')
            error = test.failure_reason or 'Unknown failure'
            
            # Truncate error if too long
            if len(error) > 150:
                error = error[:150] + "..."
            
            formatted.append(f"  {i}. {test_name}: {error}")
        return "\n".join(formatted)

    def _parse_architecture_response(self, response: str) -> Dict[str, Any]:
        """Parse architecture analysis into structured format."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        # Fallback: return basic structure
        return {
            "system_type": "unknown",
            "agents": [],
            "prompts": [],
            "control_flow": {"entry_points": [], "flow": "", "decision_points": []},
            "configuration": {"api_keys": [], "models": [], "config_files": []},
            "dependencies": []
        }

    def _parse_pattern_analysis_response(self, response: str, pattern_name: str = "") -> Dict[str, Any]:
        """Parse pattern analysis into structured format with robust JSON extraction."""
        if not response or not response.strip():
            print(f"⚠️  Empty response for pattern: {pattern_name}")
            return {
                "root_cause": "Empty response from analysis",
                "pattern_characteristics": {"common_inputs": [], "common_failures": []},
                "code_issues": [],
                "recommendations": []
            }
        
        # Strategy 1: Try to extract JSON from markdown code block
        json_block_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_block_match:
            try:
                result = json.loads(json_block_match.group(1))
                if self._validate_analysis_structure(result):
                    return result
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON decode error in code block for {pattern_name}: {e}")
        
        # Strategy 2: Try to extract JSON without code block markers
        json_match = re.search(r'\{[^{]*"root_cause".*?\}', response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if self._validate_analysis_structure(result):
                    return result
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON decode error (strategy 2) for {pattern_name}: {e}")
        
        # Strategy 3: Find the largest JSON object in response
        json_objects = re.findall(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', response, re.DOTALL)
        for json_str in sorted(json_objects, key=len, reverse=True):
            try:
                result = json.loads(json_str)
                if self._validate_analysis_structure(result):
                    return result
            except json.JSONDecodeError:
                continue
        
        # Strategy 4: Try to extract information from text even if JSON parsing fails
        print(f"⚠️  All JSON parsing failed for {pattern_name}, attempting text extraction...")
        extracted = self._extract_from_text(response)
        if extracted.get("root_cause") and extracted["root_cause"] != "Unable to determine root cause":
            return extracted
        
        # Complete fallback
        print(f"❌ Failed to parse response for {pattern_name}")
        print(f"   Response length: {len(response)} chars")
        print(f"   First 200 chars: {response[:200]}")
        
        return {
            "root_cause": "Unable to determine root cause",
            "pattern_characteristics": {"common_inputs": [], "common_failures": []},
            "code_issues": [],
            "recommendations": []
        }
    
    def _validate_analysis_structure(self, data: Dict[str, Any]) -> bool:
        """Validate that the analysis dict has expected structure."""
        return (
            isinstance(data, dict) and
            "root_cause" in data and
            isinstance(data.get("root_cause"), str)
        )
    
    def _extract_from_text(self, response: str) -> Dict[str, Any]:
        """Extract analysis information from text when JSON parsing fails."""
        result = {
            "root_cause": "Unable to determine root cause",
            "pattern_characteristics": {"common_inputs": [], "common_failures": []},
            "code_issues": [],
            "recommendations": []
        }
        
        # Try to find root cause in text
        root_cause_patterns = [
            r'root[_\s]cause[:\s]+([^\n]+)',
            r'cause[:\s]+([^\n]+)',
            r'issue[:\s]+([^\n]+)',
            r'problem[:\s]+([^\n]+)',
        ]
        
        for pattern in root_cause_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                root_cause = match.group(1).strip()
                if len(root_cause) > 10:  # Meaningful root cause
                    result["root_cause"] = root_cause
                    break
        
        # Try to find recommendations in text
        rec_section = re.search(r'recommendation[s]?[:\s]+(.+?)(?:\n\n|\Z)', response, re.IGNORECASE | re.DOTALL)
        if rec_section:
            rec_text = rec_section.group(1)
            # Extract numbered or bulleted recommendations
            recs = re.findall(r'(?:^|\n)[\d\-\*]+[\.\):\s]+(.+?)(?=\n[\d\-\*]+|$)', rec_text, re.DOTALL)
            for i, rec in enumerate(recs[:3]):  # Max 3 recommendations
                result["recommendations"].append({
                    "type": "unknown",
                    "title": f"Recommendation {i+1}",
                    "description": rec.strip(),
                    "priority": "medium",
                    "effort": "medium"
                })
        
        return result

    def _parse_file_list_response(self, response: str) -> List[str]:
        """Parse file paths from response."""
        lines = response.strip().split('\n')
        file_paths = []
        
        for line in lines:
            line = line.strip()
            # Look for file paths
            if line and ('.py' in line or '.txt' in line or '.md' in line or '.yaml' in line or '.json' in line):
                # Clean up the path
                path = line.split()[0] if ' ' in line else line
                path = path.strip('"\'')
                file_paths.append(path)
        
        return file_paths[:8]  # Limit to 8 files

    def clear_cache(self):
        """Clear the response cache."""
        self._response_cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cached_responses": len(self._response_cache),
            "cache_size_mb": sum(len(v) for v in self._response_cache.values()) / (1024 * 1024)
        }
