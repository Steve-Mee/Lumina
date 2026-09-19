"""Read-only Birth π* pin. Awakening never loads or writes the canonical zip in place."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_exit_policy_export import (
    PI_STAR_META_NAME,
    PI_STAR_ZIP_NAME,
    file_sha256,
    resolve_pi_star_path,
)

PIN_DIR_REL = Path("state") / "lumina_birth_freeze"
FROZEN_NAMES = frozenset({PI_STAR_ZIP_NAME, PI_STAR_META_NAME})


def pin_dir(workspace_root: Path) -> Path:
    return Path(workspace_root) / PIN_DIR_REL


def refuse_birth_pi_star_write(path: Path | str) -> None:
    name = Path(path).name.lower()
    if name in {n.lower() for n in FROZEN_NAMES}:
        raise RuntimeError(f"refused write to frozen Birth artefact: {path}")


def freeze_rel_key(workspace_root: Path, path: Path) -> str:
    root = Path(workspace_root).resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return Path(path).name


def pin_birth_pi_star(workspace_root: Path) -> Path:
    """Copy canonical π* into the pin dir once. Never overwrite an existing pin.

    Refuses to pin a zip whose sha256 disagrees with a remembered freeze fingerprint.
    """
    root = Path(workspace_root)
    dest_dir = pin_dir(root)
    dest_zip = dest_dir / PI_STAR_ZIP_NAME
    dest_dir.mkdir(parents=True, exist_ok=True)
    remembered = _read_remembered_sha(root)
    src = resolve_pi_star_path(root)
    if dest_zip.is_file() and dest_zip.stat().st_size > 0:
        return dest_zip
    if not src.is_file() or src.stat().st_size <= 0:
        raise FileNotFoundError(f"birth_exit_pi_star_missing path={src}")
    actual = file_sha256(src)
    if remembered and actual != remembered:
        return dest_zip
    shutil.copy2(src, dest_zip)
    meta = src.with_name(PI_STAR_META_NAME)
    if meta.is_file():
        shutil.copy2(meta, dest_dir / PI_STAR_META_NAME)
    (dest_dir / "sha256.txt").write_text(actual + "\n", encoding="utf-8")
    return dest_zip


def remember_fingerprint_sha(workspace_root: Path, fingerprint: dict[str, Any] | None) -> None:
    sha = expected_zip_sha_from_fingerprint(fingerprint)
    if not sha:
        return
    dest_dir = pin_dir(workspace_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "sha256.txt"
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        return
    path.write_text(sha + "\n", encoding="utf-8")


def _read_remembered_sha(workspace_root: Path) -> str | None:
    path = pin_dir(workspace_root) / "sha256.txt"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text if len(text) == 64 else None


def restore_birth_pi_star_from_pin(workspace_root: Path) -> bool:
    """Rewrite canonical π* from pin if pin exists. Returns True if restored."""
    root = Path(workspace_root)
    pinned = pin_dir(root) / PI_STAR_ZIP_NAME
    if not pinned.is_file() or pinned.stat().st_size <= 0:
        return False
    dest = resolve_pi_star_path(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".zip.restore")
    shutil.copy2(pinned, tmp)
    tmp.replace(dest)
    pinned_meta = pin_dir(root) / PI_STAR_META_NAME
    if pinned_meta.is_file():
        meta_dest = dest.with_name(PI_STAR_META_NAME)
        meta_tmp = meta_dest.with_suffix(".json.restore")
        shutil.copy2(pinned_meta, meta_tmp)
        meta_tmp.replace(meta_dest)
    return True


def copy_for_load(src: Path) -> Path:
    """Temp copy so PPO.load cannot mutate the freeze original."""
    if not src.is_file() or src.stat().st_size <= 0:
        raise FileNotFoundError(str(src))
    tmp = Path(tempfile.mkdtemp(prefix="lumina_pi_star_load_")) / src.name
    shutil.copy2(src, tmp)
    return tmp


def expected_zip_sha_from_fingerprint(fingerprint: dict[str, Any] | None) -> str | None:
    if not fingerprint:
        return None
    for key, val in fingerprint.items():
        text = str(key).replace("\\", "/").lower()
        if text.endswith("/" + PI_STAR_ZIP_NAME) or text.endswith(PI_STAR_ZIP_NAME):
            sha = str(val or "").strip()
            if len(sha) == 64:
                return sha
    return None
