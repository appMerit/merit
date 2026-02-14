"""Symtable-based dependency builder for sut resources.

Uses Python's symtable module for scope analysis (which names a function
references) and a thin AST layer only for mapping import names to their
resolved module paths.
"""

import ast
from enum import Enum
import importlib.util
import inspect
import symtable
import sys
from collections import deque
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True, frozen=True)
class DependencyEntry:
    """Repository-local dependency.

    Attributes
    ----------
    name : str
        Fully qualified module name.
    file_path : Path
        Absolute path to the resolved module source file.
    """

    module_name: str
    file_path: Path
    # TODO: Add member name
    # TODO: Add member location


class DependencyCollectionMode(str, Enum):
    """Strategy controlling graph expansion.

    Attributes
    ----------
    MODULE : str
        Traverse dependencies from module-level imports for each discovered module.
    SYMBOL : str
        Start from a specific symbol in the seed module and follow only reachable
        imports from that symbol's scope.
    """

    MODULE = "module"
    SYMBOL = "symbol"


def _resolve_from_import(node: ast.ImportFrom, module_name: str, module_file: Path) -> str:
    """Resolve a ``from ... import`` statement to a module path"""

    if node.level == 0:
        assert node.module
        return node.module
    package = module_name if module_file.name == "__init__.py" else module_name.rpartition(".")[0]
    return importlib.util.resolve_name("." * node.level + (node.module or ""), package)


class ImportIndex:
    """Index import statements per scope using AST"""

    def __init__(self, source: str, module_name: str, module_file: Path) -> None:
        self._module_level: dict[str, str] = {}
        self._function_level: dict[str, dict[str, str]] = {}
        self._local_functions: set[str] = set()
        self._build(ast.parse(source), module_name, module_file)

    @property
    def local_functions(self) -> set[str]:
        """Return locally defined function names for this module"""

        return self._local_functions

    def get_module_level(self, name: str) -> str | None:
        """Get module-level import target for a local symbol"""

        return self._module_level.get(name)

    def get_function_level(self, func_name: str, name: str) -> str | None:
        """Get function-scope import target for a local symbol"""

        func_imports = self._function_level.get(func_name)
        return func_imports.get(name) if func_imports else None

    def all_module_imports(self) -> set[str]:
        """Return all module-level imported module names"""

        return set(self._module_level.values())

    def _build(self, tree: ast.Module, module_name: str, module_file: Path) -> None:
        """Populate import lookup structures from parsed AST"""

        for stmt in tree.body:
            match stmt:
                case ast.Import() | ast.ImportFrom():
                    for local, mod in self._extract(stmt, module_name, module_file):
                        self._module_level[local] = mod
                case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name):
                    self._local_functions.add(name)
                    func_imports: dict[str, str] = {}
                    for node in ast.walk(stmt):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            for local, mod in self._extract(node, module_name, module_file):
                                func_imports[local] = mod
                    if func_imports:
                        self._function_level[name] = func_imports

    @staticmethod
    def _extract(node: ast.stmt, module_name: str, module_file: Path) -> list[tuple[str, str]]:
        """Extract local alias to module mappings from an import node"""
        results: list[tuple[str, str]] = []
        match node:
            case ast.Import(names=names):
                for alias in names:
                    local = alias.asname or alias.name.split(".", 1)[0]
                    results.append((local, alias.name))
            case ast.ImportFrom():
                resolved = _resolve_from_import(node, module_name, module_file)
                for alias in node.names:
                    if alias.name != "*":
                        results.append((alias.asname or alias.name, resolved))
        return results


class ModuleAnalyzer:
    """Use symtable to find which imported modules are reachable from targets.

    Targeted mode traces from specific function names; full mode returns
    all module-level imports.
    """

    def __init__(self, source: str, filename: str) -> None:
        self._table = symtable.symtable(source, filename, "exec")
        self._children = {child.get_name(): child for child in self._table.get_children()}

    def reachable_modules(self, targets: set[str] | None, index: ImportIndex) -> set[str]:
        """Compute imported modules reachable from a symbol set.

        Parameters
        ----------
        targets : set[str] | None
            Starting symbols to trace. When ``None``, returns all module-level
            imports.
        index : ImportIndex
            Import alias resolution index for the same module source.

        Returns
        -------
        set[str]
            Resolved module names reachable from ``targets``.
        """

        if targets is None:
            return self._all_imports(index)
        return self._trace_from(targets, index)

    def _all_imports(self, index: ImportIndex) -> set[str]:
        """Collect all module-level imported modules"""

        modules: set[str] = set()
        for sym in self._table.get_symbols():
            if sym.is_imported():
                mod = index.get_module_level(sym.get_name())
                if mod:
                    modules.add(mod)
        return modules

    def _trace_from(self, targets: set[str], index: ImportIndex) -> set[str]:
        """Trace reachable imports from target symbols using BFS"""

        modules: set[str] = set()
        visited: set[str] = set()
        pending: deque[str] = deque(targets)

        while pending:
            name = pending.popleft()
            if name in visited:
                continue
            visited.add(name)

            child = self._children.get(name)
            if child is None:
                # Target is not a function — might be an imported symbol.
                mod = index.get_module_level(name)
                if mod:
                    modules.add(mod)
                continue

            for sym in child.get_symbols():
                sym_name = sym.get_name()

                if sym.is_imported():
                    mod = index.get_function_level(name, sym_name)
                    if mod:
                        modules.add(mod)
                elif sym.is_global() and not sym.is_assigned():
                    mod = index.get_module_level(sym_name)
                    if mod:
                        modules.add(mod)
                    elif sym_name in index.local_functions and sym_name not in visited:
                        pending.append(sym_name)

        return modules


class ModuleResolver:
    """Resolve module names to repository-local file paths."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    @cache
    def resolve(self, module_name: str) -> Path | None:
        """Resolve a module name to a local source file path.

        Parameters
        ----------
        module_name : str
            Fully qualified module name to resolve.

        Returns
        -------
        Path | None
            Absolute module path when the module is repository-local, otherwise
            ``None``.
        """

        if module_name.split(".", 1)[0] in sys.stdlib_module_names:
            return None
        spec = importlib.util.find_spec(module_name)
        if spec is None or not spec.has_location or spec.origin is None:
            return None
        module_path = Path(spec.origin).resolve()
        if "site-packages" in module_path.parts or not module_path.is_relative_to(self._repo_root):
            return None
        return module_path


class DependencyCollector:
    """BFS traversal collecting transitive repository-local dependencies."""

    def __init__(self, repo_root: Path) -> None:
        self._resolver = ModuleResolver(repo_root)
        self._cache: dict[Path, tuple[ImportIndex, ModuleAnalyzer]] = {}

    def collect(
        self,
        *,
        seed_module: str,
        seed_file: Path,
        mode: DependencyCollectionMode = DependencyCollectionMode.MODULE,
        seed_symbol: str | None = None,
    ) -> list[DependencyEntry]:
        """Collect transitive repository-local dependencies for a seed module.

        Parameters
        ----------
        seed_module : str
            Fully qualified module name where traversal starts.
        seed_file : Path
            Source file path for ``seed_module``.
        mode : DependencyCollectionMode, default=DependencyCollectionMode.MODULE
            Collection strategy for initial and subsequent expansion.
        seed_symbol : str | None, default=None
            Symbol name used only when ``mode`` is ``SYMBOL``.

        Returns
        -------
        list[Dependency]
            Sorted dependency entries including the seed module.
        """

        discovered: dict[str, Path] = {seed_module: seed_file}
        pending: deque[tuple[str, set[str] | None]] = deque()
        if mode == DependencyCollectionMode.SYMBOL and seed_symbol:
            pending.append((seed_module, {seed_symbol}))
        else:
            pending.append((seed_module, None))
        if mode == DependencyCollectionMode.MODULE:
            self._enqueue_parent_packages(seed_module, discovered, pending)
        visited: set[str] = set()

        while pending:
            module_name, targets = pending.popleft()
            if module_name in visited:
                continue
            visited.add(module_name)

            file_path = discovered[module_name]
            index, analyzer = self._load(file_path, module_name)
            reachable = analyzer.reachable_modules(targets, index)

            for mod in reachable:
                resolved = self._resolver.resolve(mod)
                if resolved is not None and mod not in discovered:
                    discovered[mod] = resolved
                    pending.append((mod, None))
                    if mode == DependencyCollectionMode.MODULE:
                        self._enqueue_parent_packages(mod, discovered, pending)

        return [
            DependencyEntry(module_name=name, file_path=path)
            for name, path in sorted(discovered.items())
        ]

    def _enqueue_parent_packages(
        self,
        module_name: str,
        discovered: dict[str, Path],
        pending: deque[tuple[str, set[str] | None]],
    ) -> None:
        """Add resolvable parent packages to traversal queues"""

        parts = module_name.split(".")
        for idx in range(1, len(parts)):
            package_name = ".".join(parts[:idx])
            if package_name in discovered:
                continue
            resolved = self._resolver.resolve(package_name)
            if resolved is None:
                continue
            discovered[package_name] = resolved
            pending.append((package_name, None))

    def _load(self, file_path: Path, module_name: str) -> tuple[ImportIndex, ModuleAnalyzer]:
        """Load and cache per-module analysis artifacts"""

        cached = self._cache.get(file_path)
        if cached is not None:
            return cached
        source = file_path.read_text(encoding="utf-8")
        pair = (
            ImportIndex(source, module_name, file_path),
            ModuleAnalyzer(source, str(file_path)),
        )
        self._cache[file_path] = pair
        return pair


def collect_dependencies(
    fn: Callable[..., Any],
    *,
    mode: DependencyCollectionMode | str = DependencyCollectionMode.MODULE,
) -> list[DependencyEntry]:
    """Collect repository-local module dependencies for a callable.

    Parameters
    ----------
    fn : Callable[..., Any]
        Function used as the dependency-graph entry point.
    mode : DependencyCollectionMode | str, default=DependencyCollectionMode.MODULE
        Collection strategy. String values are coerced to
        ``DependencyCollectionMode``.

    Returns
    -------
    list[Dependency]
        Sorted transitive dependencies discovered from ``fn``.
    """

    if isinstance(mode, str):
        mode = DependencyCollectionMode(mode)

    owner_module = inspect.getmodule(fn)
    owner_file_attr = getattr(owner_module, "__file__", None)
    assert owner_module and owner_file_attr

    owner_file = Path(owner_file_attr).resolve()
    repo_root = next(p for p in (owner_file.parent, *owner_file.parents) if (p / ".git").exists())
    collector = DependencyCollector(repo_root)
    return collector.collect(
        seed_module=owner_module.__name__,
        seed_file=owner_file,
        mode=mode,
        seed_symbol=fn.__name__,
    )
