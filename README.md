# Merit Analyzer

AI-powered test failure analysis for AI systems.

## Quick Start

### Installation

```bash
# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

### Usage

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY=your_key_here

# Run analysis
merit tests.csv -p ./your_project -o report.md
```

### CSV Format

Your CSV file should have these columns:

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `input_value` | any | Yes | Test input |
| `expected` | any | Yes | Expected output |
| `actual` | any | Yes | Actual output |
| `passed` | bool | Yes | true/false |
| `error_message` | str | No | Error message if failed |
| `additional_context` | str | No | Additional context |

**Example CSV:**

```csv
input_value,expected,actual,passed,error_message
"Calculate price for 2 items","$40","$20",false,"Price calculation incorrect"
"Format date 2024-01-15","Jan 15, 2024","2024-01-15",false,"Date not formatted"
"Validate email test@example.com","true","false",false,"Email validation failed"
```

## How It Works

1. **Parse CSV** → Loads test results into structured data
2. **Cluster Failures** → Groups similar failures using embeddings + HDBSCAN
3. **Analyze Code** → Uses Claude Agent SDK to find root causes in your codebase
4. **Generate Report** → Creates markdown report with fixes

## Output Format

The tool generates a markdown report with:

```
# Test Failure Analysis Report

## 1. ERROR_GROUP_NAME

### Problematic Behavior
Description of what's happening...

### Root Cause
file.py:line - specific issue

### Problematic Code
[Code snippet]

### Recommended Fixes
1. Fix title (Priority: HIGH, Effort: low)
   Detailed description with code examples...

### Relevant Test Results
- Input: ..., Expected: ..., Got: ...
```

## Structure

**Key data abstractions:**
- `src/merit_analyzer/types` - Data models (TestCase, AssertionState, etc.)

**Key stateless processors:** 
- `src/merit_analyzer/processors` - Clustering, markdown formatting

**Key stateful engines:**
- `src/merit_analyzer/engines` - LLM client, code analyzer

**Tests:**
- `tests/unit`

## Development Branches

- **`main`** - Stable release branch
- **`mark/end-to-end`** - End-to-end implementation and testing
- **`nick/clustering`** - Pattern clustering improvements