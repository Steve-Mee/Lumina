"""Hybrid quarantine gates for known stub / heuristic paths.

Defaults preserve historical behavior. Strict modes are opt-in via config.
Every active legacy path logs under ``hybrid_quarantine.<id>``.

SIM/PAPER-only bulk strict profile (does not change committed defaults):
- env ``LUMINA_HYBRID_STRICT=1`` (or true/yes/on), or
- ``hybrid_quarantine.apply_strict_in_sim: true``

When that opt-in is active and config ``mode`` is sim/paper, all six gates use the
strict profile. REAL / unknown modes ignore the opt-in (warning logged).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from lumina_core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Inventory IDs (documented in docs/hybrid-quarantine.md)
MULTI_DAY_SIM = "multi_day_sim"
SHADOW_TRACE_VERDICT = "shadow_trace_verdict"
ARCH_PATCH_APPLY = "arch_patch_apply"
KILL_SWITCH_AUTH = "kill_switch_auth"
PLATEAU_TERMINAL_PASSTHROUGH = "plateau_terminal_passthrough"
VLLM_LIFECYCLE = "vllm_lifecycle"

_QUARANTINE_IDS = frozenset(
    {
        MULTI_DAY_SIM,
        SHADOW_TRACE_VERDICT,
        ARCH_PATCH_APPLY,
        KILL_SWITCH_AUTH,
        PLATEAU_TERMINAL_PASSTHROUGH,
        VLLM_LIFECYCLE,
    }
)

_SIM_LIKE_MODES = frozenset({"sim", "paper"})


def _cfg() -> dict[str, Any]:
    try:
        raw = ConfigLoader().config
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _nested(cfg: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = cfg
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default if key == keys[-1] else {})
    return cur


def _truthy_env(name: str) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _runtime_mode(cfg: dict[str, Any] | None = None) -> str:
    data = cfg if cfg is not None else _cfg()
    return str(data.get("mode", "") or "").strip().lower()


def apply_strict_in_sim_requested(cfg: dict[str, Any] | None = None) -> bool:
    """True when env or config requests the SIM/PAPER strict profile (not yet mode-gated)."""
    if _truthy_env("LUMINA_HYBRID_STRICT"):
        return True
    data = cfg if cfg is not None else _cfg()
    return bool(_nested(data, "hybrid_quarantine", "apply_strict_in_sim", default=False))


def sim_strict_profile_active(cfg: dict[str, Any] | None = None) -> bool:
    """True only when opt-in is requested and mode is sim/paper. REAL never auto-strict."""
    data = cfg if cfg is not None else _cfg()
    if not apply_strict_in_sim_requested(data):
        return False
    mode = _runtime_mode(data)
    if mode in _SIM_LIKE_MODES:
        return True
    if mode:
        logger.warning(
            "hybrid_quarantine.apply_strict_in_sim ignored for mode=%s (SIM/PAPER only)",
            mode,
        )
    return False


def log_quarantine(quarantine_id: str, *, strict: bool, detail: str = "") -> None:
    """Structured inventory log for active hybrid stubs."""
    if quarantine_id not in _QUARANTINE_IDS:
        logger.warning("hybrid_quarantine.unknown_id id=%s", quarantine_id)
    logger.info(
        "hybrid_quarantine.%s strict=%s %s",
        quarantine_id,
        strict,
        detail.strip() or "active",
    )


def require_true_backtest() -> bool:
    """When True: multi-day sim refuses RNG/heuristic fitness (fail-closed). Default False."""
    cfg = _cfg()
    if sim_strict_profile_active(cfg):
        return True
    hq = _nested(cfg, "hybrid_quarantine", "require_true_backtest", default=None)
    if hq is not None:
        return bool(hq)
    return bool(_nested(cfg, "evolution", "multi_day_sim", "require_true_backtest", default=False))


def require_trace_verdict() -> bool:
    """When True: shadow risk must derive verdict from decision_fn output. Default False."""
    cfg = _cfg()
    if sim_strict_profile_active(cfg):
        return True
    hq = _nested(cfg, "hybrid_quarantine", "require_trace_verdict", default=None)
    if hq is not None:
        return bool(hq)
    return bool(_nested(cfg, "risk", "shadow", "require_trace_verdict", default=False))


def require_real_patch_apply() -> bool:
    """When True: architecture_meta sandbox refuses pretend deltas. Default False."""
    cfg = _cfg()
    if sim_strict_profile_active(cfg):
        return True
    hq = _nested(cfg, "hybrid_quarantine", "require_real_patch_apply", default=None)
    if hq is not None:
        return bool(hq)
    return bool(_nested(cfg, "architecture_meta", "require_real_patch_apply", default=False))


def require_kill_switch_reset_authorization() -> bool:
    """When True: reset_kill_switch requires non-empty authorization_code. Default False."""
    cfg = _cfg()
    if sim_strict_profile_active(cfg):
        return True
    hq = _nested(cfg, "hybrid_quarantine", "require_reset_authorization", default=None)
    if hq is not None:
        return bool(hq)
    return bool(_nested(cfg, "risk", "kill_switch", "require_reset_authorization", default=False))


def handler_terminal_passthrough() -> bool:
    """When True (default): plateau_handler resolve_terminal returns handled=True placeholder."""
    cfg = _cfg()
    if sim_strict_profile_active(cfg):
        return False
    hq = _nested(cfg, "hybrid_quarantine", "handler_terminal_passthrough", default=None)
    if hq is not None:
        return bool(hq)
    return bool(_nested(cfg, "birth", "plateau", "handler_terminal_passthrough", default=True))


def manage_vllm_lifecycle() -> bool:
    """When True: start_vllm_server must report healthy or fail. Default False (health-check only)."""
    cfg = _cfg()
    if sim_strict_profile_active(cfg):
        return True
    hq = _nested(cfg, "hybrid_quarantine", "manage_lifecycle", default=None)
    if hq is not None:
        return bool(hq)
    return bool(_nested(cfg, "vllm", "manage_lifecycle", default=False))


def inventory() -> dict[str, bool]:
    """Current gate states for docs / CI inventory."""
    return {
        MULTI_DAY_SIM: require_true_backtest(),
        SHADOW_TRACE_VERDICT: require_trace_verdict(),
        ARCH_PATCH_APPLY: require_real_patch_apply(),
        KILL_SWITCH_AUTH: require_kill_switch_reset_authorization(),
        PLATEAU_TERMINAL_PASSTHROUGH: handler_terminal_passthrough(),
        VLLM_LIFECYCLE: manage_vllm_lifecycle(),
    }


__all__ = [
    "MULTI_DAY_SIM",
    "SHADOW_TRACE_VERDICT",
    "ARCH_PATCH_APPLY",
    "KILL_SWITCH_AUTH",
    "PLATEAU_TERMINAL_PASSTHROUGH",
    "VLLM_LIFECYCLE",
    "log_quarantine",
    "apply_strict_in_sim_requested",
    "sim_strict_profile_active",
    "require_true_backtest",
    "require_trace_verdict",
    "require_real_patch_apply",
    "require_kill_switch_reset_authorization",
    "handler_terminal_passthrough",
    "manage_vllm_lifecycle",
    "inventory",
]
