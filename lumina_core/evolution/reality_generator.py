"""Stress-scenario suites for multi-reality SIM training.

Builds parallel ``nightly_report``-shaped payloads so :class:`MultiDaySimRunner`
can score DNA / weights under black-swan, flash-crash, regime-shift, and
liquidity stress without touching live order flow.

**Fase 3 (OHLC):** :func:`stress_simulator_ohlc` past historische tick/OHLC-rijen per
``_reality_id`` aan (returns + spread). Alleen actief wanneer echte data geladen is
(DNA) of wanneer ``neuroevolution.use_ohlc_stress_rollouts`` true is (meerdere
PPO-rollouts; kostbaar).

Voor PPO-neuroevolutie: :func:`aggregate_ppo_eval_worst_reality` (metric-stress) of
meerdere rollouts op :func:`stress_simulator_ohlc` (Fase 3, zie ``use_ohlc_stress_rollouts``).
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

# (name, pnl_mult, drawdown_mult, sharpe_mult) — drawdown_mult scales stress magnitude.
_STRESS_PRESETS: list[tuple[str, float, float, float]] = [
    ("baseline", 1.0, 1.0, 1.0),
    ("black_swan_1987_style", -2.8, 4.5, -1.4),
    ("flash_crash_2010_style", -2.2, 3.6, -1.0),
    ("covid_liquidity_gap", -1.9, 3.2, -0.85),
    ("regime_shift_bear", -1.1, 2.0, -0.55),
    ("regime_shift_chop", 0.25, 1.65, -0.22),
    ("liquidity_crash", -1.35, 2.75, -0.48),
    ("high_vol_squeeze", -0.55, 2.35, 0.08),
    ("gap_and_go_against", -1.6, 2.15, -0.62),
    ("trend_exhaustion_fade", 0.15, 1.55, -0.28),
    ("correlation_breakdown", -0.95, 2.25, -0.32),
    ("margin_spiral_stress", -1.15, 2.95, -0.38),
    ("microstructure_noise", 0.08, 1.7, -0.12),
    ("carry_unwind", -1.45, 2.5, -0.58),
    ("sovereign_shock_proxy", -1.25, 2.4, -0.45),
]


def _stable_int(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)


def stress_simulator_ohlc(
    bars: list[dict[str, Any]],
    reality_id: int,
    *,
    stress_seed: str = "ohlc",
) -> list[dict[str, Any]]:
    """Fase 3: transformeer OHLC-rij zodat returns en intrabar-spread harder/zwakker worden.

    Zelfde preset-index als :func:`build_parallel_reports` (``reality_id`` mod presets).
    Deterministisch o.b.v. ``reality_id`` + ``stress_seed``. Gebruikt
    :func:`simulator_data_support.normalize_simulator_bars` voor geldige prijzen.

    Wordt gebruikt door :class:`MultiDaySimRunner` (``real_ticks``) en optioneel door
    neuro- PPO wanneer ``use_ohlc_stress_rollouts`` true is.
    """
    from .simulator_data_support import normalize_simulator_bars

    base = normalize_simulator_bars(bars)
    if len(base) < 2:
        return [dict(b) for b in base]

    name, pm, dm, sm = _STRESS_PRESETS[int(reality_id) % len(_STRESS_PRESETS)]
    rng = random.Random(_stable_int(f"{stress_seed}|{name}|ohlc|{reality_id}"))
    # Amplify close-to-close returns; widen high-low when drawdown mult is large
    ret_amp = 1.0 + 0.14 * (abs(float(pm)) * 0.1) * (-0.9 if float(pm) < 0 else 0.25)
    ret_amp = max(0.5, min(1.9, ret_amp + rng.uniform(-0.04, 0.04)))
    span_amp = 1.0 + 0.12 * max(0.0, float(abs(dm)) - 1.0) + 0.08 * min(1.0, abs(float(sm)))
    span_amp = max(0.45, min(2.3, span_amp + rng.uniform(-0.02, 0.02)))

    out: list[dict[str, Any]] = []
    p0 = float(base[0].get("close", 0.0) or 0.0)
    if p0 <= 0.0:
        return [dict(b) for b in base]
    o0 = float(base[0].get("open", p0) or p0)
    h0 = float(base[0].get("high", max(o0, p0)) or p0)
    l0 = float(base[0].get("low", min(o0, p0)) or p0)
    first = dict(base[0])
    first["open"], first["high"], first["low"] = o0, h0, l0
    first["close"] = p0
    first["last"] = p0
    out.append(first)

    c_prev = p0
    for i in range(1, len(base)):
        row = base[i]
        c_raw = float(row.get("close", c_prev) or c_prev)
        o_raw = float(row.get("open", c_prev) or c_prev)
        h_raw = float(row.get("high", max(o_raw, c_raw)) or c_raw)
        l_raw = float(row.get("low", min(o_raw, c_raw)) or c_raw)
        r = (c_raw / max(c_prev, 1e-9)) - 1.0
        r2 = r * ret_amp
        c_new = max(1e-6, c_prev * (1.0 + r2))
        half = max(0.5 * (h_raw - l_raw) * span_amp, c_new * 1e-7)
        o_new = max(1e-6, c_prev * (1.0 + 0.35 * r2))
        o_new = min(o_new, max(c_prev, c_new) * 1.0005)
        h_new = max(o_new, c_new) + half
        l_new = min(o_new, c_new) - half * 0.9
        l_new = max(1e-6, l_new)
        h_new = max(h_new, c_new, o_new, l_new)
        r_out = dict(row)
        r_out["open"] = o_new
        r_out["close"] = c_new
        r_out["last"] = c_new
        r_out["high"] = h_new
        r_out["low"] = l_new
        out.append(r_out)
        c_prev = c_new
    return out


def aggregate_ppo_eval_worst_reality(
    base_eval: dict[str, Any],
    parallel_realities: int,
    *,
    stress_seed: str = "lumina_neuro_ppo",
) -> dict[str, Any]:
    """Apply the same stress presets as :func:`build_parallel_reports` to one PPO rollout.

    Eén rollout per kandidaat; daarna N synthetische stress-varianten op de
    return-metrics (zelfde multipliers + jitter als multi-reality DNA). De
    terugkeerwaarde is de **slechtste** realiteit o.b.v. ``backtest_fitness``
    (min, conservatief), vergelijkbaar met :meth:`MultiDaySimRunner._aggregate_multi_reality`.

    Geen extra ``evaluate_policy_zip_rollouts``-aanroepen: alleen
    nacht-CPU-besparend transformeren op reeds berekende metrics.
    """
    if not base_eval or not bool(base_eval.get("ok", False)):
        return dict(base_eval) if base_eval is not None else {"ok": False, "backtest_fitness": float("-inf")}

    n = max(1, min(50, int(parallel_realities)))
    if n < 2:
        return dict(base_eval)

    stressed: list[dict[str, Any]] = []
    for i in range(n):
        name, pm, dm, sm = _STRESS_PRESETS[i % len(_STRESS_PRESETS)]
        rng = random.Random(_stable_int(f"{stress_seed}|{name}|{i}"))
        jitter = 1.0 + rng.uniform(-0.02, 0.02)
        e = dict(base_eval)
        bt = float(base_eval.get("backtest_fitness", 0.0) or 0.0) * pm * sm * jitter
        sr = float(
            base_eval.get("shadow_total_training_reward", base_eval.get("shadow_total_reward", 0.0)) or 0.0
        ) * pm * sm * jitter
        inv_dd = 1.0 / max(float(dm), 0.25)
        se = float(base_eval.get("shadow_equity_delta", 0.0) or 0.0) * inv_dd * jitter
        bte = float(base_eval.get("backtest_equity_delta", 0.0) or 0.0) * inv_dd * jitter
        e["backtest_fitness"] = float(bt)
        e["shadow_total_training_reward"] = float(sr)
        e["shadow_equity_delta"] = float(se)
        e["backtest_equity_delta"] = float(bte)
        e["_reality_id"] = i
        e["_reality_name"] = name
        stressed.append(e)

    worst = min(stressed, key=lambda row: float(row.get("backtest_fitness", float("-inf")) or float("-inf")))
    return dict(worst)


def build_parallel_reports(
    base: dict[str, Any],
    count: int,
    *,
    seed: str = "lumina_multi_reality",
) -> list[dict[str, Any]]:
    """Return ``count`` stressed copies of ``base`` for parallel universe SIM.

    Cycles through historical / synthetic stress presets and adds a tiny
    deterministic jitter so seeds diverge even when presets repeat.
    """
    n = max(1, int(count))
    out: list[dict[str, Any]] = []
    base_eq = max(1.0, float(base.get("account_equity", 50_000.0) or 50_000.0))

    for i in range(n):
        name, pm, dm, sm = _STRESS_PRESETS[i % len(_STRESS_PRESETS)]
        rng = random.Random(_stable_int(f"{seed}|{name}|{i}"))
        jitter = 1.0 + rng.uniform(-0.02, 0.02)

        report = dict(base)
        pnl = float(base.get("net_pnl", 0.0) or 0.0) * pm * jitter
        dd = abs(float(base.get("max_drawdown", 0.0) or 0.0)) * dm * jitter
        sharpe = float(base.get("sharpe", 0.0) or 0.0) * sm * jitter

        report["net_pnl"] = pnl
        report["max_drawdown"] = dd
        report["sharpe"] = sharpe
        report.setdefault("account_equity", base_eq * (1.0 + rng.uniform(-0.01, 0.01)))

        report["_reality_id"] = i
        report["_reality_name"] = name
        out.append(report)

    return out
