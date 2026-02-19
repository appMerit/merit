from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from merit.testing.sut.dep_collector import (
    DependencyCollectionMode,
    DependencyCollector,
    ImportBinding,
    ImportIndex,
    ModuleAnalyzer,
    ModuleResolver,
    _resolve_from_import,
    collect_dependencies,
)


def test_resolve_from_import_handles_absolute_and_relative_paths():
    absolute = _resolve_from_import(
        node=ast.ImportFrom(module="pkg.tools", names=[], level=0),
        module_name="pkg.module",
        module_file=Path("/repo/pkg/module.py"),
    )
    assert absolute == "pkg.tools"

    relative_in_module = _resolve_from_import(
        node=ast.ImportFrom(module="utils", names=[], level=1),
        module_name="pkg.sub.module",
        module_file=Path("/repo/pkg/sub/module.py"),
    )
    assert relative_in_module == "pkg.sub.utils"

    relative_in_package = _resolve_from_import(
        node=ast.ImportFrom(module="helpers", names=[], level=1),
        module_name="pkg.sub",
        module_file=Path("/repo/pkg/sub/__init__.py"),
    )
    assert relative_in_package == "pkg.sub.helpers"


def test_import_index_captures_module_and_function_scoped_imports():
    source = """
import top.dep as dep
from pkg.deep import thing as alias

def build():
    import inner.mod as local_dep
    return dep, local_dep
"""
    index = ImportIndex(source, "pkg.module", Path("/repo/pkg/module.py"))

    assert index.get_module_level("dep") == ImportBinding(module_name="top.dep")
    assert index.get_module_level("alias") == ImportBinding(module_name="pkg.deep", imported_name="thing")
    assert index.get_function_level("build", "local_dep") == ImportBinding(module_name="inner.mod")
    assert index.local_functions == {"build"}
    assert index.all_module_imports() == {"top.dep", "pkg.deep"}


def test_module_analyzer_follows_local_functions_and_global_imports():
    source = """
import outer.mod as outer_mod
from pkg import unused

def helper():
    import helper.dep as helper_dep
    return helper_dep

def target():
    import direct.dep as direct_dep
    return helper(), outer_mod, direct_dep
"""
    index = ImportIndex(source, "pkg.module", Path("/repo/pkg/module.py"))
    analyzer = ModuleAnalyzer(source, "/repo/pkg/module.py")

    reachable = analyzer.reachable_modules({"target"}, index)

    assert reachable == {"direct.dep", "helper.dep", "outer.mod"}


def test_module_analyzer_all_imports_mode_returns_only_module_level_imports():
    source = """
import top.dep as top_dep
from pkg.deep import thing as alias

def build():
    import local.dep as local_dep
    return top_dep, alias, local_dep
"""
    index = ImportIndex(source, "pkg.module", Path("/repo/pkg/module.py"))
    analyzer = ModuleAnalyzer(source, "/repo/pkg/module.py")

    reachable = analyzer.reachable_modules(None, index)

    assert reachable == {"top.dep", "pkg.deep"}


def test_module_resolver_ignores_stdlib_and_site_packages(monkeypatch: pytest.MonkeyPatch):
    repo_root = Path("/repo")
    resolver = ModuleResolver(repo_root)

    monkeypatch.setattr("merit.testing.sut.dep_collector.importlib.util.find_spec", lambda _: None)
    assert resolver.resolve("unknown.module") is None
    assert resolver.resolve("sys") is None

    site_spec = SimpleNamespace(
        has_location=True, origin="/venv/lib/python3.12/site-packages/pkg/mod.py"
    )
    monkeypatch.setattr(
        "merit.testing.sut.dep_collector.importlib.util.find_spec",
        lambda _: site_spec,
    )
    assert resolver.resolve("external.pkg") is None


def test_module_resolver_resolves_repo_local_module(monkeypatch: pytest.MonkeyPatch):
    repo_root = Path("/repo")
    resolver = ModuleResolver(repo_root)
    local_spec = SimpleNamespace(has_location=True, origin="/repo/pkg/mod.py")

    monkeypatch.setattr(
        "merit.testing.sut.dep_collector.importlib.util.find_spec",
        lambda _: local_spec,
    )

    assert resolver.resolve("pkg.mod") == Path("/repo/pkg/mod.py")


def test_module_resolver_cache_is_instance_local(monkeypatch: pytest.MonkeyPatch):
    repo_root = Path("/repo")
    first = ModuleResolver(repo_root)
    second = ModuleResolver(repo_root)
    local_spec = SimpleNamespace(has_location=True, origin="/repo/pkg/mod.py")
    calls = 0

    def fake_find_spec(module_name: str):
        nonlocal calls
        calls += 1
        assert module_name == "pkg.mod"
        return local_spec

    monkeypatch.setattr(
        "merit.testing.sut.dep_collector.importlib.util.find_spec",
        fake_find_spec,
    )

    assert first.resolve("pkg.mod") == Path("/repo/pkg/mod.py")
    assert first.resolve("pkg.mod") == Path("/repo/pkg/mod.py")
    assert second.resolve("pkg.mod") == Path("/repo/pkg/mod.py")
    assert calls == 2


def test_dependency_collector_module_mode_enqueues_parent_packages(
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = Path("/repo")
    collector = DependencyCollector(repo_root)

    module_files = {
        "pkg": Path("/repo/pkg/__init__.py"),
        "pkg.sub": Path("/repo/pkg/sub/__init__.py"),
        "pkg.sub.mod": Path("/repo/pkg/sub/mod.py"),
        "pkg.sub.dep": Path("/repo/pkg/sub/dep.py"),
    }
    graph = {
        "pkg": set(),
        "pkg.sub": set(),
        "pkg.sub.mod": {ImportBinding("pkg.sub.dep")},
        "pkg.sub.dep": set(),
    }

    def fake_resolve(module_name: str) -> Path | None:
        return module_files.get(module_name)

    class FakeAnalyzer:
        def __init__(self, module_name: str) -> None:
            self.module_name = module_name

        def reachable_bindings(
            self, targets: set[str] | None, index: ImportIndex
        ) -> set[ImportBinding]:
            assert index is not None
            return graph[self.module_name]

    monkeypatch.setattr(collector._resolver, "resolve", fake_resolve)
    monkeypatch.setattr(
        collector,
        "_load",
        lambda file_path, module_name: (
            ImportIndex("", module_name, file_path),
            FakeAnalyzer(module_name),
        ),
    )

    deps = collector.collect(
        seed_module="pkg.sub.mod",
        seed_file=module_files["pkg.sub.mod"],
        mode=DependencyCollectionMode.MODULE,
    )

    assert [dep.module_name for dep in deps] == ["pkg", "pkg.sub", "pkg.sub.dep", "pkg.sub.mod"]


def test_dependency_collector_symbol_mode_uses_seed_symbol_only_once(
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = Path("/repo")
    collector = DependencyCollector(repo_root)

    module_files = {
        "pkg.mod": Path("/repo/pkg/mod.py"),
        "pkg.dep": Path("/repo/pkg/dep.py"),
    }
    graph = {
        "pkg.mod": {ImportBinding("pkg.dep", "dep_entrypoint")},
        "pkg.dep": set(),
    }
    calls: list[tuple[str, set[str] | None]] = []

    class FakeAnalyzer:
        def __init__(self, module_name: str) -> None:
            self.module_name = module_name

        def missing_module_symbols(self, names: set[str]) -> set[str]:
            return set()

        def reachable_bindings(
            self, targets: set[str] | None, index: ImportIndex
        ) -> set[ImportBinding]:
            assert index is not None
            calls.append((self.module_name, targets))
            return graph[self.module_name]

    monkeypatch.setattr(
        collector._resolver, "resolve", lambda module_name: module_files.get(module_name)
    )
    monkeypatch.setattr(
        collector,
        "_load",
        lambda file_path, module_name: (
            ImportIndex("", module_name, file_path),
            FakeAnalyzer(module_name),
        ),
    )

    deps = collector.collect(
        seed_module="pkg.mod",
        seed_file=module_files["pkg.mod"],
        mode=DependencyCollectionMode.SYMBOL,
        seed_symbol="entrypoint",
    )

    assert [dep.module_name for dep in deps] == ["pkg.dep", "pkg.mod"]
    assert calls == [("pkg.mod", {"entrypoint"}), ("pkg.dep", {"dep_entrypoint"})]


def test_dependency_collector_symbol_mode_handles_cycles_and_duplicate_edges(
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = Path("/repo")
    collector = DependencyCollector(repo_root)

    module_files = {
        "pkg.a": Path("/repo/pkg/a.py"),
        "pkg.b": Path("/repo/pkg/b.py"),
        "pkg.c": Path("/repo/pkg/c.py"),
    }
    graph = {
        "pkg.a": {ImportBinding("pkg.b"), ImportBinding("pkg.c")},
        "pkg.b": {ImportBinding("pkg.a"), ImportBinding("pkg.c")},
        "pkg.c": {ImportBinding("pkg.b")},
    }
    calls: list[str] = []

    class FakeAnalyzer:
        def __init__(self, module_name: str) -> None:
            self.module_name = module_name

        def missing_module_symbols(self, names: set[str]) -> set[str]:
            return set()

        def reachable_bindings(
            self, targets: set[str] | None, index: ImportIndex
        ) -> set[ImportBinding]:
            assert index is not None
            calls.append(self.module_name)
            return graph[self.module_name]

    monkeypatch.setattr(
        collector._resolver, "resolve", lambda module_name: module_files.get(module_name)
    )
    monkeypatch.setattr(
        collector,
        "_load",
        lambda file_path, module_name: (
            ImportIndex("", module_name, file_path),
            FakeAnalyzer(module_name),
        ),
    )

    deps = collector.collect(
        seed_module="pkg.a",
        seed_file=module_files["pkg.a"],
        mode=DependencyCollectionMode.SYMBOL,
        seed_symbol="entrypoint",
    )

    assert [dep.module_name for dep in deps] == ["pkg.a", "pkg.b", "pkg.c"]
    assert sorted(set(calls)) == ["pkg.a", "pkg.b", "pkg.c"]


def test_dependency_collector_symbol_mode_falls_back_to_submodule_when_symbol_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = Path("/repo")
    collector = DependencyCollector(repo_root)

    module_files = {
        "pkg.seed": Path("/repo/pkg/seed.py"),
        "pkg": Path("/repo/pkg/__init__.py"),
        "pkg.value": Path("/repo/pkg/value.py"),
    }
    source_by_module = {
        "pkg.seed": "from pkg import value\n\n\ndef entrypoint():\n    return value.VALUE\n",
        "pkg": "SOMETHING = 1\n",
        "pkg.value": "VALUE = 1\n",
    }

    monkeypatch.setattr(
        collector._resolver, "resolve", lambda module_name: module_files.get(module_name)
    )
    monkeypatch.setattr(
        collector,
        "_load",
        lambda file_path, module_name: (
            ImportIndex(source_by_module[module_name], module_name, file_path),
            ModuleAnalyzer(source_by_module[module_name], str(file_path)),
        ),
    )

    deps = collector.collect(
        seed_module="pkg.seed",
        seed_file=module_files["pkg.seed"],
        mode=DependencyCollectionMode.SYMBOL,
        seed_symbol="entrypoint",
    )

    assert [dep.module_name for dep in deps] == ["pkg", "pkg.seed", "pkg.value"]


def test_dependency_collector_load_caches_by_file_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    module_file = repo_root / "mod.py"
    module_file.write_text("import pkg.dep\n", encoding="utf-8")
    collector = DependencyCollector(repo_root)
    read_count = 0
    original_read_text = Path.read_text

    def counted_read_text(self: Path, encoding: str = "utf-8") -> str:
        nonlocal read_count
        if self == module_file:
            read_count += 1
        return original_read_text(self, encoding=encoding)

    monkeypatch.setattr(Path, "read_text", counted_read_text)

    first_index, first_analyzer = collector._load(module_file, "pkg.mod")
    second_index, second_analyzer = collector._load(module_file, "pkg.mod")

    assert read_count == 1
    assert first_index is second_index
    assert first_analyzer is second_analyzer


def test_collect_dependencies_collects_real_repo_local_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    source_dir = repo_root / "pkg"
    source_dir.mkdir(parents=True)
    (source_dir / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "dep.py").write_text("VALUE = 1\n", encoding="utf-8")
    module_file = source_dir / "module.py"
    module_file.write_text(
        "import pkg.dep\n\ndef entrypoint():\n    return pkg.dep.VALUE\n",
        encoding="utf-8",
    )

    def entrypoint():
        return None

    fake_module = SimpleNamespace(__name__="pkg.module", __file__=str(module_file.resolve()))
    monkeypatch.syspath_prepend(str(repo_root))
    monkeypatch.setattr("merit.testing.sut.dep_collector.inspect.getmodule", lambda _: fake_module)

    deps = collect_dependencies(entrypoint, mode="module")

    assert [dep.module_name for dep in deps] == ["pkg", "pkg.dep", "pkg.module"]


def test_collect_dependencies_rejects_invalid_mode_value():
    def entrypoint():
        return None

    with pytest.raises(ValueError):
        collect_dependencies(entrypoint, mode="not-a-mode")


def test_collect_dependencies_requires_owner_module(monkeypatch: pytest.MonkeyPatch):
    def entrypoint():
        return None

    monkeypatch.setattr("merit.testing.sut.dep_collector.inspect.getmodule", lambda _: None)

    with pytest.raises(ValueError):
        collect_dependencies(entrypoint)


def test_collect_dependencies_requires_owner_file(monkeypatch: pytest.MonkeyPatch):
    def entrypoint():
        return None

    fake_module = SimpleNamespace(__name__="pkg.module")
    monkeypatch.setattr("merit.testing.sut.dep_collector.inspect.getmodule", lambda _: fake_module)

    with pytest.raises(ValueError):
        collect_dependencies(entrypoint)


def test_collect_dependencies_fails_when_git_root_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module_file = tmp_path / "pkg" / "module.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("def entrypoint():\n    return None\n", encoding="utf-8")

    def entrypoint():
        return None

    fake_module = SimpleNamespace(__name__="pkg.module", __file__=str(module_file.resolve()))
    monkeypatch.setattr("merit.testing.sut.dep_collector.inspect.getmodule", lambda _: fake_module)

    with pytest.raises(StopIteration):
        collect_dependencies(entrypoint)
