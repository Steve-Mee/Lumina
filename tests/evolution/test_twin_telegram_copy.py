"""Golden tests: Twin Telegram operator copy is plain-language base_v4."""

from __future__ import annotations

from lumina_core.evolution.twin_telegram_copy import (
    TwinOperatorBrief,
    format_decision_feed_telegram,
    format_decision_telegram_message,
    format_dna_promotion_telegram,
    format_escalation_telegram,
    humanize_call,
    humanize_explanation,
)
from lumina_core.evolution.twin_decision_notify import parse_decision_feedback_text


def test_humanize_call_and_explanation() -> None:
    assert "evaluate_dna" not in humanize_call("evaluate_dna_promotion").lower()
    assert "handelsregels" in humanize_call("evaluate_dna_promotion").lower()
    why = humanize_explanation(
        "Twin score=54.83%, threshold=60%, backend=local, fitness=0.26, "
        "mutation_rate=0.03, source=local_heuristic(threshold=60%)"
    )
    assert "backend" not in why.lower()
    assert "mutation" not in why.lower()
    assert "54" in why or "55" in why
    assert "60" in why


def test_decision_feed_no_engineering_dump() -> None:
    msg = format_decision_feed_telegram(
        TwinOperatorBrief(
            kind="decision_feed",
            message_id="hsbDWdxQUYLy",
            dna_hash="55e421bda7acd8bc103f0cc629c589a57d09f08a9f93d4217bd2f8fe004978ed",
            call="evaluate_dna_promotion",
            recommendation=False,
            confidence=0.548,
            risk_flags=[],
            explanation=(
                "Twin score=54.83%, threshold=60%, backend=local, "
                "fitness=0.2600, mutation_rate=0.03, source=local_heuristic(threshold=60%)"
            ),
            mode="shadow",
            authority="propose_only",
            executable=False,
        )
    )
    low = msg.lower()
    assert "natraining" in low or "keek mee" in low
    assert "evaluate_dna" not in low
    assert "backend=" not in low
    assert "local_heuristic" not in low
    assert "mutation_rate" not in low
    assert "situatie" in low
    assert "termen" in low
    assert "ok hsbdwdxqu" in low or "ok hsbd" in low
    assert "a hsbd" in low  # base_v4 A reply
    # full 64-char dna dump not in body
    assert "55e421bda7acd8bc103f0cc629c589a57d09f08a9f93d4217bd2f8fe004978ed" not in msg


def test_format_decision_from_legacy_payload() -> None:
    msg = format_decision_telegram_message(
        {
            "decision_id": "abc123xyz99",
            "dna_hash": "deadbeefcafebabe",
            "call": "evaluate_dna_promotion",
            "recommendation": True,
            "confidence": 0.91,
            "explanation": "Twin score=91%, threshold=60%, backend=local",
            "executable": True,
            "authority": "execute_judgment",
        }
    )
    assert "evaluate_dna" not in msg.lower()
    assert "goedkeur" in msg.lower() or "approve" in msg.lower()
    assert "nátijden" in msg.lower() or "natraining" in msg.lower() or "keek mee" in msg.lower()


def test_escalation_has_choices_and_urgency() -> None:
    msg = format_escalation_telegram(
        TwinOperatorBrief(
            kind="escalation",
            message_id="esc1234567",
            dna_hash="abc123",
            recommendation=False,
            confidence=0.55,
            risk_flags=["overnight"],
            doubt_reasons=["low_conf"],
            explanation="onzeker over overnight gap",
            choices=[
                {
                    "id": "A",
                    "label": "APPROVE — doorzetten\n+ sneller\n− risico blijft",
                },
                {
                    "id": "B",
                    "label": "VETO — afkeuren\n+ fail-closed\n− mist kans",
                },
            ],
        )
    )
    assert "onzeker" in msg.lower() or "oordeel nodig" in msg.lower()
    assert "A —" in msg or "A —" in msg.replace("—", "-")
    assert "+" in msg and "−" in msg or "-" in msg
    assert "TWIN" in msg.upper()


def test_dna_promotion_fail_closed_copy() -> None:
    msg = format_dna_promotion_telegram(
        TwinOperatorBrief(
            kind="dna_promotion",
            message_id="dna_xyz_fullhash_extra",
            dna_hash="dna_xyz_fullhash_extra",
            recommendation=True,
            confidence=0.92,
            fitness=0.85,
            proposal_summary="Improve stage2 range patience",
            veto_window_minutes=30,
            cutoff_label="12:00 UTC",
        )
    )
    low = msg.lower()
    assert "promotie" in low or "dna" in low
    assert "APPROVE" in msg
    assert "VETO" in msg
    assert "auto-veto" in low or "geblokkeerd" in low
    # No raw fitness dump for operators
    assert "fitness" not in low
    assert "0.85" not in msg


def test_parse_abc_aliases() -> None:
    assert parse_decision_feedback_text("A dec1")["action"] == "FIX_A"
    assert parse_decision_feedback_text("B dec1")["action"] == "FIX_V"
    assert parse_decision_feedback_text("C dec1 note")["action"] == "FIX_M"
    assert parse_decision_feedback_text("FIX V dec99")["action"] == "FIX_V"
    assert parse_decision_feedback_text("OK dec1")["action"] == "OK"


def test_dna_proposal_prefix_match_for_short_ids() -> None:
    from lumina_core.notifications.telegram_notifier import TelegramNotifier

    n = TelegramNotifier(api_token="", chat_id="")
    full = "deadbeefcafebabe0123456789abcdef"
    with n._lock:  # noqa: SLF001
        n._pending_proposals[full] = {
            "status": n.STATUS_PENDING,
            "dna_fitness": 0.8,
        }
    # Short prefix as shown in Telegram body
    key = n._resolve_pending_proposal_key(full[:12])  # noqa: SLF001
    assert key == full
    n._apply_reply("APPROVE", full[:10])
    with n._lock:  # noqa: SLF001
        assert n._pending_proposals[full]["status"] == n.STATUS_APPROVED
