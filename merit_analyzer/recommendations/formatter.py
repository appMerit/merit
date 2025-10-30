"""Format recommendations for different output formats."""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from ..models.recommendation import Recommendation
from ..models.pattern import Pattern


class RecommendationFormatter:
    """Format recommendations for different output formats."""

    def __init__(self):
        """Initialize formatter."""
        self.template_cache = {}

    def format_recommendations(self, 
                             recommendations: List[Recommendation],
                             format_type: str = "markdown",
                             include_patterns: bool = True,
                             patterns: Optional[Dict[str, Pattern]] = None) -> str:
        """
        Format recommendations in the specified format.

        Args:
            recommendations: List of recommendations to format
            format_type: Output format (markdown, html, json, text)
            include_patterns: Whether to include pattern information
            patterns: Dictionary of patterns for context

        Returns:
            Formatted recommendations string
        """
        if format_type.lower() == "markdown":
            return self._format_markdown(recommendations, include_patterns, patterns)
        elif format_type.lower() == "html":
            return self._format_html(recommendations, include_patterns, patterns)
        elif format_type.lower() == "json":
            return self._format_json(recommendations, include_patterns, patterns)
        elif format_type.lower() == "text":
            return self._format_text(recommendations, include_patterns, patterns)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    def _format_markdown(self, 
                        recommendations: List[Recommendation],
                        include_patterns: bool,
                        patterns: Optional[Dict[str, Pattern]]) -> str:
        """Format recommendations as Markdown."""
        if not recommendations:
            return "# Recommendations\n\nNo recommendations available.\n"
        
        md = f"# Recommendations\n\n"
        md += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += f"Total recommendations: {len(recommendations)}\n\n"
        
        # Summary by priority
        priority_counts = {}
        for rec in recommendations:
            priority = rec.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        md += "## Summary by Priority\n\n"
        for priority in ["high", "medium", "low"]:
            count = priority_counts.get(priority, 0)
            md += f"- **{priority.title()}**: {count} recommendations\n"
        md += "\n"
        
        # Group by priority
        high_priority = [r for r in recommendations if r.priority.value == "high"]
        medium_priority = [r for r in recommendations if r.priority.value == "medium"]
        low_priority = [r for r in recommendations if r.priority.value == "low"]
        
        if high_priority:
            md += "## 🔴 High Priority Recommendations\n\n"
            md += self._format_recommendation_list_markdown(high_priority, patterns)
        
        if medium_priority:
            md += "## 🟡 Medium Priority Recommendations\n\n"
            md += self._format_recommendation_list_markdown(medium_priority, patterns)
        
        if low_priority:
            md += "## 🟢 Low Priority Recommendations\n\n"
            md += self._format_recommendation_list_markdown(low_priority, patterns)
        
        return md

    def _format_recommendation_list_markdown(self, 
                                           recommendations: List[Recommendation],
                                           patterns: Optional[Dict[str, Pattern]]) -> str:
        """Format a list of recommendations as Markdown."""
        md = ""
        
        for i, rec in enumerate(recommendations, 1):
            md += f"### {i}. {rec.title}\n\n"
            
            # Basic info
            md += f"**Type**: {rec.type.value.title()}\n"
            md += f"**Effort**: {rec.effort_estimate}\n"
            md += f"**Location**: `{rec.location}`\n\n"
            
            # Description
            md += f"**Description**: {rec.description}\n\n"
            
            # Implementation
            if rec.implementation:
                md += f"**Implementation**:\n\n{rec.implementation}\n\n"
            
            # Expected impact
            if rec.expected_impact:
                md += f"**Expected Impact**: {rec.expected_impact}\n\n"
            
            # Rationale
            if rec.rationale:
                md += f"**Rationale**: {rec.rationale}\n\n"
            
            # Code diff
            if rec.code_diff:
                md += f"**Code Changes**:\n\n```diff\n{rec.code_diff}\n```\n\n"
            
            # Before/after examples
            if rec.before_after_examples:
                md += "**Before/After Examples**:\n\n"
                for key, value in rec.before_after_examples.items():
                    md += f"**{key}**:\n```\n{value}\n```\n\n"
            
            # Dependencies
            if rec.dependencies:
                md += f"**Dependencies**: {', '.join(rec.dependencies)}\n\n"
            
            # Tags
            if rec.tags:
                md += f"**Tags**: {', '.join(rec.tags)}\n\n"
            
            md += "---\n\n"
        
        return md

    def _format_html(self, 
                    recommendations: List[Recommendation],
                    include_patterns: bool,
                    patterns: Optional[Dict[str, Pattern]]) -> str:
        """Format recommendations as HTML."""
        if not recommendations:
            return "<h1>Recommendations</h1><p>No recommendations available.</p>"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Merit Analyzer Recommendations</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .recommendation {{ border: 1px solid #ddd; margin: 20px 0; padding: 20px; border-radius: 5px; }}
        .high-priority {{ border-left: 5px solid #dc3545; }}
        .medium-priority {{ border-left: 5px solid #ffc107; }}
        .low-priority {{ border-left: 5px solid #28a745; }}
        .priority-badge {{ display: inline-block; padding: 4px 8px; border-radius: 3px; color: white; font-size: 12px; }}
        .high {{ background-color: #dc3545; }}
        .medium {{ background-color: #ffc107; }}
        .low {{ background-color: #28a745; }}
        .code {{ background-color: #f8f9fa; padding: 10px; border-radius: 3px; font-family: monospace; }}
        .summary {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>Merit Analyzer Recommendations</h1>
    <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Total recommendations: {len(recommendations)}</p>
"""
        
        # Priority summary
        priority_counts = {}
        for rec in recommendations:
            priority = rec.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        html += "<ul>"
        for priority in ["high", "medium", "low"]:
            count = priority_counts.get(priority, 0)
            html += f"<li><strong>{priority.title()}</strong>: {count} recommendations</li>"
        html += "</ul></div>"
        
        # Recommendations
        for i, rec in enumerate(recommendations, 1):
            priority_class = f"{rec.priority.value}-priority"
            html += f"""
    <div class="recommendation {priority_class}">
        <h3>{i}. {rec.title}</h3>
        <p><span class="priority-badge {rec.priority.value}">{rec.priority.value.upper()}</span></p>
        <p><strong>Type:</strong> {rec.type.value.title()}</p>
        <p><strong>Effort:</strong> {rec.effort_estimate}</p>
        <p><strong>Location:</strong> <code>{rec.location}</code></p>
        <p><strong>Description:</strong> {rec.description}</p>
"""
            
            if rec.implementation:
                html += f"<p><strong>Implementation:</strong></p><div class=\"code\">{rec.implementation}</div>"
            
            if rec.expected_impact:
                html += f"<p><strong>Expected Impact:</strong> {rec.expected_impact}</p>"
            
            if rec.rationale:
                html += f"<p><strong>Rationale:</strong> {rec.rationale}</p>"
            
            if rec.code_diff:
                html += f"<p><strong>Code Changes:</strong></p><div class=\"code\">{rec.code_diff}</div>"
            
            if rec.before_after_examples:
                html += "<p><strong>Before/After Examples:</strong></p>"
                for key, value in rec.before_after_examples.items():
                    html += f"<p><strong>{key}:</strong></p><div class=\"code\">{value}</div>"
            
            if rec.dependencies:
                html += f"<p><strong>Dependencies:</strong> {', '.join(rec.dependencies)}</p>"
            
            if rec.tags:
                html += f"<p><strong>Tags:</strong> {', '.join(rec.tags)}</p>"
            
            html += "</div>"
        
        html += "</body></html>"
        return html

    def _format_json(self, 
                    recommendations: List[Recommendation],
                    include_patterns: bool,
                    patterns: Optional[Dict[str, Pattern]]) -> str:
        """Format recommendations as JSON."""
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_recommendations": len(recommendations),
            "recommendations": []
        }
        
        # Add pattern information if requested
        if include_patterns and patterns:
            data["patterns"] = {}
            for pattern_name, pattern in patterns.items():
                data["patterns"][pattern_name] = {
                    "name": pattern.name,
                    "failure_count": pattern.failure_count,
                    "failure_rate": pattern.failure_rate,
                    "keywords": pattern.keywords,
                }
        
        # Add recommendations
        for rec in recommendations:
            rec_data = {
                "title": rec.title,
                "description": rec.description,
                "priority": rec.priority.value,
                "type": rec.type.value,
                "location": rec.location,
                "implementation": rec.implementation,
                "expected_impact": rec.expected_impact,
                "effort_estimate": rec.effort_estimate,
                "rationale": rec.rationale,
                "code_diff": rec.code_diff,
                "before_after_examples": rec.before_after_examples,
                "dependencies": rec.dependencies,
                "tags": rec.tags,
            }
            data["recommendations"].append(rec_data)
        
        return json.dumps(data, indent=2)

    def _format_text(self, 
                    recommendations: List[Recommendation],
                    include_patterns: bool,
                    patterns: Optional[Dict[str, Pattern]]) -> str:
        """Format recommendations as plain text."""
        if not recommendations:
            return "Recommendations\n\nNo recommendations available.\n"
        
        text = f"Merit Analyzer Recommendations\n"
        text += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        text += f"Total recommendations: {len(recommendations)}\n\n"
        
        # Group by priority
        high_priority = [r for r in recommendations if r.priority.value == "high"]
        medium_priority = [r for r in recommendations if r.priority.value == "medium"]
        low_priority = [r for r in recommendations if r.priority.value == "low"]
        
        if high_priority:
            text += "HIGH PRIORITY RECOMMENDATIONS\n"
            text += "=" * 40 + "\n\n"
            text += self._format_recommendation_list_text(high_priority)
        
        if medium_priority:
            text += "MEDIUM PRIORITY RECOMMENDATIONS\n"
            text += "=" * 40 + "\n\n"
            text += self._format_recommendation_list_text(medium_priority)
        
        if low_priority:
            text += "LOW PRIORITY RECOMMENDATIONS\n"
            text += "=" * 40 + "\n\n"
            text += self._format_recommendation_list_text(low_priority)
        
        return text

    def _format_recommendation_list_text(self, recommendations: List[Recommendation]) -> str:
        """Format a list of recommendations as plain text."""
        text = ""
        
        for i, rec in enumerate(recommendations, 1):
            text += f"{i}. {rec.title}\n"
            text += f"   Type: {rec.type.value.title()}\n"
            text += f"   Priority: {rec.priority.value.upper()}\n"
            text += f"   Effort: {rec.effort_estimate}\n"
            text += f"   Location: {rec.location}\n\n"
            
            text += f"   Description: {rec.description}\n\n"
            
            if rec.implementation:
                text += f"   Implementation:\n   {rec.implementation}\n\n"
            
            if rec.expected_impact:
                text += f"   Expected Impact: {rec.expected_impact}\n\n"
            
            if rec.rationale:
                text += f"   Rationale: {rec.rationale}\n\n"
            
            if rec.dependencies:
                text += f"   Dependencies: {', '.join(rec.dependencies)}\n\n"
            
            if rec.tags:
                text += f"   Tags: {', '.join(rec.tags)}\n\n"
            
            text += "-" * 60 + "\n\n"
        
        return text

    def create_summary_report(self, 
                            recommendations: List[Recommendation],
                            patterns: Dict[str, Pattern]) -> str:
        """Create a summary report of recommendations."""
        if not recommendations:
            return "No recommendations available.\n"
        
        # Calculate statistics
        total_recs = len(recommendations)
        high_priority = len([r for r in recommendations if r.priority.value == "high"])
        medium_priority = len([r for r in recommendations if r.priority.value == "medium"])
        low_priority = len([r for r in recommendations if r.priority.value == "low"])
        
        # Group by type
        type_counts = {}
        for rec in recommendations:
            type_name = rec.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        # Calculate total estimated effort
        effort_estimates = []
        for rec in recommendations:
            effort_text = rec.effort_estimate.lower()
            if 'minute' in effort_text:
                minutes_match = re.search(r'(\d+)\s*minute', effort_text)
                if minutes_match:
                    effort_estimates.append(int(minutes_match.group(1)))
            elif 'hour' in effort_text:
                hours_match = re.search(r'(\d+)\s*hour', effort_text)
                if hours_match:
                    effort_estimates.append(int(hours_match.group(1)) * 60)
        
        total_effort_minutes = sum(effort_estimates) if effort_estimates else 0
        
        summary = f"""
Merit Analyzer Summary Report
============================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Recommendations Overview:
- Total recommendations: {total_recs}
- High priority: {high_priority}
- Medium priority: {medium_priority}
- Low priority: {low_priority}

By Type:
"""
        
        for type_name, count in sorted(type_counts.items()):
            summary += f"- {type_name.title()}: {count}\n"
        
        if total_effort_minutes > 0:
            hours = total_effort_minutes // 60
            minutes = total_effort_minutes % 60
            summary += f"\nEstimated Total Effort: {hours}h {minutes}m\n"
        
        # Pattern summary
        if patterns:
            summary += f"\nPatterns Analyzed: {len(patterns)}\n"
            for pattern_name, pattern in patterns.items():
                summary += f"- {pattern_name}: {pattern.failure_count} failures\n"
        
        return summary

    def export_to_file(self, 
                      recommendations: List[Recommendation],
                      filepath: str,
                      format_type: str = "markdown",
                      patterns: Optional[Dict[str, Pattern]] = None) -> None:
        """Export recommendations to a file."""
        content = self.format_recommendations(recommendations, format_type, True, patterns)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Recommendations exported to {filepath}")
