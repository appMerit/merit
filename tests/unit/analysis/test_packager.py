from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from merit.analysis.packager import CodebasePackager
from merit.analysis.types import Guardrails, GuardrailViolationError


@pytest.mark.asyncio
async def test_packager_respects_gitignore_and_extra_excludes(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (tmp_path / "keep.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "ignored.py").write_text("print('ignore')\n", encoding="utf-8")
    (tmp_path / "skip.tmp").write_text("skip\n", encoding="utf-8")

    packager = CodebasePackager(
        root_path=tmp_path,
        guardrails=Guardrails(),
        extra_excludes=["*.tmp"],
    )
    zip_path, stats = await packager.create_zip()

    assert stats.file_count == 2  # keep.py + .gitignore

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())

    assert "keep.py" in names
    assert "ignored.py" not in names
    assert "skip.tmp" not in names

    zip_path.unlink()


@pytest.mark.asyncio
async def test_packager_fails_on_file_size_guardrail(tmp_path: Path) -> None:
    big_file = tmp_path / "big.bin"
    big_file.write_bytes(b"x" * 32)

    packager = CodebasePackager(
        root_path=tmp_path,
        guardrails=Guardrails(max_file_bytes=16),
    )

    with pytest.raises(GuardrailViolationError):
        await packager.create_zip()


@pytest.mark.asyncio
async def test_packager_fails_on_max_zip_files_guardrail(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("print('b')\n", encoding="utf-8")

    packager = CodebasePackager(
        root_path=tmp_path,
        guardrails=Guardrails(max_zip_files=1),
    )

    with pytest.raises(GuardrailViolationError, match="max_zip_files"):
        await packager.create_zip()


@pytest.mark.asyncio
async def test_packager_fails_on_zip_size_guardrail(tmp_path: Path) -> None:
    (tmp_path / "large.bin").write_bytes(os.urandom(4096))

    packager = CodebasePackager(
        root_path=tmp_path,
        guardrails=Guardrails(max_zip_bytes=200),
    )

    with pytest.raises(GuardrailViolationError, match="max_zip_bytes"):
        await packager.create_zip()
