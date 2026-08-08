"""Maturation continuum config (strict proofs + runner knobs + TTL)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MaturityConfig:
    strict_exit_proofs: bool = True
    experimental_soft_complete: bool = False
    awakening_min_twin_samples: int = 10
    apprenticeship_min_green_days: int = 5
    playground_require_first_order: bool = True
    proving_require_promotion_or_shadow: bool = True
    # Multi-day SIM for apprenticeship (real evaluate_variants bridge)
    apprenticeship_sim_days: int = 5
    apprenticeship_sim_days_probe: int = 0  # deprecated; ignored when sim_days > 0
    apprenticeship_sim_max_workers: int = 2
    apprenticeship_sim_use_real_market_data: bool = False
    apprenticeship_sim_drawdown_limit_ratio: float = 0.02
    # Telegram advance token TTL (seconds)
    telegram_advance_token_ttl_sec: int = 86400


def load_maturity_config() -> MaturityConfig:
    """Best-effort load from config.yaml maturity section."""
    raw: dict[str, Any] = {}
    try:
        from lumina_core.config_loader import ConfigLoader

        section = ConfigLoader.section("maturity", default={})
        if isinstance(section, dict):
            raw = section
    except Exception:
        raw = {}

    def _bool(key: str, default: bool) -> bool:
        if key not in raw:
            return default
        val = raw.get(key)
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in {"1", "true", "yes", "on"}

    def _int(key: str, default: int, *, lo: int = 0, hi: int = 10_000) -> int:
        try:
            v = int(raw.get(key, default))
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    def _float(key: str, default: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
        try:
            v = float(raw.get(key, default))
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    soft = _bool("experimental_soft_complete", False)
    strict = _bool("strict_exit_proofs", True)
    if soft:
        strict = False

    sim_days = _int("apprenticeship_sim_days", 5, lo=0, hi=7)
    # Back-compat: if only probe set, use it
    if sim_days <= 0:
        sim_days = _int("apprenticeship_sim_days_probe", 0, lo=0, hi=7)

    return MaturityConfig(
        strict_exit_proofs=strict,
        experimental_soft_complete=soft,
        awakening_min_twin_samples=_int("awakening_min_twin_samples", 10, lo=0, hi=10_000),
        apprenticeship_min_green_days=_int("apprenticeship_min_green_days", 5, lo=1, hi=30),
        playground_require_first_order=_bool("playground_require_first_order", True),
        proving_require_promotion_or_shadow=_bool("proving_require_promotion_or_shadow", True),
        apprenticeship_sim_days=sim_days,
        apprenticeship_sim_days_probe=_int("apprenticeship_sim_days_probe", 0, lo=0, hi=7),
        apprenticeship_sim_max_workers=_int("apprenticeship_sim_max_workers", 2, lo=1, hi=4),
        apprenticeship_sim_use_real_market_data=_bool(
            "apprenticeship_sim_use_real_market_data", False
        ),
        apprenticeship_sim_drawdown_limit_ratio=_float(
            "apprenticeship_sim_drawdown_limit_ratio", 0.02, lo=0.001, hi=0.5
        ),
        telegram_advance_token_ttl_sec=_int(
            "telegram_advance_token_ttl_sec", 86400, lo=300, hi=604800
        ),
    )
