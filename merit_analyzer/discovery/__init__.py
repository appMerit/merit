"""Discovery layer for Merit Analyzer."""

from .project_scanner import ProjectScanner
from .framework_detector import FrameworkDetector
from .code_mapper import CodeMapper

__all__ = [
    "ProjectScanner",
    "FrameworkDetector", 
    "CodeMapper",
]
