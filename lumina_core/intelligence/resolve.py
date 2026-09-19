"""Voice workload provider resolver. News is Voice, never Lungs, never orders."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

VoiceProviderId = Literal["ollama", "grok_remote", "vllm", "off"]


class VoiceWorkload(StrEnum):
    LEARN_EXPLAIN = "learn_explain"
    TWIN_COPY = "twin_copy"
    NEWS_INTERPRET = "news_interpret"
    STRATEGY_TEXT = "strategy_text"


_NEWS_PREFERENCE: tuple[VoiceProviderId, ...] = ("grok_remote", "ollama", "vllm")
_EXPLAIN_PREFERENCE: tuple[VoiceProviderId, ...] = ("ollama", "grok_remote", "vllm")

LUNGS_INSTALLER_TOKENS: frozenset[str] = frozenset(
    {"install_birth_physics_stack", "requirements-birth-physics", "stable_baselines3", "torch"}
)


def preference_for(workload: VoiceWorkload) -> tuple[VoiceProviderId, ...]:
    if workload is VoiceWorkload.NEWS_INTERPRET:
        return _NEWS_PREFERENCE
    return _EXPLAIN_PREFERENCE


def resolve_provider(
    workload: VoiceWorkload,
    *,
    allowed_providers: list[str],
    selected_provider: VoiceProviderId | str = "off",
) -> VoiceProviderId:
    """Pick a Voice provider. Never returns a Lungs installer. Off is legal."""
    allowed = {str(item).strip().lower() for item in allowed_providers}
    allowed.discard("off")
    preferred = preference_for(workload)
    selected = str(selected_provider or "off").strip().lower()
    if selected in allowed and selected in preferred:
        # Honour an explicit healthy selection when it is legal for the workload.
        if selected in {"ollama", "grok_remote", "vllm"}:
            if workload is VoiceWorkload.NEWS_INTERPRET and selected == "grok_remote":
                return "grok_remote"
    for candidate in preferred:
        if candidate in allowed:
            if candidate in LUNGS_INSTALLER_TOKENS:
                continue
            return candidate
    return "off"


def fail_closed_news_result(*, reason: str = "voice_off") -> dict[str, object]:
    """Neutral news payload when Voice is off or unusable. Never throws."""
    return {
        "sentiment_signal": "neutral",
        "sentiment_score": 0.0,
        "high_impact": False,
        "high_impact_events": [],
        "summary": "Thinking assistant is off; news reading stays neutral.",
        "dynamic_multiplier": 1.0,
        "news_avoidance_window": False,
        "news_avoidance_hold_until_ts": 0.0,
        "news_avoidance_reason": "",
        "confidence": 0.0,
        "fallback_level": 1,
        "fallback_reason_code": reason,
        "degraded": True,
        "order_path_coupled": False,
    }
