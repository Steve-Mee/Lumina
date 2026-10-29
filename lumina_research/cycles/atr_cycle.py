"""Action-5 ES ATR/points grid. MES is the D13 control. NQ closed. No 16/8."""

from __future__ import annotations

from pathlib import Path

from lumina_research.cycles.catalog import HypothesisSpec, catalog
from lumina_research.cycles.nq_lock import assert_nq_templates_closed
from lumina_research.cycles.positive_control import BREAKOUT_MIDPOINT_ATR, FADE_MIDPOINT_ATR
from lumina_research.cycles.runner import ResearchCycleResult, run_research_cycles
from lumina_research.proof.runner import DEFAULT_REPORTS

_REPO = Path(__file__).resolve().parents[2]
ATR_CYCLES_STEM = "phase5_p2_atr_es"
ATR_RESULTS_NAME = "phase5_p2_atr_es_results.md"
ATR_SEAL_NAME = "phase5_p2_atr_es_holdout_seal.json"
ATR_TIME_STOP = 2000
# Team 17:34: these four stay killed. DSR floor is not relaxed. A lower-turnover
# version is a new pre-register (fresh trial), not a rerun of this grid.
DSR_ONLY_KILLS: frozenset[str] = frozenset(
    {
        "p2a-or-bo-es",
        "p2a-rm-es",
        "p2a-pb-es",
        "p2a-gap-es",
    }
)

_GRID: tuple[tuple[str, str, str, str, int, float, float | None, float | None, bool], ...] = (
    ("p2a-mr-es", "mean_reversion", "mean_reversion", "fade", 60, 1.5, 1.0, 1.2, False),
    ("p2a-vwap-es", "vwap_distance", "vwap_distance", "fade", 60, 1.5, 1.0, 1.2, False),
    ("p2a-tod-es", "time_of_day_inventory", "time_of_day", "fade", 30, 0.0, 1.0, 1.2, False),
    ("p2a-or-fade-es", "opening_range_fade", "opening_range", "fade", 30, 0.0, 1.0, 1.2, False),
    ("p2a-or-bo-es", "opening_range_breakout", "opening_range", "breakout", 30, 0.0, 1.8, 0.9, False),
    ("p2a-rm-es", "regime_momentum", "regime_momentum", "follow", 120, 0.40, 1.8, 0.9, False),
    ("p2a-rc-es", "range_compression", "range_compression", "breakout", 60, 0.25, 1.8, 0.9, False),
    ("p2a-vx-es", "volatility_expansion", "volatility_expansion", "breakout", 60, 0.75, 1.8, 0.9, False),
    ("p2a-pb-es", "trend_pullback", "trend_pullback", "follow", 120, 0.0, 1.8, 0.9, False),
    ("p2a-gap-es", "overnight_gap", "overnight_gap", "fade", 1, 8.0, None, None, True),
)


def atr_es_specs() -> tuple[HypothesisSpec, ...]:
    by_template = {item.template_id: item for item in catalog()}
    out: list[HypothesisSpec] = []
    for config_id, template_id, family, mode, lookback, threshold, target_atr, stop_atr, no_br in _GRID:
        source = by_template[template_id]
        out.append(
            HypothesisSpec(
                config_id=config_id,
                template_id=template_id,
                family=family,
                instrument="ES",
                lookback=lookback,
                threshold=threshold,
                mode=mode,
                target_ticks=1,
                stop_ticks=1,
                rationale=source.rationale,
                session_filter="rth",
                time_stop_bars=ATR_TIME_STOP,
                session_end_flatten=True,
                has_fit_step=False,
                target_atr=target_atr,
                stop_atr=stop_atr,
                atr_n_sessions=14,
                disable_brackets=no_br,
            )
        )
    if len(out) != 10:
        raise RuntimeError("ATR ES grid must be 10 pre-registered configs")
    if any(item.instrument != "ES" for item in out):
        raise RuntimeError("ATR grid is ES only")
    assert_nq_templates_closed(item.instrument for item in out)
    fade_t, fade_s = FADE_MIDPOINT_ATR
    bo_t, bo_s = BREAKOUT_MIDPOINT_ATR
    fade = {item.config_id for item in out if item.target_atr == fade_t and item.stop_atr == fade_s}
    breakout = {item.config_id for item in out if item.target_atr == bo_t and item.stop_atr == bo_s}
    if not fade or not breakout:
        raise RuntimeError("ATR grid must keep pre-registered fade 1.0/1.2 and breakout 1.8/0.9 midpoints")
    if not DSR_ONLY_KILLS <= {item.config_id for item in out}:
        raise RuntimeError("DSR-only kills must remain in the frozen grid")
    return tuple(out)


def run_atr_es_cycle(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    data_dir: Path | None = None,
    repo_root: Path | None = None,
) -> ResearchCycleResult:
    root = repo_root if repo_root is not None else _REPO
    return run_research_cycles(
        work_dir=work_dir,
        report_dir=report_dir,
        evolution_log_dir=None,
        data_dir=data_dir,
        repo_root=root,
        specs=atr_es_specs(),
        cycles_stem=ATR_CYCLES_STEM,
        results_name=ATR_RESULTS_NAME,
        allowed_instruments=frozenset({"ES", "MES"}),
        control_per_instrument=True,
        write_sidecars=False,
        seal_filename=ATR_SEAL_NAME,
        require_known_files=True,
        control_geometry_mode="atr",
        required_control_roots=frozenset({"MES", "ES"}),
        control_block_seeds=(),
    )
