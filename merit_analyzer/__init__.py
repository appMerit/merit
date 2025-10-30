"""
Merit Analyzer - AI system test failure analysis and recommendation engine.

This package provides tools to analyze AI system test failures and generate
specific, actionable recommendations for fixing them.
"""

from .core.analyzer import MeritAnalyzer
from .models.test_result import TestResult, TestResultBatch
from .models.report import AnalysisReport, ReportSummary, PatternSummary, Recommendation

__version__ = "1.0.0"
__author__ = "Merit Analyzer Team"

__all__ = [
    "MeritAnalyzer",
    "TestResult", 
    "TestResultBatch",
    "AnalysisReport",
    "ReportSummary", 
    "PatternSummary",
    "Recommendation",
]
