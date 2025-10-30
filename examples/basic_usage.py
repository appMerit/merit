"""Basic usage example for Merit Analyzer."""

import json
from merit_analyzer import MeritAnalyzer, TestResult


def main():
    """Demonstrate basic usage of Merit Analyzer."""
    
    # Example test results
    test_results = [
        TestResult(
            test_id="test_001",
            test_name="pricing_inquiry",
            input="How much does the pro plan cost?",
            expected_output="$49/month",
            actual_output="We have various pricing tiers available",
            status="failed",
            failure_reason="Response too vague, missing specific price",
            category="pricing",
            tags=["pricing", "pro_plan"]
        ),
        TestResult(
            test_id="test_002", 
            test_name="pricing_inquiry_2",
            input="What's the cost of the enterprise plan?",
            expected_output="$199/month",
            actual_output="Please contact sales for enterprise pricing",
            status="failed",
            failure_reason="Should provide direct pricing, not redirect to sales",
            category="pricing",
            tags=["pricing", "enterprise"]
        ),
        TestResult(
            test_id="test_003",
            test_name="support_inquiry",
            input="How do I reset my password?",
            expected_output="Go to Settings > Security > Reset Password",
            actual_output="Go to Settings > Security > Reset Password",
            status="passed",
            category="support",
            tags=["support", "password"]
        ),
        TestResult(
            test_id="test_004",
            test_name="pricing_inquiry_3",
            input="Show me pricing for all plans",
            expected_output="Basic: $9/month, Pro: $49/month, Enterprise: $199/month",
            actual_output="Our plans start at $9/month",
            status="failed",
            failure_reason="Incomplete pricing information",
            category="pricing",
            tags=["pricing", "all_plans"]
        )
    ]
    
    # Initialize analyzer
    print("🚀 Initializing Merit Analyzer...")
    analyzer = MeritAnalyzer(
        project_path="./example_project",  # Replace with your project path
        api_key="your-api-key-here",      # Replace with your API key
        provider="anthropic"
    )
    
    # Run analysis
    print("🔍 Running analysis...")
    report = analyzer.analyze(test_results)
    
    # Display results
    print("\n📊 Analysis Results:")
    print(f"Total tests: {report.summary.total_tests}")
    print(f"Failed: {report.summary.failed}")
    print(f"Pass rate: {report.summary.pass_rate:.1%}")
    print(f"Patterns found: {report.summary.patterns_found}")
    print(f"Recommendations: {len(report.recommendations)}")
    
    # Display patterns
    if report.patterns:
        print("\n🔍 Failure Patterns:")
        for pattern_name, pattern in report.patterns.items():
            print(f"  {pattern_name}: {pattern.failure_count} failures")
            if pattern.root_cause:
                print(f"    Root cause: {pattern.root_cause}")
    
    # Display top recommendations
    if report.recommendations:
        print("\n💡 Top Recommendations:")
        high_priority = [r for r in report.recommendations if r.priority.value == "high"]
        for i, rec in enumerate(high_priority[:3], 1):
            print(f"  {i}. {rec.title}")
            print(f"     Type: {rec.type.value.title()}")
            print(f"     Effort: {rec.effort_estimate}")
            print(f"     Impact: {rec.expected_impact}")
    
    # Save report
    print("\n💾 Saving report...")
    analyzer.save_report(report, "example_analysis.json")
    
    # Export recommendations
    print("📄 Exporting recommendations...")
    analyzer.export_recommendations(report, "example_recommendations.md", "markdown")
    
    print("✅ Analysis complete!")


if __name__ == "__main__":
    main()
