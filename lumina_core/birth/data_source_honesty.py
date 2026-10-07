"""Fail-closed tape honesty: SYNTHETIC ≡ LIVE physics, never SYNTHETIC ≡ REAL certificate.

Certified cache schema is not a live-tape certificate. prefer_real_data_only means
refuse Fabric miss / refuse toy generate_synthetic_ticks — not pct=100.
"""

from __future__ import annotations

from typing import Any

REAL_SOURCE_ALLOWLIST = frozenset(
    {
        "real",
        "real_nt",
        "real_fabric",
        "nt8",
        "ninja",
    }
)
SYNTHETIC_SOURCE_BLOCKLIST = frozenset(
    {
        "synthetic_cloud_fixture",
        "synthetic",
        "cloud_fixture",
        "practice",
        "sim",
        "fixture",
    }
)


class DataSourceHonestyError(ValueError):
    """Reported real_data_pct does not match tick sources."""


def source_is_real(source: str) -> bool:
    s = str(source or "").strip().lower()
    if not s:
        return False
    if s in SYNTHETIC_SOURCE_BLOCKLIST or s.startswith("synthetic"):
        return False
    return s in REAL_SOURCE_ALLOWLIST


def resolved_tick_source(row: dict[str, Any], *, default_if_empty: str) -> str:
    existing = str(row.get("source") or "").strip()
    if existing:
        return existing
    return str(default_if_empty or "")


def tape_source_label(ticks: list[dict[str, Any]] | None) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for tick in ticks or []:
        s = str(tick.get("source") or "").strip().lower()
        if not s or s in seen:
            continue
        seen.add(s)
        labels.append(s)
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return "mixed"


def real_data_percentage(ticks: list[dict[str, Any]] | None) -> float:
    if not ticks:
        return 0.0
    n = len(ticks)
    real_count = sum(1 for tick in ticks if source_is_real(str(tick.get("source") or "")))
    pct = 100.0 * float(real_count) / float(n)
    if real_count < n and pct >= 100.0:
        return 99.999
    return pct


def host_real_data_pct(
    ticks: list[dict[str, Any]] | None,
    *,
    prefer_real_data_only: bool = False,
    certified_cache: bool = False,
    manifest_pct: float | None = None,
) -> float:
    """Ticks win. prefer_real / certified cache / manifest cannot stamp 100."""
    _ = prefer_real_data_only, certified_cache, manifest_pct
    return real_data_percentage(ticks)


def bind_host_real_data_pct(host: Any, ticks: list[dict[str, Any]] | None) -> float:
    pct = real_data_percentage(ticks)
    host._real_data_pct = pct
    manifest = getattr(host, "_data_manifest", None)
    if isinstance(manifest, dict):
        manifest["real_data_pct"] = pct
    return pct


def assert_pct_matches_ticks(pct: float, ticks: list[dict[str, Any]] | None) -> None:
    honest = real_data_percentage(ticks)
    reported = float(pct)
    if abs(reported - honest) > 0.05:
        raise DataSourceHonestyError(
            f"real_data_pct={reported} disagrees with ticks honest={honest}"
        )
    if reported >= 95.0 and honest < 95.0:
        raise DataSourceHonestyError(
            f"real_data_pct={reported} >= 95 but ticks honest={honest} < 95"
        )


def real_historical_tape_reason(
    ticks: list[dict[str, Any]] | None = None,
    *,
    real_data_pct: Any | None = None,
    source: str | None = None,
) -> str | None:
    """None only when every examined tick is allowlisted historical market data.

    Ticks win over a manifest stamp. No ticks and no stamp is "no evidence"
    (receipt-only unit hosts). A present stamp below 100% real is a refusal.
    """
    if ticks is not None:
        if not ticks:
            return "real_historical_tape_empty"
        reasons = synthetic_source_reasons(ticks)
        if reasons:
            return reasons[0]
        pct = real_data_percentage(ticks)
        if pct < 100.0 - 1e-6:
            return f"real_data_pct={pct:.2f}<100"
        return None
    if source is not None and str(source).strip() and not source_is_real(str(source)):
        return f"synthetic_tape:{source}"
    if real_data_pct is not None:
        try:
            pct = float(real_data_pct)
        except (TypeError, ValueError):
            return "real_data_pct_unreadable"
        if pct < 100.0 - 1e-6:
            return f"real_data_pct={pct:.2f}<100"
    return None


def synthetic_source_reasons(ticks: list[dict[str, Any]] | None) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for tick in ticks or []:
        raw = str(tick.get("source") or "").strip().lower()
        if source_is_real(raw):
            continue
        label = raw or "empty"
        reason = f"synthetic_source:{label}"
        if reason in seen:
            continue
        seen.add(reason)
        reasons.append(reason)
    return reasons


__all__ = [
    "DataSourceHonestyError",
    "REAL_SOURCE_ALLOWLIST",
    "SYNTHETIC_SOURCE_BLOCKLIST",
    "assert_pct_matches_ticks",
    "bind_host_real_data_pct",
    "host_real_data_pct",
    "real_data_percentage",
    "real_historical_tape_reason",
    "resolved_tick_source",
    "source_is_real",
    "synthetic_source_reasons",
    "tape_source_label",
]
