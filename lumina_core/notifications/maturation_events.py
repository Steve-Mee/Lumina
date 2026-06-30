"""Maturation ladder milestone events for Telegram (ADR-0028)."""

from __future__ import annotations

from typing import Any

from lumina_core.maturity.maturation_progress import MILESTONE_TO_PHASE, MaturationPhase
from lumina_core.notifications.milestone_events import MilestoneCategory, MilestoneEvent

_PHASE_LABELS: dict[str, str] = {
    MaturationPhase.GENESIS.value: "Genesis",
    MaturationPhase.BIRTH.value: "Birth",
    MaturationPhase.AWAKENING.value: "Awakening",
    MaturationPhase.PLAYGROUND.value: "Playground",
    MaturationPhase.APPRENTICESHIP.value: "Apprenticeship",
    MaturationPhase.PROVING_GROUND.value: "Proving Ground",
    MaturationPhase.REAL.value: "REAL",
}

_TITLES: dict[str, str] = {
    "genesis_contract_signed": "Genesis contract signed",
    "birth_started": "Birth Phase started",
    "birth_certificate_issued": "Birth Certificate issued",
    "evolution_proof_passed": "Evolution Proof passed",
    "deck_unlocked": "Command Deck unlocked",
    "first_sim_order_placed": "First sim order placed",
    "sim_mirror_api_ok": "Sim mirror API connected",
    "sim_real_guard_stable": "SIM stability GREEN",
    "shadow_validation_passed": "Shadow validation passed",
    "promotion_gate_passed": "Promotion gate passed",
    "human_real_approval": "Operator REAL approval",
    "real_trading_live": "REAL trading live",
}


def maturation_milestone_event(
    milestone_id: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> MilestoneEvent:
    mid = str(milestone_id or "").strip()
    meta = dict(metadata or {})
    phase = MILESTONE_TO_PHASE.get(mid, MaturationPhase.GENESIS)
    phase_label = _PHASE_LABELS.get(phase.value, phase.value)
    title = _TITLES.get(mid, mid.replace("_", " ").title())

    summary = _build_summary(mid, phase_label, meta)
    context = _build_context(mid, meta)

    return MilestoneEvent(
        milestone_id=f"maturation:{mid}",
        category=MilestoneCategory.BIRTH,
        title=title,
        summary=summary,
        context=context,
        dedupe_key=f"maturation:{mid}",
    )


def _build_summary(milestone_id: str, phase_label: str, meta: dict[str, Any]) -> str:
    if milestone_id == "genesis_contract_signed":
        return f"Maturation fase {phase_label}: groeicontract opgeslagen vóór Birth."
    if milestone_id == "birth_started":
        mode = meta.get("training_mode", "certified")
        budget = int(meta.get("trade_budget", 0) or 0)
        resumed = bool(meta.get("resumed", False))
        text = f"Maturation fase {phase_label}: Birth gestart ({mode}, budget {budget:,})."
        return text + (" Hervat vanaf checkpoint." if resumed else "")
    if milestone_id == "birth_certificate_issued":
        trades = int(meta.get("cumulative_trades", 0) or 0)
        return f"Maturation fase {phase_label}: Birth Certificate v2 uitgegeven ({trades:,} trades)."
    if milestone_id == "evolution_proof_passed":
        wr = float(meta.get("oos_winrate", 0.0) or 0.0)
        return f"Maturation fase {phase_label}: Evolution Proof passed (OOS winrate {wr:.1%})."
    if milestone_id == "deck_unlocked":
        return f"Maturation fase {phase_label}: Command Deck beschikbaar na Birth artifacts."
    if milestone_id == "first_sim_order_placed":
        return f"Maturation fase {phase_label}: eerste sim-order geplaatst."
    if milestone_id == "sim_mirror_api_ok":
        return f"Maturation fase {phase_label}: sim mirror API OK."
    if milestone_id == "sim_real_guard_stable":
        days = int(meta.get("consecutive_green_days", 0) or 0)
        return f"Maturation fase {phase_label}: READY_FOR_REAL ({days}/5 green days)."
    if milestone_id == "shadow_validation_passed":
        return f"Maturation fase {phase_label}: shadow validation passed."
    if milestone_id == "promotion_gate_passed":
        return f"Maturation fase {phase_label}: PromotionGate passed — REAL eligibility stap dichterbij."
    if milestone_id == "human_real_approval":
        src = str(meta.get("source", "command_deck") or "command_deck")
        return f"Maturation fase {phase_label}: operator REAL goedgekeurd ({src})."
    if milestone_id == "real_trading_live":
        return f"Maturation fase {phase_label}: REAL mode actief — live kapitaalbescherming actief."
    return f"Maturation milestone: {milestone_id} (fase {phase_label})."


def _build_context(milestone_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    ctx: dict[str, Any] = {"maturation_milestone": milestone_id}
    for key in (
        "training_mode",
        "trade_budget",
        "resumed",
        "cumulative_trades",
        "oos_winrate",
        "lift",
        "consecutive_green_days",
        "shadow_status",
        "dna_hash",
        "mode",
        "source",
        "action",
        "qty",
    ):
        if key in meta and meta[key] is not None:
            ctx[key] = meta[key]
    return ctx
