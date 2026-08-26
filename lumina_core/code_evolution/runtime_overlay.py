"""OverlayPort — load applied store by runtime_role only (K1, K3, K15)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.code_evolution.operators import PARAMETER_CATALOG
from lumina_core.code_evolution.runtime_role import (
    CHAMPION,
    CHALLENGER,
    applied_root_for_role,
    normalize_runtime_role,
)
from lumina_core.code_evolution.snippet_eval import evaluate_snippet_sandbox, snippet_ast_forbidden

PARAMS_FILE = "params.json"


@dataclass(frozen=True, slots=True)
class OverlaySnapshot:
    role: str
    active: bool
    params: dict[str, float]
    confluence_nudge: float
    loaded_from: str
    schema_ledger: str
    fail_reasons: tuple[str, ...] = ()
    requires_org_cols: bool = False


def empty_overlay(role: str | None = None) -> OverlaySnapshot:
    r = normalize_runtime_role(role)
    return OverlaySnapshot(
        role=r,
        active=False,
        params={},
        confluence_nudge=0.0,
        loaded_from="",
        schema_ledger="",
        fail_reasons=("empty",),
    )


def _load_params(store: Path) -> dict[str, float]:
    path = store / PARAMS_FILE
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, val in raw.items():
        if key not in PARAMETER_CATALOG:
            continue
        try:
            out[str(key)] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def _eval_store_snippets(store: Path) -> tuple[float, list[str]]:
    reasons: list[str] = []
    nudge = 0.0
    for sub in ("snippets", "indicators"):
        folder = store / sub
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.py")):
            try:
                code = path.read_text(encoding="utf-8")
            except OSError as exc:
                reasons.append(f"read_failed:{path.name}")
                _ = exc
                continue
            ast_bad = snippet_ast_forbidden(code)
            if ast_bad:
                reasons.extend(ast_bad)
                continue
            evaluated = evaluate_snippet_sandbox(
                proposal_id=path.stem[:80],
                code=code,
                operator=(
                    "add_simple_indicator" if sub == "indicators" else "strategy_snippet_adjust"
                ),
            )
            if not evaluated.get("ok"):
                reasons.extend(str(v) for v in evaluated.get("violations") or ["sandbox_failed"])
                continue
            nudge += float(evaluated.get("nudge") or 0.0)
    return max(-0.05, min(0.05, nudge)), reasons


def load_overlay(
    *,
    journal_root: Path | str,
    role: str | None,
    schema_ledger_expected: str = "",
    schema_ledger_loaded: str = "",
    requires_org_cols: bool = False,
    store_path: Path | str | None = None,
) -> OverlaySnapshot:
    """Champion reads champion store only. Challenger files never leak (K1)."""
    resolved = normalize_runtime_role(role)
    store = Path(store_path) if store_path is not None else Path(applied_root_for_role(journal_root, resolved))
    if requires_org_cols and str(schema_ledger_expected or "") != str(schema_ledger_loaded or ""):
        return OverlaySnapshot(
            role=resolved,
            active=False,
            params={},
            confluence_nudge=0.0,
            loaded_from=str(store),
            schema_ledger=str(schema_ledger_loaded or ""),
            fail_reasons=("schema_ledger_mismatch",),
            requires_org_cols=True,
        )
    params = _load_params(store)
    nudge, snip_reasons = _eval_store_snippets(store)
    if snip_reasons:
        return OverlaySnapshot(
            role=resolved,
            active=False,
            params={},
            confluence_nudge=0.0,
            loaded_from=str(store),
            schema_ledger=str(schema_ledger_loaded or ""),
            fail_reasons=tuple(snip_reasons),
            requires_org_cols=requires_org_cols,
        )
    active = bool(params) or abs(nudge) > 1e-12
    return OverlaySnapshot(
        role=resolved,
        active=active,
        params=params,
        confluence_nudge=nudge,
        loaded_from=str(store),
        schema_ledger=str(schema_ledger_loaded or ""),
        fail_reasons=() if active else ("empty",),
        requires_org_cols=requires_org_cols,
    )


def effective_min_confluence(base: float, overlay: OverlaySnapshot | None) -> float:
    if overlay is None or not overlay.active:
        return float(base)
    if overlay.role not in (CHAMPION, CHALLENGER):
        return float(base)
    raw = overlay.params.get("confluence_threshold")
    if raw is None:
        value = float(base)
    else:
        value = float(raw)
    value = value + float(overlay.confluence_nudge)
    return max(0.0, min(1.0, value))


def overlay_from_engine(engine: Any) -> OverlaySnapshot:
    snap = getattr(engine, "runtime_overlay", None)
    if isinstance(snap, OverlaySnapshot):
        return snap
    return empty_overlay(CHAMPION)


def load_champion_from_pointer(
    workspace: Path | str,
    *,
    journal_root: Path | str,
    schema_ledger_expected: str = "",
    schema_ledger_loaded: str = "",
    requires_org_cols: bool = False,
) -> OverlaySnapshot:
    """Champion OverlayPort follows CHAMPION.json — never applied/challenger (K1/K10)."""
    from lumina_core.evolution.artifacts import bundle_dir, read_pointer

    ptr = read_pointer(workspace, CHAMPION)
    artifact_id = str(ptr.get("artifact_id") or "").strip()
    if not artifact_id:
        return empty_overlay(CHAMPION)
    store = bundle_dir(workspace, artifact_id) / "overlay"
    if not store.is_dir():
        return empty_overlay(CHAMPION)
    return load_overlay(
        journal_root=journal_root,
        role=CHAMPION,
        schema_ledger_expected=schema_ledger_expected,
        schema_ledger_loaded=schema_ledger_loaded,
        requires_org_cols=requires_org_cols,
        store_path=store,
    )


def bind_overlay_to_engine(
    engine: Any,
    *,
    workspace: Path | str,
    journal_root: Path | str | None = None,
    role: str | None = None,
) -> OverlaySnapshot:
    """Attach OverlaySnapshot. Default champion is empty unless a signed pointer exists."""
    resolved = normalize_runtime_role(role if role is not None else getattr(engine, "runtime_role", None))
    root = Path(journal_root) if journal_root is not None else Path(workspace) / "state" / "code_evolution"
    if resolved == CHALLENGER:
        snap = load_overlay(journal_root=root, role=CHALLENGER)
    else:
        snap = load_champion_from_pointer(workspace, journal_root=root)
    engine.runtime_role = resolved
    engine.runtime_overlay = snap
    return snap
