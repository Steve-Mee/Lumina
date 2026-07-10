"""SSOT helpers for certificate failure diagnostics in birth status payloads."""

from __future__ import annotations

from typing import Any


def _is_rich_oos_metrics(oos: Any) -> bool:
    if not isinstance(oos, dict):
        return False
    for key in ("oos_winrate", "oos_sharpe", "oos_max_drawdown_pct"):
        if oos.get(key) is not None:
            return True
    return False


def merge_certificate_diagnostics(
    progress: dict[str, Any] | None,
    checkpoint: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge progress + checkpoint OOS fields for certificate_failed UI."""
    prog = dict(progress or {})
    ckpt = dict(checkpoint or {}) if isinstance(checkpoint, dict) else {}

    oos = prog.get("oos_metrics")
    if not _is_rich_oos_metrics(oos):
        ckpt_oos = ckpt.get("oos_metrics")
        if _is_rich_oos_metrics(ckpt_oos):
            oos = dict(ckpt_oos)
        elif isinstance(oos, dict):
            oos = dict(oos)
        elif isinstance(ckpt_oos, dict):
            oos = dict(ckpt_oos)
        else:
            oos = {}

    failure_reasons = list(prog.get("failure_reasons") or [])
    if not failure_reasons and isinstance(oos, dict):
        raw = oos.get("failure_reasons")
        if isinstance(raw, list):
            failure_reasons = [str(x) for x in raw]

    runway_phase = str(prog.get("runway_phase", "") or "").strip()
    birth_exit_wr = prog.get("birth_exit_winrate")
    if birth_exit_wr is None:
        birth_exit_wr = ckpt.get("birth_exit_winrate")

    return {
        "oos_metrics": oos if isinstance(oos, dict) else {},
        "failure_reasons": failure_reasons,
        "runway_phase": runway_phase,
        "birth_exit_winrate": birth_exit_wr,
        "checkpoint_oos_metrics": (
            dict(ckpt["oos_metrics"])
            if isinstance(ckpt.get("oos_metrics"), dict)
            else {}
        ),
    }
