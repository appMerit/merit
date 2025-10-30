"""Data models for Merit Analyzer."""

from .test_result import TestResult, TestResultBatch
from .pattern import Pattern
from .recommendation import Recommendation
from .report import AnalysisReport, ReportSummary, PatternSummary

__all__ = [
    "TestResult",
    "TestResultBatch", 
    "Pattern",
    "Recommendation",
    "AnalysisReport",
    "ReportSummary",
    "PatternSummary",
]
