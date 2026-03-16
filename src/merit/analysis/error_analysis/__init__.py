"""Error analysis package."""

from .collector import ErrorDataCollector
from .dependency_scope import DependencyScopeBuilder


__all__ = ["ErrorDataCollector", "DependencyScopeBuilder"]
