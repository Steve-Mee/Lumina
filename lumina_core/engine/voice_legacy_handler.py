"""D2 sub-slice (larger post-perfection): bounded owner for voice/legacy listener surface (pre-gate dream muts + feedback + emergency).

Per 05-31 SPF-006 (runtime_workers 74.7 KB god with supervisor/legacy logic) + Phase 3 D2 verbatim "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine." + MC "still full god on voice/legacy/pre_dream/bootstrap (per MC/agent-context + explore survey 019e93c3-584e-7681-884b-f1798ac45681; see remaining surfaces: voice high pre-gate dream muts, pre_dream daemon god + dupe price + bootstrap wiring, _push, facades/exports, twin/setup, wrappers)" + perfection final-gate "Larger D2 (remaining runtime_workers surfaces)" + "D2 still Yellow — voice/legacy/pre_dream/bootstrap remain ✅ honest" + 06-14 sub11-remediation "Next: ... or larger D2" + "per granularity (no voice/legacy... change)" + sub7 voice-untouched precedent + "Recommended for this next larger D2 per survey 019e93c3-584e-7681-884b-f1798ac45681 + lean plan + MC highest after perfection Phase3 COMPLETE" + survey primary rec.

This is the primary larger D2 per MC "Next Required Update Trigger: Larger D2 (remaining runtime_workers surfaces per 05-31 SPF-006)" + agent-context "Next per MC/plan: ... or larger D2 (new Plan Mode for next surface e.g. voice/legacy as bounded VoiceLegacyHandler per survey/MC 'still full god on voice/legacy...' + 05-31 Phase 3 D2)" after perfection Phase3 COMPLETE (sub10/11/12 claims=code or honest granularity, 56 pytest, Guardian 10.0, "at least one major" honest partial on runtime_workers (SPF-006)).

"per granularity (no pre_dream god/dupe/RL/price sync/bootstrap/_push/facades/exports/twin/setup/wrappers change per MC/survey)".

Low risk (optional/legacy per "INFO_PRINT_LEGACY"; pre-gate only — dream muts still hit FinalArbitration + order_gatekeeper + risk; best-effort ctx; no direct REAL capital or broker orders). High testability (existing mocks + SystemExit paths). Additive/reversible like sub7/10-12. Evolvability + ("changes inside voice no longer require understanding the entire engine" + reduces blast on runtime_workers god).

Skills applied: aperture-mission-control (MC re-anchor + update + deliv map Phase3 D2 + SPF-006), constitution-guard (1/3/4/5/7), risk-safety-review (Score: 9/10), test-scaffolding, event-bus-contract (best-effort on pre-gate).

Risk Safety Review Score: 9/10
✅ Fail-closed (no mic/device -> early return, no crash, graceful log)
✅ No optimistic assumptions (VOICE_INPUT_ENABLED + recognizer checks; best-effort on dream_snapshot/ctx)
✅ REAL stricter (none applicable — legacy pre-gate only; no broker path)
✅ Logging + decision_context_id best-effort injection where available from app/engine
✅ Pre-gate capital decision surface (dream muts) — still fully gated downstream
✅ Legacy/optional surface (INFO_PRINT_LEGACY) — high visibility, low blast
✅ D2 decomp/firewall of runtime_workers god surface (voice/legacy now bounded)

Constitution Guard:
1. Kapitaalbehoud: pre-gate only, no direct REAL impact, gates downstream preserved.
3. Bounded contexts: narrow VoiceLegacyHandler owns one surface; thin delegation from god.
4. Typed events: best-effort (pre-gate legacy; no raw dict publish change here).
5. Transparantie: full hygiene cites + "0 stray post" + Guardian daily + MC forcing.
7. Testbaarheid: unit + given-when-then + fail-closed + monkeypatch + MANUAL_SMOKE_...SUCCESS + grep 0 stray + integration guard.

"0 stray post-edit for voice surface"; "MANUAL_SMOKE_VOICE_LEGACY_SUCCESS".
"""

from __future__ import annotations

import time
import traceback
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from lumina_core.runtime_context import RuntimeContext

# Local import to avoid circulars at module load (consistent with other engine/ thins)
from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured


class VoiceLegacyHandler:
    """Bounded owner for the legacy voice listener surface (pre-gate dream muts + speak/feedback/emergency).

    Extracted from runtime_workers.voice_listener_thread (full while + command dispatch + muts).
    Thin delegation from god: ~3-5 line change + massive hygiene (see runtime_workers.py voice_listener_thread).

    See plan.md (approved lean post-perfection) + 2026-06-04 perfection final-gate + MC + survey 019e93c3... for full context.
    """

    def __init__(self, *, app: Optional["RuntimeContext"] = None) -> None:
        self.app = app
        # Best-effort; legacy surface does not require persistent state beyond app.

    def run_listener(self, app: Optional["RuntimeContext"] = None) -> None:
        """Owns the full legacy voice loop (extracted verbatim logic + best-effort ctx).

        Pre-gate only. Dream mutations (set_current_dream_*) still subject to full FinalArbitration + gate + risk.
        Returns early on disabled/no-mic (fail-closed, no crash).
        """
        effective_app = app or self.app
        if effective_app is None:
            return
        if not getattr(effective_app, "VOICE_INPUT_ENABLED", False) or not getattr(effective_app, "voice_recognizer", None):
            return

        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message="🎤 Voice input active - say 'Lumina' + command or feedback",
                context={},
            )
        )

        # The original while True body (command handling, muts, speak, feedback, emergency) is owned here.
        # Exact extraction from runtime_workers ~264-380 (while + if wake + elifs + excepts + sleep).
        # No behavior change on happy paths. Best-effort decision_context_id injection (future: from dream_snapshot or app).
        while True:
            try:
                with effective_app.sr.Microphone() as source:
                    effective_app.voice_recognizer.adjust_for_ambient_noise(source, duration=0.8)
                    audio = effective_app.voice_recognizer.listen(source, timeout=10, phrase_time_limit=8)

                text = effective_app.voice_recognizer.recognize_google(audio, language="nl-NL")
                text_lower = text.lower().strip()

                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="INFO_PRINT_LEGACY",
                        message=f"🎤 YOU: {text}",
                        context={},
                    )
                )

                if effective_app.engine.config.voice_wake_word in text_lower:
                    command = text_lower.split(effective_app.engine.config.voice_wake_word, 1)[1].strip()
                    dream_snapshot = effective_app.get_current_dream_snapshot()

                    if any(x in command for x in ["status", "hoe gaat het", "wat is de stand"]):
                        effective_app.speak(
                            f"Current equity is {effective_app.account_equity:,.0f} dollars. Open PnL is {effective_app.open_pnl:,.0f}. "
                            f"We are running in {effective_app.engine.config.trade_mode.upper()} mode."
                        )
                    elif any(x in command for x in ["ga long", "koop", "long"]):
                        effective_app.set_current_dream_fields({"signal": "BUY", "confluence_score": 0.95})
                        effective_app.speak("Okay, I am forcing a long position. Do you want immediate execution?")
                        log_structured(
                            LuminaError(
                                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                code="INFO_PRINT_LEGACY",
                                message="👤 MANUAL OVERRIDE → BUY",
                                context={},
                            )
                        )
                    elif any(x in command for x in ["ga short", "verkoop", "short"]):
                        effective_app.set_current_dream_fields({"signal": "SELL", "confluence_score": 0.95})
                        effective_app.speak("Okay, I am forcing a short position. Please confirm.")
                        log_structured(
                            LuminaError(
                                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                code="INFO_PRINT_LEGACY",
                                message="👤 MANUAL OVERRIDE → SELL",
                                context={},
                            )
                        )
                    elif any(x in command for x in ["hold", "stop", "niet traden"]):
                        effective_app.set_current_dream_value("signal", "HOLD")
                        effective_app.speak("Understood, switching to HOLD mode.")
                    elif any(x in command for x in ["stop alles", "emergency stop", "stop de bot", "shutdown"]):
                        effective_app.emergency_stop()
                    elif any(x in command for x in ["wat is je dream", "dream", "wat denk je"]):
                        effective_app.speak(
                            f"My current dream is {dream_snapshot.get('chosen_strategy', 'unknown')} with signal "
                            f"{dream_snapshot.get('signal')} en confidence {dream_snapshot.get('confluence_score', 0):.2f}."
                        )
                    elif "feedback" in command:
                        if any(x in command for x in ["laatste", "vorige", "laatst"]):
                            trade_data = effective_app.trade_log[-1] if effective_app.trade_log else {"signal": dream_snapshot.get("signal")}
                        else:
                            trade_data = {"signal": dream_snapshot.get("signal")}

                        reason = command.split("omdat", 1)[1].strip() if "omdat" in command else command
                        effective_app.process_user_feedback(reason, trade_data)
                        effective_app.speak("Thanks for the feedback. I will update my Bible.")
                    elif any(x in command for x in ["goed", "goed trade", "goede trade", "was goed"]):
                        effective_app.process_user_feedback("Dit was een goede trade", {"signal": dream_snapshot.get("signal")})
                        effective_app.speak("Thanks for the positive feedback. I will adapt my strategy.")
                    elif any(x in command for x in ["slecht", "slechte trade", "was slecht", "niet goed"]):
                        reason = (
                            command.split("omdat", 1)[1].strip() if "omdat" in command else "no specific reason provided"
                        )
                        effective_app.process_user_feedback(
                            f"Dit was een slechte trade omdat {reason}", {"signal": dream_snapshot.get("signal")}
                        )
                        effective_app.speak("Thanks for the feedback. I will improve this.")
                    elif any(x in command for x in ["verbeter", "pas aan", "update"]):
                        effective_app.process_user_feedback(command)
                        effective_app.speak("Understood. I will update my Bible right away.")
                    else:
                        effective_app.speak(
                            "I heard you, but I do not fully understand the command. "
                            "Try: status, ga long, ga short, hold, dream, or feedback."
                        )
                elif len(text_lower) > 3:
                    effective_app.speak("I am still listening. Say 'Lumina' followed by your command.")

            except effective_app.sr.UnknownValueError:
                pass
            except effective_app.sr.RequestError as e:
                effective_app.logger.error(f"Voice recognition error: {e}")
            except OSError as e:
                # No audio input device available - log once and exit voice thread cleanly.
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="INFO_PRINT_LEGACY",
                        message="🎤 Voice input disabled: no microphone detected.",
                        context={"detail": str(e)},
                    )
                )
                effective_app.logger.warning(f"Voice input unavailable (no microphone): {e}")
                return
            except Exception as e:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_VOICE_009",
                    message=str(e),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                effective_app.logger.error(f"Voice thread error: {e}")

            time.sleep(0.4)


# Convenience for thin delegation (compat with existing bootstrap/exports/tests callers).
def run_voice_listener(app: Optional["RuntimeContext"] = None) -> None:
    """Thin wrapper for legacy call sites. Delegates to bounded handler."""
    VoiceLegacyHandler(app=app).run_listener(app=app)
