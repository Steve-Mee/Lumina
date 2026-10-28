"""Pre-register the first P2 cycle: 12 of 24 variants, chosen before seeing any bars."""

from __future__ import annotations

from pathlib import Path

from lumina_research.cycles.catalog import HypothesisSpec, catalog
from lumina_research.validation.audit import utc_now_iso

FIRST_CYCLE_N_MIN = 10
FIRST_CYCLE_N_MAX = 15
FIRST_CYCLE_CONFIG_IDS: tuple[str, ...] = (
    "mr-mes-10-1.5",
    "vi-mnq-10-0.55",
    "rm-mes-10-0.40",
    "or-mes-5-bo",
    "or-mnq-15-fade",
    "gap-mes-8",
    "vwap-mes-20-1.5",
    "rc-mes-20-0.25",
    "cr-mes-3",
    "tod-mes-15",
    "pb-mnq-20",
    "vx-mes-20",
)
FIRST_CYCLE_RATIONALE = (
    "First P2 cycle is locked to 12 of the 24 pre-filter variants before any NT8 bar is read. "
    "Steve's data order is MES/MNQ 1m first, so each of the 12 registered economic families "
    "contributes its micro contract (MES or MNQ) rather than the ES/NQ duplicate. That keeps "
    "one economically distinct mechanism per family, stays inside the 10-15 band, and avoids "
    "doubling the trial count into full-size contracts before the micro tape is proven. "
    "Lookbacks, thresholds, and 16/8 tick geometry are the catalog values already justified "
    "in the economic rationale fields. Ranking used only those fields. No Sharpe, FAR, PBO, "
    "or bar statistic entered the choice. The 12 unused ES/NQ duplicates remain in the "
    "24-variant pre-filter for a later cycle after the holdout is still untouched."
)


def first_cycle_specs(prefilter: tuple[HypothesisSpec, ...] | None = None) -> tuple[HypothesisSpec, ...]:
    rows = prefilter if prefilter is not None else catalog()
    wanted = set(FIRST_CYCLE_CONFIG_IDS)
    selected = tuple(item for item in rows if item.config_id in wanted)
    if len(selected) != len(FIRST_CYCLE_CONFIG_IDS):
        raise RuntimeError("first-cycle ids must resolve to catalog variants")
    if len(selected) < FIRST_CYCLE_N_MIN or len(selected) > FIRST_CYCLE_N_MAX:
        raise RuntimeError("first cycle must be 10-15 variants")
    templates = {item.template_id for item in selected}
    if len(templates) != 12:
        raise RuntimeError("first cycle must cover all 12 registered families")
    instruments = {item.instrument for item in selected}
    if not instruments.issubset({"MES", "MNQ"}):
        raise RuntimeError("first cycle is MES/MNQ only")
    return selected


def write_first_cycle_preregister(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "phase5_first_cycle_preregister.md"
    specs = first_cycle_specs()
    lines = [
        "# Phase 5 first-cycle pre-registration (before seeing data)",
        "",
        f"- generated_at: `{utc_now_iso()}`",
        f"- prefilter_n: `{len(catalog())}`",
        f"- first_cycle_n: `{len(specs)}`",
        "- holdout: last 9 months locked; never used for this selection",
        "",
        "## Rationale",
        "",
        FIRST_CYCLE_RATIONALE,
        "",
        "## Selected variants",
        "",
        "| config_id | template | instrument | lookback | threshold | mode | target/stop |",
        "|---|---|---|---|---|---|---|",
    ]
    for spec in specs:
        lines.append(
            f"| {spec.config_id} | {spec.template_id} | {spec.instrument} | {spec.lookback} | "
            f"{spec.threshold} | {spec.mode} | {spec.target_ticks}/{spec.stop_ticks} |"
        )
    unused = tuple(item.config_id for item in catalog() if item.config_id not in set(FIRST_CYCLE_CONFIG_IDS))
    lines.extend(["", "## Deferred to a later cycle (still pre-filter, not discarded)", ""])
    for config_id in unused:
        lines.append(f"- `{config_id}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
