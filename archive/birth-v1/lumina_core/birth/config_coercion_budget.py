"""Trade budget resolution for birth v2."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.config_coercion_helpers import _coerce_int

def resolve_trade_budget_cap(raw: dict[str, Any]) -> tuple[int, str]:
    """Resolve global birth trade budget; prefer birth_v2, else first_boot.training_trades."""
    section = raw.get("birth_v2")
    first_boot = raw.get("first_boot")
    fb_trades = 0
    if isinstance(first_boot, dict):
        fb_trades = max(0, _coerce_int(first_boot.get("training_trades"), 0))

    if isinstance(section, dict) and section.get("trade_budget_cap") is not None:
        cap = max(500, _coerce_int(section.get("trade_budget_cap"), 10_000))
        return cap, "birth_v2.trade_budget_cap"

    if fb_trades > 0:
        return max(500, fb_trades), "first_boot.training_trades"

    return 10_000, "default"


def resolve_effective_trade_budget(
    raw: dict[str, Any],
    *,
    target_trades: int | None = None,
) -> tuple[int, str]:
    """Priority: explicit start arg > birth_v2.trade_budget_cap > first_boot.training_trades."""
    if target_trades is not None:
        try:
            from lumina_core.first_boot_ui import normalize_first_boot_training_trades

            normalized = normalize_first_boot_training_trades(int(target_trades))
            if normalized > 0:
                return normalized, "start_arg.target_trades"
        except (TypeError, ValueError):
            pass
    return resolve_trade_budget_cap(raw)


