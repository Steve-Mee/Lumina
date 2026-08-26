"""Shared teach-while-train question style for base / micro / escalation (base_v4).

Plain lead → live data bullets → term glossary → clear ask.
Choices always carry explicit + / − consequences.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from lumina_core.evolution.twin_curriculum_types import TwinChoice

# Human-readable labels for doubt_reasons / risk flags
_DOUBT_NL: dict[str, str] = {
    "low_conf": "lage zekerheid (onder de high-conf drempel)",
    "conflicting_risk_flags": "risk flags bij twijfelachtige conf",
    "novel_pattern": "nieuw DNA-patroon (nog niet door jou gelabeld)",
    "unseen_risk_flags": "ongewone / zeldzame risk flags",
}

_FLAG_NL: dict[str, str] = {
    "correlated_instruments": "gecorreleerde instrumenten (dubbele blootstelling)",
    "overnight": "overnight / gap-risico",
    "black_swan": "extreme schok (black swan)",
    "low_liquidity": "lage liquiditeit / brede spread",
}


def choice_with_consequences(text: str, *, plus: str, minus: str) -> str:
    """Choice label with explicit positive and negative consequences."""
    return f"{text}\n+ {plus}\n− {minus}"


def standard_avm_choices(
    *,
    approve_plus: str | None = None,
    approve_minus: str | None = None,
    veto_plus: str | None = None,
    veto_minus: str | None = None,
    modify_plus: str | None = None,
    modify_minus: str | None = None,
    need_data: bool = True,
) -> tuple[TwinChoice, ...]:
    """APPROVE / VETO / MODIFY (+ optional need_more_data) with base_v4 ± style."""
    choices: list[TwinChoice] = [
        TwinChoice(
            id="A",
            label=choice_with_consequences(
                "APPROVE — doorzetten",
                plus=approve_plus or "Loop/DNA gaat verder; snellere vooruitgang",
                minus=approve_minus
                or "Als het fout is, zit de fout in de volgende stappen",
            ),
            value_signal="approve",
        ),
        TwinChoice(
            id="B",
            label=choice_with_consequences(
                "VETO — afkeuren / stoppen",
                plus=veto_plus or "Geen risicovolle stap doorlaten",
                minus=veto_minus or "Je mist de kans als dit wél goed was",
            ),
            value_signal="veto",
        ),
        TwinChoice(
            id="C",
            label=choice_with_consequences(
                "MODIFY — alleen met aanpassing",
                plus=modify_plus or "Kans behouden mét strengere voorwaarden",
                minus=modify_minus or "Kost extra ronde tijd voordat je verdergaat",
            ),
            value_signal="modify",
        ),
    ]
    if need_data:
        choices.append(
            TwinChoice(
                id="D",
                label=choice_with_consequences(
                    "Meer data nodig (nog niet beslissen)",
                    plus="Minder kans op een haastige foute label",
                    minus="De bot wacht; je verliest even tempo",
                ),
                value_signal="need_more_data",
            )
        )
    return tuple(choices)


def _rec_nl(rec: bool | None | str) -> str:
    if rec is True or (isinstance(rec, str) and rec.upper() == "APPROVE"):
        return "APPROVE (doorzetten)"
    if rec is False or (isinstance(rec, str) and rec.upper() == "VETO"):
        return "VETO (afkeuren)"
    if isinstance(rec, str) and rec.upper() == "MODIFY":
        return "MODIFY (aanpassen)"
    return "onbekend / geen duidelijke neiging"


def _flags_nl(flags: Sequence[str] | None) -> str:
    items = [str(f).strip() for f in (flags or []) if str(f).strip()]
    if not items:
        return "geen"
    out: list[str] = []
    for f in items[:6]:
        gloss = _FLAG_NL.get(f)
        out.append(f"{f} ({gloss})" if gloss else f)
    return ", ".join(out)


def _reasons_nl(reasons: Sequence[str] | None) -> str:
    items = [str(r).strip() for r in (reasons or []) if str(r).strip()]
    if not items:
        return "—"
    return "; ".join(_DOUBT_NL.get(r, r) for r in items[:6])


def format_teach_scenario(
    *,
    lead: str,
    live_lines: Sequence[str],
    ask: str,
    terms: Sequence[str] | None = None,
    explanation: str = "",
    max_explanation: int = 220,
) -> str:
    """
    base_v4 layout:
      lead
      Live data: bullet lines
      optional Twin-uitleg
      Termen: …
      ask
    """
    parts: list[str] = [str(lead or "").strip()]
    bullets = [str(x).strip() for x in live_lines if str(x).strip()]
    if bullets:
        parts.append("Live data:\n" + "\n".join(f"• {b}" for b in bullets))
    exp = str(explanation or "").strip()
    if exp:
        if len(exp) > max_explanation:
            exp = exp[: max_explanation - 1] + "…"
        parts.append(f"Twin-uitleg: {exp}")
    term_list = list(terms) if terms is not None else [
        "DNA = handelsregels van de bot",
        "conf = hoe zeker de Twin is (in %)",
        "APPROVE / VETO / MODIFY = doorzetten / afkeuren / alleen met aanpassing",
        "risk flags = waarschuwingen van de risk-check",
    ]
    if term_list:
        parts.append("Termen: " + " · ".join(term_list))
    parts.append(str(ask or "").strip())
    return "\n".join(p for p in parts if p)


def format_micro_live_scenario(
    *,
    conf: float,
    recommendation: bool | None | str = None,
    risk_flags: Sequence[str] | None = None,
    dna_hash: str = "",
    summary: str = "",
    source_hint: str = "",
) -> str:
    """Teach-while-train scenario for micro (live or gym) with operator clarity."""
    conf_pct = max(0, min(100, int(round(float(conf) * 100))))
    dna = str(dna_hash or "").strip()
    dna_short = f"{dna[:14]}…" if len(dna) > 14 else (dna or "—")
    body = str(summary or "").strip()
    # If caller already passed a long free-form summary, keep as context line
    live: list[str] = [
        f"Twin-neiging: {_rec_nl(recommendation)}",
        f"Zekerheid (conf): {conf_pct}%",
        f"Risk flags: {_flags_nl(list(risk_flags) if risk_flags is not None else None)}",
        f"DNA: {dna_short}",
    ]
    if source_hint:
        live.insert(0, f"Bron: {source_hint}")
    if body and body not in live:
        # Avoid duplicating if summary is only technical dump
        if len(body) > 280:
            body = body[:277] + "…"
        live.append(f"Context: {body}")
    return format_teach_scenario(
        lead=(
            "Oefenvraag met live of recente bot-data — label alsof dit kapitaal-kritisch is "
            "(REAL-conscience). In pure SIM blokkeert de Twin de leerlus niet; jouw antwoord "
            "traint de standaard voor sim_real_guard en REAL."
        ),
        live_lines=live,
        ask="Kies A/B/C/D. Bij elke optie zie je + (voordeel) en − (nadeel).",
    )


def format_escalation_live_scenario(
    *,
    conf: float,
    recommendation: bool | None = None,
    risk_flags: Sequence[str] | None = None,
    dna_hash: str = "",
    explanation: str = "",
    doubt_reasons: Sequence[str] | None = None,
) -> str:
    """Teach-while-train scenario for doubt escalation (pre-decision human ask)."""
    conf_pct = max(0, min(100, int(round(float(conf) * 100))))
    dna = str(dna_hash or "").strip()
    dna_short = f"{dna[:14]}…" if len(dna) > 14 else (dna or "—")
    live: list[str] = [
        f"Twin-neiging (intern, nog niet definitief): {_rec_nl(recommendation)}",
        f"Zekerheid (conf): {conf_pct}% — onder of rond de high-conf drempel (~80%)",
        f"Waarom escalatie: {_reasons_nl(doubt_reasons)}",
        f"Risk flags: {_flags_nl(risk_flags)}",
        f"DNA: {dna_short}",
    ]
    return format_teach_scenario(
        lead=(
            "De Twin is onzeker en vraagt jouw oordeel vóór er een besluit valt "
            "(twijfel-escalatie op values-active / REAL-like pad). "
            "Antwoord alsof kapitaal telt — dit traint de enige Twin-conscience."
        ),
        live_lines=live,
        explanation=explanation,
        ask="Wat zou jij doen? Elke optie toont + (voordeel) en − (nadeel).",
    )


def metrics_hint_from_live(
    *,
    conf: float,
    risk_flags: Iterable[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    flags = [str(f) for f in (risk_flags or []) if str(f).strip()][:4]
    parts = [f"conf={float(conf):.2f}", f"flags={flags or '[]'}"]
    for k, v in (extra or {}).items():
        parts.append(f"{k}={v}")
    return " ".join(parts)
