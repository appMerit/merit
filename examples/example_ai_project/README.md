# Example AI Project

This is an example AI project with intentional issues that can be used to test Merit Analyzer.

## Issues in the Code

This project contains several intentional issues that Merit Analyzer should be able to detect:

1. **Input Validation Issues**: The `PricingAgent.handle_pricing_inquiry()` method doesn't properly validate empty inputs
2. **Vague Responses**: Pricing inquiries return vague responses instead of specific information
3. **Timeout Issues**: Complex requests don't have proper timeout handling
4. **Error Handling**: Poor error handling for edge cases

## Running the Example

```bash
cd examples/example_ai_project
python main.py
```

## Testing with Merit Analyzer

1. Run the example project to generate test results
2. Use Merit Analyzer to analyze the failures:

```bash
merit-analyze --project-path examples/example_ai_project --test-results test_results.json --api-key your-api-key
```

This will demonstrate how Merit Analyzer can identify patterns in the failures and provide specific recommendations for fixing them.
