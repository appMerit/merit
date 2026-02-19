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


@dataclass(slots=True, frozen=True)
class ImportBinding:
    """Binding from a local name to an imported module/symbol."""

    module_name: str
    imported_name: str | None = None


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
        self._module_level: dict[str, ImportBinding] = {}
        self._function_level: dict[str, dict[str, ImportBinding]] = {}
        self._local_functions: set[str] = set()
        self._build(ast.parse(source), module_name, module_file)

    @property
    def local_functions(self) -> set[str]:
        """Return locally defined function names for this module"""

        return self._local_functions

    def get_module_level(self, name: str) -> ImportBinding | None:
        """Get module-level import target for a local symbol"""

        return self._module_level.get(name)

    def get_function_level(self, func_name: str, name: str) -> ImportBinding | None:
        """Get function-scope import target for a local symbol"""

        func_imports = self._function_level.get(func_name)
        return func_imports.get(name) if func_imports else None

    def all_module_imports(self) -> set[str]:
        """Return all module-level imported module names"""

        return {binding.module_name for binding in self._module_level.values()}

    def _build(self, tree: ast.Module, module_name: str, module_file: Path) -> None:
        """Populate import lookup structures from parsed AST"""

        for stmt in tree.body:
            match stmt:
                case ast.Import() | ast.ImportFrom():
                    for local, mod in self._extract(stmt, module_name, module_file):
                        self._module_level[local] = mod
                case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name):
                    self._local_functions.add(name)
                    func_imports: dict[str, ImportBinding] = {}
                    for node in ast.walk(stmt):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            for local, mod in self._extract(node, module_name, module_file):
                                func_imports[local] = mod
                    if func_imports:
                        self._function_level[name] = func_imports

    @staticmethod
    def _extract(
        node: ast.stmt, module_name: str, module_file: Path
    ) -> list[tuple[str, ImportBinding]]:
        """Extract local alias to module mappings from an import node"""
        results: list[tuple[str, ImportBinding]] = []
        match node:
            case ast.Import(names=names):
                for alias in names:
                    local = alias.asname or alias.name.split(".", 1)[0]
                    results.append((local, ImportBinding(alias.name)))
            case ast.ImportFrom():
                resolved = _resolve_from_import(node, module_name, module_file)
                for alias in node.names:
                    if alias.name != "*":
                        results.append(
                            (alias.asname or alias.name, ImportBinding(resolved, alias.name))
                        )
        return results


class ModuleAnalyzer:
    """Use symtable to find which imported modules are reachable from targets.

    Targeted mode traces from specific function names; full mode returns
    all module-level imports.
    """

    def __init__(self, source: str, filename: str) -> None:
        self._table = symtable.symtable(source, filename, "exec")
        self._children = {child.get_name(): child for child in self._table.get_children()}
        self._module_symbols = {symbol.get_name() for symbol in self._table.get_symbols()}

    def missing_module_symbols(self, names: set[str]) -> set[str]:
        """Return symbol names not present in this module scope."""

        return {name for name in names if name not in self._module_symbols}

    def reachable_modules(self, targets: set[str] | None, index: ImportIndex) -> set[str]:
        """Compatibility helper returning only module names."""

        return {binding.module_name for binding in self.reachable_bindings(targets, index)}

    def reachable_bindings(
        self, targets: set[str] | None, index: ImportIndex
    ) -> set[ImportBinding]:
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
        set[ImportBinding]
            Import bindings reachable from ``targets``.
        """

        if targets is None:
            return self._all_imports(index)
        return self._trace_from(targets, index)

    def _all_imports(self, index: ImportIndex) -> set[ImportBinding]:
        """Collect all module-level imported modules"""

        modules: set[ImportBinding] = set()
        for sym in self._table.get_symbols():
            if sym.is_imported():
                binding = index.get_module_level(sym.get_name())
                if binding:
                    modules.add(binding)
        return modules

    def _trace_from(self, targets: set[str], index: ImportIndex) -> set[ImportBinding]:
        """Trace reachable imports from target symbols using BFS"""

        modules: set[ImportBinding] = set()
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
                binding = index.get_module_level(name)
                if binding:
                    modules.add(binding)
                continue

            for sym in child.get_symbols():
                sym_name = sym.get_name()

                if sym.is_imported():
                    binding = index.get_function_level(name, sym_name)
                    if binding:
                        modules.add(binding)
                elif sym.is_global() and not sym.is_assigned():
                    binding = index.get_module_level(sym_name)
                    if binding:
                        modules.add(binding)
                    elif sym_name in index.local_functions and sym_name not in visited:
                        pending.append(sym_name)

        return modules


class ModuleResolver:
    """Resolve module names to repository-local file paths."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._resolved: dict[str, Path | None] = {}

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

        if module_name in self._resolved:
            return self._resolved[module_name]
        if module_name.split(".", 1)[0] in sys.stdlib_module_names:
            self._resolved[module_name] = None
            return None
        spec = importlib.util.find_spec(module_name)
        if spec is None or not spec.has_location or spec.origin is None:
            self._resolved[module_name] = None
            return None
        module_path = Path(spec.origin).resolve()
        if "site-packages" in module_path.parts or not module_path.is_relative_to(self._repo_root):
            self._resolved[module_name] = None
            return None
        self._resolved[module_name] = module_path
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
        visited_module: set[str] = set()
        visited_symbol: set[tuple[str, frozenset[str]]] = set()

        while pending:
            module_name, targets = pending.popleft()
            if module_name in visited_module:
                continue
            if targets is None:
                visited_module.add(module_name)
            else:
                symbol_key = (module_name, frozenset(targets))
                if symbol_key in visited_symbol:
                    continue
                visited_symbol.add(symbol_key)

            file_path = discovered[module_name]
            index, analyzer = self._load(file_path, module_name)
            reachable = analyzer.reachable_bindings(targets, index)

            for binding in reachable:
                mod = binding.module_name
                resolved = self._resolver.resolve(mod)
                if resolved is not None and mod not in discovered:
                    discovered[mod] = resolved
                if resolved is not None:
                    pending.append((mod, self._next_targets(mode, binding)))
                    if mode == DependencyCollectionMode.MODULE:
                        self._enqueue_parent_packages(mod, discovered, pending)
            if mode == DependencyCollectionMode.SYMBOL and targets is not None:
                self._enqueue_submodule_fallbacks(
                    module_name=module_name,
                    targets=targets,
                    analyzer=analyzer,
                    discovered=discovered,
                    pending=pending,
                )

        return [
            DependencyEntry(module_name=name, file_path=path)
            for name, path in sorted(discovered.items())
        ]

    @staticmethod
    def _next_targets(mode: DependencyCollectionMode, binding: ImportBinding) -> set[str] | None:
        """Choose target symbols to propagate into a dependency."""

        if mode == DependencyCollectionMode.SYMBOL and binding.imported_name is not None:
            return {binding.imported_name}
        return None

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

    def _enqueue_submodule_fallbacks(
        self,
        *,
        module_name: str,
        targets: set[str],
        analyzer: ModuleAnalyzer,
        discovered: dict[str, Path],
        pending: deque[tuple[str, set[str] | None]],
    ) -> None:
        """When `from pkg import name` can't be resolved in pkg, try pkg.name."""

        for symbol in analyzer.missing_module_symbols(targets):
            submodule = f"{module_name}.{symbol}"
            resolved = self._resolver.resolve(submodule)
            if resolved is None:
                continue
            if submodule not in discovered:
                discovered[submodule] = resolved
            pending.append((submodule, None))

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
    if not (owner_module and owner_file_attr):
        raise ValueError("Cannot determine module or file for the provided callable")

    owner_file = Path(owner_file_attr).resolve()
    repo_root = next(p for p in (owner_file.parent, *owner_file.parents) if (p / ".git").exists())
    collector = DependencyCollector(repo_root)
    return collector.collect(
        seed_module=owner_module.__name__,
        seed_file=owner_file,
        mode=mode,
        seed_symbol=fn.__name__,
    )
