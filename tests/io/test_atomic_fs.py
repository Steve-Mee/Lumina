"""Windows-safe atomic replace: retry, leftover tmp cleanup, dest unchanged on failure."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lumina_core.io.atomic_fs import atomic_write_text, atomic_write_text_many, tmp_siblings


@pytest.mark.unit
def test_atomic_write_retries_permissionerror_then_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "payload.json"
    dest.write_text("old", encoding="utf-8")
    calls = {"n": 0}
    real_replace = os.replace

    def _flaky(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            err = PermissionError(13, "Access is denied")
            setattr(err, "winerror", 5)
            raise err
        real_replace(src, dst)

    monkeypatch.setattr("lumina_core.io.atomic_fs.os.replace", _flaky)
    atomic_write_text(dest, "new", retries=8, base_delay_sec=0.01)
    assert dest.read_text(encoding="utf-8") == "new"
    assert calls["n"] == 3
    assert tmp_siblings(dest) == []


@pytest.mark.unit
def test_atomic_write_exhausted_retries_leaves_dest_and_cleans_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "payload.json"
    dest.write_text("old", encoding="utf-8")

    def _always_locked(_src: str | os.PathLike[str], _dst: str | os.PathLike[str]) -> None:
        err = PermissionError(13, "Access is denied")
        setattr(err, "winerror", 5)
        raise err

    monkeypatch.setattr("lumina_core.io.atomic_fs.os.replace", _always_locked)
    with pytest.raises(PermissionError):
        atomic_write_text(dest, "new", retries=3, base_delay_sec=0.01)
    assert dest.read_text(encoding="utf-8") == "old"
    assert tmp_siblings(dest) == []


@pytest.mark.unit
def test_atomic_write_many_stops_before_later_dests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text("keep-a", encoding="utf-8")
    second.write_text("keep-b", encoding="utf-8")
    real_replace = os.replace

    def _fail_second(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(dst).name == "b.json":
            raise PermissionError(13, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr("lumina_core.io.atomic_fs.os.replace", _fail_second)
    with pytest.raises(PermissionError):
        atomic_write_text_many(
            ((first, "new-a"), (second, "new-b")),
            retries=2,
            base_delay_sec=0.01,
        )
    assert first.read_text(encoding="utf-8") == "new-a"
    assert second.read_text(encoding="utf-8") == "keep-b"
    assert tmp_siblings(first) == []
    assert tmp_siblings(second) == []
