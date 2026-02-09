"""Test discovery."""

from merit.testing.discovery.collector import StaticTestReference, collect, collect_static
from merit.testing.discovery.loader import MeritModuleLoader
from merit.testing.models import MeritTestDefinition


# Backwards compatibility alias
TestItem = MeritTestDefinition

__all__ = [
    "MeritModuleLoader",
    "MeritTestDefinition",
    "StaticTestReference",
    "TestItem",
    "collect",
    "collect_static",
]
