"""Runtime role SSOT — champion never reads challenger stores (K1)."""

from __future__ import annotations

from pathlib import Path

CHAMPION = "champion"
CHALLENGER = "challenger"
ROLES: frozenset[str] = frozenset({CHAMPION, CHALLENGER})
REAL_LIKE = frozenset({"real", "live", "prod", "production", "sim_real_guard"})


def normalize_runtime_role(role: str | None) -> str:
    raw = str(role or CHAMPION).strip().lower()
    return raw if raw in ROLES else CHAMPION


def is_real_like_capital(mode: str | None) -> bool:
    return str(mode or "").strip().lower() in REAL_LIKE


def applied_root_for_role(journal_root: str | Path, role: str | None) -> Path:
    root = Path(journal_root)
    return root / "applied" / normalize_runtime_role(role)
