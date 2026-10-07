"""Measured phase-status copy for Telegram. Informational only — never a gate."""

from __future__ import annotations

from typing import Any

STATUS_PHASES: frozenset[str] = frozenset(
    {
        "awakening",
        "playground",
        "apprenticeship",
        "proving_ground",
        "real",
    }
)

_LABELS: dict[str, str] = {
    "genesis": "Genesis",
    "birth": "Birth",
    "awakening": "Awakening",
    "playground": "Playground",
    "apprenticeship": "Apprenticeship",
    "proving_ground": "Proving Ground",
    "real": "REAL",
}

_SKIP_LEARNED = frozenset({"exit_proofs", "blockers"})
_PLAYGROUND_N_P_BUCKET = 25


def format_phase_status(
    phase: str,
    *,
    kind: str,
    message: str | None = None,
    learned: dict[str, Any] | None = None,
    missing: list[str] | None = None,
    error: str | None = None,
    stop_reason: str | None = None,
    next_step: str | None = None,
    goal: str | None = None,
) -> tuple[str, str, str]:
    phase_id = str(phase or "").strip().lower()
    label = _LABELS.get(phase_id, phase_id.replace("_", " ").title())
    payload = dict(learned or {})
    gaps = [str(item) for item in (missing or []) if str(item).strip()]
    resolved = _resolve_kind(str(kind or "").strip().lower(), payload, gaps)
    title = _title(label, resolved)
    body_lines: list[str] = []
    if goal:
        body_lines.append("Doel (fase-specificatie):")
        body_lines.append(str(goal))
    if message:
        body_lines.append(str(message))
    measured = _measured_lines(payload)
    if measured:
        body_lines.append("Gemeten:")
        body_lines.extend(measured)
    proofs = [str(item) for item in (payload.get("exit_proofs") or []) if str(item).strip()]
    if resolved == "passed" and proofs:
        body_lines.append("Bewijs:")
        body_lines.extend(proofs)
    elif resolved == "failed" and proofs:
        body_lines.append("Deels binnen")
        body_lines.extend(proofs)
    if gaps:
        body_lines.append("Ontbreekt:")
        body_lines.extend(gaps)
    if error:
        body_lines.append(str(error))
    if stop_reason:
        body_lines.append(str(stop_reason))
    if next_step:
        body_lines.append(str(next_step))
    return title, "\n".join(body_lines).strip(), resolved


def fingerprint_phase_status(
    phase: str,
    *,
    kind: str,
    message: str | None = None,
    learned: dict[str, Any] | None = None,
    missing: list[str] | None = None,
    error: str | None = None,
    stop_reason: str | None = None,
    next_step: str | None = None,
) -> str:
    phase_id = str(phase or "").strip().lower()
    payload = dict(learned or {})
    parts = [
        phase_id,
        str(kind or "").strip().lower(),
        str(error or "").strip(),
        str(stop_reason or "").strip(),
        str(next_step or "").strip(),
    ]
    if phase_id == "playground":
        n_p = _as_int(payload.get("n_p"))
        parts.append(f"n_p_bucket:{n_p // _PLAYGROUND_N_P_BUCKET if n_p is not None else '-'}")
        live_bucket = str(payload.get("liveness_bucket") or "").strip()
        if live_bucket:
            parts.append(f"liveness:{live_bucket}")
    else:
        parts.append("|".join(sorted(str(item) for item in (missing or []) if str(item).strip())))
        parts.append(str(message or "").strip())
        parts.append(_stable_learned(payload))
    return "|".join(parts)


def _resolve_kind(kind: str, learned: dict[str, Any], missing: list[str]) -> str:
    if kind != "passed":
        return kind or "progress"
    if missing:
        return "failed"
    pass_now = learned.get("pass_now")
    if pass_now is False:
        return "failed"
    return "passed"


def _title(label: str, kind: str) -> str:
    if kind == "failed":
        return f"{label} gefaald"
    if kind == "passed":
        return f"{label} gehaald"
    if kind == "started":
        return f"{label} gestart"
    return f"{label} — tussenstand"


def _measured_lines(learned: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, raw in learned.items():
        if key in _SKIP_LEARNED or raw is None:
            continue
        if isinstance(raw, bool):
            lines.append(f"{key}: {str(raw).lower()}")
            continue
        if isinstance(raw, list):
            if not raw:
                continue
            lines.append(f"{key}: {', '.join(str(item) for item in raw)}")
            continue
        lines.append(f"{key}: {raw}")
    return lines


def _stable_learned(learned: dict[str, Any]) -> str:
    items: list[str] = []
    for key in sorted(learned):
        if key in _SKIP_LEARNED:
            continue
        raw = learned[key]
        if raw is None:
            continue
        items.append(f"{key}={raw}")
    return ";".join(items)


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
