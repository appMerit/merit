"""Code analysis engine using Claude Agent SDK for root cause analysis."""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

from ..types import AssertionStateGroup


@dataclass
class AnalysisResult:
    """Result of analyzing an error group."""
    group_name: str
    group_description: str
    root_cause: str
    problematic_code: str
    recommendations: List[Dict[str, Any]]
    relevant_tests: List[str]


class CodeAnalyzer:
    """
    Stateful engine for analyzing error groups using Claude Agent SDK.
    
    Takes clustered test failures and uses Claude to:
    1. Find the problematic code
    2. Determine root cause
    3. Generate fix recommendations
    """

    def __init__(self, project_path: str, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize the code analyzer.

        Args:
            project_path: Path to the project to analyze
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.project_path = Path(project_path)
        self.api_key = api_key
        self.model = model
        
        # Lazy import Claude SDK components
        self._ClaudeSDKClient = None
        self._ClaudeAgentOptions = None
        self._tool = None
        self._create_sdk_mcp_server = None

    def _lazy_import_sdk(self):
        """Lazy import Claude Agent SDK to avoid hanging on module import."""
        if self._ClaudeSDKClient is None:
            from claude_agent_sdk import (  # type: ignore
                ClaudeSDKClient,
                ClaudeAgentOptions,
                tool,
                create_sdk_mcp_server
            )
            self._ClaudeSDKClient = ClaudeSDKClient
            self._ClaudeAgentOptions = ClaudeAgentOptions
            self._tool = tool
            self._create_sdk_mcp_server = create_sdk_mcp_server

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response to extract JSON."""
        # Try to extract JSON from the response
        try:
            # Look for JSON object
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                return json.loads(json_str)
        except Exception:
            pass
        
        # Fallback if parsing fails
        return {
            'root_cause': 'Unable to determine root cause',
            'problematic_code': response_text[:500],
            'recommendations': []
        }

    async def analyze_multiple_groups(self, groups: List[AssertionStateGroup]) -> List[AnalysisResult]:
        """
        Analyze multiple error groups using ClaudeSDKClient with custom tools.
        
        Uses ClaudeSDKClient (not query()) to support custom tools via MCP server.

        Args:
            groups: List of error groups from clustering

        Returns:
            List of analysis results
        """
        self._lazy_import_sdk()
        
        # Define custom tool ONCE using @tool decorator (outside loop)
        # Use FULL JSON Schema for better Claude understanding
        @self._tool(
            "submit_analysis",
            "REQUIRED: You MUST call this tool when you have completed your investigation and are ready to submit your final analysis of the test failure. This is the ONLY way to complete the task.",
            {
                "type": "object",
                "properties": {
                    "root_cause": {
                        "type": "string",
                        "description": "The root cause with file:line reference (e.g., 'calculator.py:35 - Missing zero check causes ZeroDivisionError')"
                    },
                    "problematic_code": {
                        "type": "string",
                        "description": "The exact code snippet that is causing the problem"
                    },
                    "recommendations": {
                        "type": "array",
                        "description": "List of 1-3 actionable recommendations with actual code fixes",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["code", "prompt", "config", "design"],
                                    "description": "Type of fix"
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Short action-oriented title (e.g., 'Add zero division check')"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Complete explanation of the fix and why it's needed"
                                },
                                "file": {
                                    "type": "string",
                                    "description": "File path where the fix should be applied"
                                },
                                "line_number": {
                                    "type": "string",
                                    "description": "Line number(s) to modify (e.g., '6' or '6-8')"
                                },
                                "current_code": {
                                    "type": "string",
                                    "description": "The current buggy code snippet"
                                },
                                "fixed_code": {
                                    "type": "string",
                                    "description": "The corrected code that fixes the issue"
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                    "description": "Priority level"
                                },
                                "effort": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                    "description": "Implementation effort"
                                }
                            },
                            "required": ["type", "title", "description", "file", "line_number", "current_code", "fixed_code", "priority", "effort"]
                        }
                    }
                },
                "required": ["root_cause", "problematic_code", "recommendations"]
            }
        )
        async def submit_analysis_handler(args):
            """Handler for submit_analysis tool - returns confirmation."""
            return {
                "content": [{
                    "type": "text",
                    "text": f"✅ Analysis submitted successfully: {args.get('root_cause', 'N/A')}"
                }]
            }
        
        # Create SDK MCP server with the custom tool (once)
        analyzer_server = self._create_sdk_mcp_server(
            name="analyzer",
            version="1.0.0",
            tools=[submit_analysis_handler]
        )
        
        
        results = []
        total_input_tokens = 0
        total_output_tokens = 0
        
        # Define hook to remind Claude before stopping
        async def ensure_tool_call_hook(input_data, tool_use_id, context):
            """Remind Claude to call submit_analysis before completing."""
            return {
                'systemMessage': 'REMINDER: You must call mcp__analyzer__submit_analysis to submit your findings before ending.'
            }
        
        # Configure options with MCP server (ONCE for all clusters)
        options = self._ClaudeAgentOptions(
            cwd=str(self.project_path),
            mcp_servers={"analyzer": analyzer_server},
            allowed_tools=["Read", "Grep", "Glob", "mcp__analyzer__submit_analysis"],
            max_turns=8,
            model=self.model,
            stderr=lambda msg: None,  # Suppress errors
            hooks={
                'Stop': [{'hooks': [ensure_tool_call_hook]}]
            },
            system_prompt="""You are a code debugger. Your task is to:
1. Use Grep to search for relevant code
2. Use Read to examine the problematic files
3. Identify the root cause with file:line reference
4. Create fix recommendations with ACTUAL CODE CHANGES (before/after)
5. MANDATORY: Call mcp__analyzer__submit_analysis with your findings

For each recommendation, you MUST provide:
- The specific file and line number to change
- The current buggy code snippet
- The fixed code that resolves the issue

YOU MUST call mcp__analyzer__submit_analysis before the conversation ends. This is REQUIRED to complete the task."""
        )
        
        # Create ONE ClaudeSDKClient for all clusters to maintain context
        async with self._ClaudeSDKClient(options=options) as client:
            # Analyze each group with shared context
            for group in groups:
                try:
                    # Build minimal prompt
                    prompt = self._build_minimal_prompt(group)
                    
                    print(f"\n🔍 Analyzing group: {group.metadata.name}")
                    
                    # Use the same client - maintains context!
                    response_text = ""
                    tool_result = None
                    tool_was_called = False
                    await client.query(prompt)
                    
                    async for message in client.receive_response():
                        # Get usage from ResultMessage (only message with usage info)
                        if type(message).__name__ == 'ResultMessage' and hasattr(message, 'usage'):
                            usage = message.usage
                            if isinstance(usage, dict):
                                # Sum ALL input token types (regular + cache creation + cache read)
                                total_input_tokens = (
                                    usage.get('input_tokens', 0) +
                                    usage.get('cache_creation_input_tokens', 0) +
                                    usage.get('cache_read_input_tokens', 0)
                                )
                                total_output_tokens = usage.get('output_tokens', 0)
                        
                        # Extract tool calls and text
                        if hasattr(message, 'content'):
                            for block in message.content:
                                if hasattr(block, 'text'):
                                    response_text += block.text
                                # Extract structured data from tool call - check by class name
                                elif type(block).__name__ == 'ToolUseBlock':
                                    # Check for ANY variation of submit_analysis
                                    if 'submit_analysis' in block.name.lower():
                                        tool_was_called = True
                                        tool_result = block.input
                    
                    # Safety net: Retry if tool wasn't called on first attempt
                    if not tool_was_called:
                        print(f"   ⚠️  Tool not called, retrying with explicit request...")
                        await client.query("Please call the mcp__analyzer__submit_analysis tool NOW with your findings.")
                        
                        async for message in client.receive_response():
                            # Update token counts from retry
                            if type(message).__name__ == 'ResultMessage' and hasattr(message, 'usage'):
                                usage = message.usage
                                if isinstance(usage, dict):
                                    total_input_tokens += (
                                        usage.get('input_tokens', 0) +
                                        usage.get('cache_creation_input_tokens', 0) +
                                        usage.get('cache_read_input_tokens', 0)
                                    )
                                    total_output_tokens += usage.get('output_tokens', 0)
                            
                            if hasattr(message, 'content'):
                                for block in message.content:
                                    if hasattr(block, 'text'):
                                        response_text += block.text
                                    elif type(block).__name__ == 'ToolUseBlock':
                                        if 'submit_analysis' in block.name.lower():
                                            tool_was_called = True
                                            tool_result = block.input
                        
                        if tool_was_called:
                            print(f"   ✅ Tool called successfully on retry")
                
                    # Use tool result if available, otherwise parse text
                    if tool_result:
                        # With new schema, recommendations should already be an array
                        recs = tool_result.get('recommendations', [])
                        # Handle legacy string format if needed
                        if isinstance(recs, str):
                            try:
                                recs = json.loads(recs)
                            except:
                                recs = []
                        # Ensure it's a list
                        if not isinstance(recs, list):
                            recs = []
                        
                        analysis_data = {
                            'root_cause': tool_result.get('root_cause', 'Unknown'),
                            'problematic_code': tool_result.get('problematic_code', 'Not found'),
                            'recommendations': recs
                        }
                    else:
                        # Fallback to text parsing
                        analysis_data = self._parse_response(response_text)
                    
                    # Extract relevant test info
                    relevant_tests = [
                        f"Input: {state.test_case.input_value}, Expected: {state.test_case.expected}, Got: {state.return_value}"
                        for state in group.assertion_states[:3]
                    ]
                    
                    results.append(AnalysisResult(
                        group_name=group.metadata.name,
                        group_description=group.metadata.description,
                        root_cause=analysis_data.get('root_cause', 'Unknown'),
                        problematic_code=analysis_data.get('problematic_code', 'Not found'),
                        recommendations=analysis_data.get('recommendations', []),
                        relevant_tests=relevant_tests
                    ))
                    
                except Exception as e:
                    import traceback
                    print(f"\n⚠️  Error analyzing group '{group.metadata.name}': {e}")
                    traceback.print_exc()
                    results.append(AnalysisResult(
                        group_name=group.metadata.name,
                        group_description=group.metadata.description,
                        root_cause=f'Error: {str(e)}',
                        problematic_code='Analysis failed',
                        recommendations=[],
                        relevant_tests=[]
                    ))
        
        # Calculate cost with proper cache pricing
        # Note: total_input_tokens already includes all input types summed
        # Claude Sonnet 4 pricing:
        # - Regular input: $3/M
        # - Cache write: $3.75/M  
        # - Cache read: $0.30/M (10x cheaper!)
        # - Output: $15/M
        # 
        # For simplicity, we use blended rate since we don't track each type separately in results
        # Total input cost ≈ $0.30-3.00/M depending on cache hits
        input_cost = (total_input_tokens / 1_000_000) * 3.0  # Conservative estimate
        output_cost = (total_output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost
        
        print(f"\n📊 Token Usage:")
        print(f"   Input:  {total_input_tokens:,} tokens (${input_cost:.4f})")
        print(f"   Output: {total_output_tokens:,} tokens (${output_cost:.4f})")
        print(f"   Total:  ${total_cost:.4f}")
        print(f"   Note: Actual cost may be lower due to prompt caching")
        
        return results
    
    def _build_minimal_prompt(self, group: AssertionStateGroup) -> str:
        """Build minimal prompt for this group to save tokens."""
        # Get sample error (just first one)
        sample_error = ""
        if group.assertion_states:
            state = group.assertion_states[0]
            error_msg = state.test_case.error_message or 'Test failed'
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."
            sample_error = error_msg
        
        prompt = f"""Analyze this test failure:

Pattern: {group.metadata.name}
Failed tests: {len(group.assertion_states)}
Error: {sample_error}

Steps:
1. Use Grep to find relevant code
2. Use Read to examine the buggy code
3. Identify the root cause

THEN YOU MUST call mcp__analyzer__submit_analysis with:
- root_cause: "file.py:line - specific issue description"
- problematic_code: "the exact code snippet causing the problem"
- recommendations: array of fix objects, where EACH recommendation MUST include:
  * type: "code" | "prompt" | "config" | "design"
  * title: short description
  * description: why this fix is needed
  * file: the file path to modify
  * line_number: which line(s) to change (e.g., "6" or "6-8")
  * current_code: the buggy code snippet
  * fixed_code: the corrected code that fixes the issue
  * priority: "high" | "medium" | "low"
  * effort: "high" | "medium" | "low"

CRITICAL: For code-type recommendations, you MUST provide the actual fixed code, not just a description.

DO NOT just describe the fix - you MUST call the tool to submit your analysis."""
        
        return prompt


def analyze_groups(
    groups: List[AssertionStateGroup],
    project_path: str,
    api_key: str,
    model: str = "claude-sonnet-4-20250514"
) -> List[AnalysisResult]:
    """
    Convenience function to analyze error groups synchronously.

    Args:
        groups: Error groups from clustering
        project_path: Path to project
        api_key: Anthropic API key
        model: Claude model to use

    Returns:
        List of analysis results
    """
    analyzer = CodeAnalyzer(project_path, api_key, model)
    
    # Run async analysis
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(analyzer.analyze_multiple_groups(groups))
    finally:
        loop.close()

