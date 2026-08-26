"""Operator-facing Twin Telegram copy (base_v4, plain language).

SSOT for human-readable Twin messages on Telegram. Technical dumps stay in
audit JSONL — never in the operator body.

Elon bar: non-technical operator decides in ≤15s without Command Deck.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from lumina_core.evolution.twin_question_style import (
    _flags_nl,
    _reasons_nl,
    _rec_nl,
    format_teach_scenario,
)

# Internal call → plain NL situation
_CALL_NL: dict[str, str] = {
    "evaluate_dna_promotion": "Voorstel: nieuwe handelsregels (DNA) promoten in de leerlus",
    "evaluate_dna": "Voorstel: handelsregels (DNA) beoordelen",
    "evaluate_code_proposal": "Voorstel: code-wijziging beoordelen",
    "evaluate_shadow": "Voorstel: shadow-resultaat beoordelen",
    "evaluate_shadow_promotion": "Voorstel: shadow-promotie beoordelen",
    "shadow_observe": "Twin keek mee bij een shadow-observatie",
    "micro": "Korte Twin-oefening met live of recente data",
    "escalation": "Twin is onzeker en vraagt jouw oordeel vóór een besluit",
}


def short_id(value: str, *, n: int = 10) -> str:
    s = str(value or "").strip()
    if not s:
        return "—"
    return s if len(s) <= n else s[:n]


def short_dna(dna_hash: str, *, n: int = 12) -> str:
    s = str(dna_hash or "").strip()
    if not s:
        return "—"
    return f"{s[:n]}…" if len(s) > n else s


def humanize_call(call: str) -> str:
    c = str(call or "").strip()
    if not c:
        return "Voorstel: Twin-beoordeling van een bot-stap"
    key = c.lower()
    if key in _CALL_NL:
        return _CALL_NL[key]
    # snake_case → soft fallback
    soft = key.replace("evaluate_", "").replace("_", " ")
    return f"Voorstel: {soft} beoordelen"


def humanize_explanation(raw: str, *, max_len: int = 220) -> str:
    """Strip engineering dumps into one operator sentence when possible."""
    text = str(raw or "").strip()
    if not text:
        return ""

    # Pattern: Twin score=X%, threshold=Y%
    m = re.search(
        r"score\s*=\s*([0-9.]+)\s*%?\s*,?\s*threshold\s*=\s*([0-9.]+)\s*%?",
        text,
        re.I,
    )
    if m:
        try:
            score = float(m.group(1))
            thr = float(m.group(2))
            # scores sometimes already percent (54.83) or ratio
            if score <= 1.5 and thr <= 1.5:
                score_pct, thr_pct = score * 100.0, thr * 100.0
            else:
                score_pct, thr_pct = score, thr
            if score_pct < thr_pct:
                return (
                    f"Twin-score {score_pct:.0f}% lag onder de drempel {thr_pct:.0f}% "
                    f"— daarom neiging tot afkeuren."
                )
            return (
                f"Twin-score {score_pct:.0f}% lag op/boven de drempel {thr_pct:.0f}% "
                f"— daarom neiging tot goedkeuren."
            )
        except (TypeError, ValueError):
            pass

    # Drop pure engineering tokens from free text
    cleaned = text
    for pat in (
        r"\bbackend\s*=\s*\S+",
        r"\bsource\s*=\s*\S+",
        r"\bmutation_rate\s*=\s*\S+",
        r"\bfitness\s*=\s*\S+",
        r"\blocal_heuristic\([^)]*\)",
        r"\bthreshold\s*=\s*\S+",
    ):
        cleaned = re.sub(pat, "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;")
    if not cleaned:
        return ""
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def conf_pct(confidence: float) -> int:
    c = float(confidence)
    if c <= 1.5:
        c = c * 100.0
    return max(0, min(100, int(round(c))))


@dataclass
class TwinOperatorBrief:
    """Structured facts for one Twin→operator Telegram message."""

    kind: str  # decision_feed | escalation | dna_promotion | micro
    message_id: str = ""
    dna_hash: str = ""
    call: str = ""
    recommendation: bool | None = None
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    explanation: str = ""
    doubt_reasons: list[str] = field(default_factory=list)
    mode: str = ""
    authority: str = ""
    executable: bool | None = None
    fitness: float | None = None
    proposal_summary: str = ""
    veto_window_minutes: int | None = None
    cutoff_label: str = ""
    choices: Sequence[dict[str, Any]] = field(default_factory=tuple)


def format_decision_feed_telegram(brief: TwinOperatorBrief) -> str:
    """Post-hoc Twin judgment — optional operator feedback (natraining)."""
    mid = short_id(brief.message_id)
    conf = conf_pct(brief.confidence)
    lean = _rec_nl(brief.recommendation)
    why = humanize_explanation(brief.explanation) or (
        "Twin-score lag onder of rond de drempel."
        if brief.recommendation is False
        else "Twin-score lag op/boven de drempel."
    )
    situation = humanize_call(brief.call)
    flags = _flags_nl(brief.risk_flags)

    lines = [
        "LUMINA · Twin keek mee (natraining)",
        "Dit is géén spoed-goedkeuring. De Twin heeft al geoordeeld; jij mag bijsturen.",
        "",
        "Situatie",
        f"• Wat: {situation}",
        f"• Twin-oordeel: {lean}",
        f"• Zekerheid: {conf}%",
        f"• Risico-signalen: {flags}",
        f"• DNA: {short_dna(brief.dna_hash)}",
        f"• Waarom (kort): {why}",
        "",
        "Termen",
        "DNA = handelsregels van de bot · conf = zekerheid · "
        "APPROVE = doorzetten · VETO = afkeuren · MODIFY = alleen met aanpassing",
        "",
        "Jouw feedback (optioneel — leert de Twin, stopt niets)",
        "• OK     = eens met de Twin",
        "• A      = had GOEDGEKEURD moeten zijn",
        "• B      = had AFGEKEURD moeten zijn",
        "• C      = alleen met aanpassing (stuur 1 korte zin)",
        "",
        "Antwoord bv.:",
        f"  OK {mid}",
        f"  A {mid}",
        f"  C {mid} strengere limiet",
    ]
    return "\n".join(lines)


def format_escalation_telegram(brief: TwinOperatorBrief) -> str:
    """Pre-decision doubt escalation — path waits for A/B/C/D."""
    mid = short_id(brief.message_id)
    conf = conf_pct(brief.confidence)
    lead = (
        "LUMINA · Twin is onzeker — jouw oordeel nodig\n"
        "Zonder jouw antwoord gaat dit pad niet sole-auto verder."
    )
    live = [
        f"Twin-neiging (nog niet definitief): {_rec_nl(brief.recommendation)}",
        f"Zekerheid: {conf}%",
        f"Waarom escalatie: {_reasons_nl(brief.doubt_reasons)}",
        f"Risico-signalen: {_flags_nl(brief.risk_flags)}",
        f"DNA: {short_dna(brief.dna_hash)}",
    ]
    why = humanize_explanation(brief.explanation)
    if why:
        live.append(f"Twin-uitleg: {why}")

    body = format_teach_scenario(
        lead=lead,
        live_lines=live,
        ask="Wat zou jij doen? Elke optie toont + (voordeel) en − (nadeel).",
        terms=[
            "DNA = handelsregels",
            "conf = zekerheid",
            "APPROVE / VETO / MODIFY = doorzetten / afkeuren / aanpassen",
        ],
        explanation="",
    )
    lines = [body, ""]
    for c in brief.choices or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip() or "?"
        label = str(c.get("label") or "").strip()
        if not label:
            continue
        # Prefer multi-line ± for Telegram readability
        parts = label.split("\n")
        lines.append(f"{cid} — {parts[0]}")
        for extra in parts[1:]:
            e = extra.strip()
            if e:
                lines.append(f"   {e}")
        lines.append("")
    lines.append(f"Antwoord: A  of  TWIN {mid} A")
    return "\n".join(lines).rstrip()


def format_dna_promotion_telegram(brief: TwinOperatorBrief) -> str:
    """REAL DNA promotion window — fail-closed APPROVE/VETO."""
    mid = short_id(brief.message_id or brief.dna_hash, n=16)
    conf = conf_pct(brief.confidence)
    lean = _rec_nl(brief.recommendation) if brief.recommendation is not None else "onbekend"
    summary = humanize_explanation(brief.proposal_summary, max_len=240) or str(
        brief.proposal_summary or ""
    ).strip()[:240]
    window = brief.veto_window_minutes
    window_txt = f"{int(window)} min" if window is not None else "beperkte tijd"
    cutoff = str(brief.cutoff_label or "").strip()

    lines = [
        "LUMINA · DNA-promotie — goedkeuren of blokkeren",
        "Zonder jouw antwoord wordt dit geblokkeerd (fail-closed).",
        "",
        "Situatie",
        "• Wat: een set handelsregels (DNA) wil doorgroeien (promotie)",
        f"• Twin-neiging: {lean}",
        f"• Zekerheid Twin: {conf}%",
        f"• DNA: {short_dna(brief.dna_hash)}",
    ]
    if summary:
        lines.append(f"• Samenvatting: {summary}")
    lines.extend(
        [
            f"• Antwoordtermijn: {window_txt}"
            + (f" (tot {cutoff})" if cutoff else ""),
            "",
            "Termen",
            "APPROVE = promotie mag verder · VETO = promotie geblokkeerd · "
            "geen antwoord = auto-VETO (veilige kant)",
            "",
            "Antwoord:",
            f"  APPROVE {mid}",
            f"  VETO {mid}",
        ]
    )
    return "\n".join(lines)


def format_decision_telegram_message(payload: dict[str, Any]) -> str:
    """Adapter: legacy decision_notify payload → operator Telegram body."""
    brief = TwinOperatorBrief(
        kind="decision_feed",
        message_id=str(payload.get("decision_id") or ""),
        dna_hash=str(payload.get("dna_hash") or ""),
        call=str(payload.get("call") or ""),
        recommendation=(
            bool(payload["recommendation"])
            if "recommendation" in payload
            else None
        ),
        confidence=float(payload.get("confidence") or 0.0),
        risk_flags=list(payload.get("risk_flags") or []),
        explanation=str(payload.get("explanation") or payload.get("why") or ""),
        mode=str(payload.get("mode") or ""),
        authority=str(payload.get("authority") or ""),
        executable=payload.get("executable") if "executable" in payload else None,
    )
    # Prefer twin_answer if recommendation missing
    if brief.recommendation is None:
        ans = str(payload.get("twin_answer") or "").upper()
        if "APPROVE" in ans:
            brief.recommendation = True
        elif "VETO" in ans:
            brief.recommendation = False
    return format_decision_feed_telegram(brief)


__all__ = [
    "TwinOperatorBrief",
    "short_id",
    "short_dna",
    "humanize_call",
    "humanize_explanation",
    "conf_pct",
    "format_decision_feed_telegram",
    "format_escalation_telegram",
    "format_dna_promotion_telegram",
    "format_decision_telegram_message",
]
