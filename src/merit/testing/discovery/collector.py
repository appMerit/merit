"""Test discovery for merit_* files and functions."""

import ast
import importlib.util
import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from merit.testing.decorators.tags import TagData, get_tag_data, merge_tag_data
from merit.testing.discovery.loader import MeritModuleLoader
from merit.testing.models import MeritTestDefinition, Modifier


@dataclass(frozen=True)
class StaticTestReference:
    """A test reference discovered from source without importing the module."""

    name: str
    module_path: Path
    class_name: str | None = None
    tags: frozenset[str] = frozenset()

    @property
    def full_name(self) -> str:
        """Full qualified name for matching and filtering."""
        if self.class_name:
            return f"{self.module_path.stem}::{self.class_name}::{self.name}"
        return f"{self.module_path.stem}::{self.name}"


def _resolve_path(path: Path | str | None) -> Path:
    if path is None:
        return Path.cwd().resolve()
    if isinstance(path, str):
        return Path(path).resolve()
    return path.resolve()


def _iter_merit_files(path: Path) -> list[Path]:
    if path.is_file():
        if path.name.startswith("merit_") and path.suffix == ".py":
            return [path]
        return []
    if path.is_dir():
        return sorted(path.rglob("merit_*.py"))
    return []


def _is_tag_root(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Name):
        return expr.id == "tag"
    if isinstance(expr, ast.Attribute):
        return isinstance(expr.value, ast.Name) and expr.value.id == "merit" and expr.attr == "tag"
    return False


def _is_tag_method(expr: ast.expr, method_name: str) -> bool:
    return isinstance(expr, ast.Attribute) and expr.attr == method_name and _is_tag_root(expr.value)


def _extract_static_tags(decorators: list[ast.expr]) -> set[str]:
    tags: set[str] = set()
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        if _is_tag_root(decorator.func):
            for arg in decorator.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    tags.add(arg.value)
            continue
        if _is_tag_method(decorator.func, "skip"):
            tags.add("skip")
            continue
        if _is_tag_method(decorator.func, "xfail"):
            tags.add("xfail")
    return tags


def _collect_static_from_module(path: Path) -> list[StaticTestReference]:
    module = ast.parse(path.read_text(), filename=str(path))
    refs: list[StaticTestReference] = []

    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("merit_"):
                refs.append(
                    StaticTestReference(
                        name=node.name,
                        module_path=path,
                        tags=frozenset(_extract_static_tags(node.decorator_list)),
                    )
                )
            continue

        if isinstance(node, ast.ClassDef) and node.name.startswith("Merit"):
            class_tags = _extract_static_tags(node.decorator_list)
            for class_node in node.body:
                if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if class_node.name.startswith("merit_"):
                        tags = class_tags | _extract_static_tags(class_node.decorator_list)
                        refs.append(
                            StaticTestReference(
                                name=class_node.name,
                                module_path=path,
                                class_name=node.name,
                                tags=frozenset(tags),
                            )
                        )

    return refs


def collect_static(path: Path | str | None = None) -> list[StaticTestReference]:
    """Discover test names and tags without importing modules."""
    resolved_path = _resolve_path(path)
    refs: list[StaticTestReference] = []

    for file_path in _iter_merit_files(resolved_path):
        refs.extend(_collect_static_from_module(file_path))

    return refs


def _load_module(path: Path) -> ModuleType:
    """Dynamically load a Python module from path."""
    # Use unique module name to avoid collisions
    module_name = f"merit_discovery.{path.stem}_{hash(path)}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
        loader=MeritModuleLoader(fullname=module_name, path=path),
    )
    if spec is None or spec.loader is None:
        msg = f"Cannot load module from {path}"
        raise ImportError(msg)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _extract_test_params(fn: Callable[..., Any]) -> list[str]:
    """Extract parameter names from function signature (excluding 'self')."""
    sig = inspect.signature(fn)
    return [p for p in sig.parameters if p != "self"]


def _get_modifiers(fn: Callable[..., Any]) -> list[Modifier]:
    """Extract modifiers from function's __merit_modifiers__ attribute."""
    return getattr(fn, "__merit_modifiers__", [])


def _collect_from_module(module: ModuleType, module_path: Path) -> list[MeritTestDefinition]:
    """Collect all merit_* tests from a module."""
    items: list[MeritTestDefinition] = []

    for name, obj in inspect.getmembers(module):
        if name.startswith("merit_") and inspect.isfunction(obj):
            items.append(_build_item_for_callable(obj, name, module_path))

        elif name.startswith("Merit") and inspect.isclass(obj):
            class_tags = get_tag_data(obj)
            for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                if method_name.startswith("merit_"):
                    items.append(
                        _build_item_for_callable(
                            method,
                            method_name,
                            module_path,
                            class_name=name,
                            parent_tags=class_tags,
                        )
                    )

    return items


def _build_item_for_callable(
    fn: Callable[..., Any],
    name: str,
    module_path: Path,
    class_name: str | None = None,
    parent_tags: TagData | None = None,
) -> MeritTestDefinition:
    """Create a single MeritTestDefinition for a callable with modifiers attached."""
    combined_tags = merge_tag_data(parent_tags, get_tag_data(fn))
    modifiers = reversed(_get_modifiers(fn))
    definition_error: str | None = getattr(fn, "__merit_definition_error__", None)

    return MeritTestDefinition(
        name=name,
        fn=fn,
        module_path=module_path,
        is_async=inspect.iscoroutinefunction(fn),
        params=_extract_test_params(fn),
        class_name=class_name,
        modifiers=list(modifiers),
        tags=set(combined_tags.tags),
        skip_reason=combined_tags.skip_reason,
        xfail_reason=combined_tags.xfail_reason,
        xfail_strict=combined_tags.xfail_strict,
        definition_error=definition_error,
        run_inline=getattr(fn, "__merit_run_inline__", False),
    )


def collect(path: Path | str | None = None) -> list[MeritTestDefinition]:
    """Discover all merit_* tests from path.

    Args:
        path: File or directory to search. Defaults to current directory.

    Returns:
        List of discovered MeritTestDefinition objects.

    Example:
        items = collect()  # Current directory
        items = collect("merit_agents.py")  # Specific file
        items = collect("./tests/")  # Directory
    """
    path = _resolve_path(path)
    items: list[MeritTestDefinition] = []

    for file_path in _iter_merit_files(path):
        module = _load_module(file_path)
        items.extend(_collect_from_module(module, file_path))

    return items
