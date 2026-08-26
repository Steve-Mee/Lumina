"""Telegram notifier for REAL DNA approval proposals.

Config priority:
1. Explicit constructor args
2. config.yaml monitoring.webhook.telegram_bot_token / telegram_chat_id
3. TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID environment variables

Fail-closed approval model:
- Any REAL promotion proposal remains blocked until Steve replies APPROVE.
- VETO reply or window expiry without APPROVE blocks promotion.
- Missing credentials returns False on send, which blocks promotion upstream.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.notifications.telegram_gateway import get_telegram_gateway
from lumina_core.notifications.telegram_journal import record_inbound, record_outbound

logger = logging.getLogger(__name__)

_NOTIFIER: Any = None
_NOTIFIER_LOCK = threading.Lock()


def _run_async(awaitable: Any) -> Any:
    """Run a coroutine from sync code without nesting into a live event loop.

    FastAPI/uvicorn already owns the thread loop. Creating a sibling loop and
    calling ``run_until_complete`` raises ``Cannot run the event loop while
    another loop is running`` and leaves the coroutine un-awaited. First
    principles: never nest — offload to a worker thread with its own loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    def _runner() -> Any:
        return asyncio.run(awaitable)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


class TelegramNotifier:
    """Send DNA promotion proposals to Steve and read APPROVE/VETO replies."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_VETOED = "vetoed"
    STATUS_EXPIRED = "expired"

    def __init__(self, veto_registry=None, api_token=None, chat_id=None):
        self._veto_registry = veto_registry
        self._api_token, self._chat_id = self._resolve_credentials(api_token=api_token, chat_id=chat_id)
        self._pending_proposals: dict[str, dict[str, Any]] = {}
        self._pending_twin_questions: dict[str, dict[str, Any]] = {}
        self._last_update_id: int = 0
        self._lock = threading.RLock()

    @staticmethod
    def _resolve_credentials(*, api_token: str | None, chat_id: str | None) -> tuple[str, str]:
        # Priority: 1) explicit constructor args, 2) top-level telegram: section,
        # 3) monitoring.webhook section, 4) environment variables.
        tg_cfg = ConfigLoader.section("telegram", default={})
        tg_cfg = tg_cfg if isinstance(tg_cfg, dict) else {}
        webhook_cfg = ConfigLoader.section("monitoring", "webhook", default={})
        if not isinstance(webhook_cfg, dict):
            webhook_cfg = {}
        token = str(
            api_token
            or tg_cfg.get("token")
            or webhook_cfg.get("telegram_bot_token")
            or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        ).strip()
        resolved_chat_id = str(
            chat_id
            or tg_cfg.get("chat_id")
            or webhook_cfg.get("telegram_chat_id")
            or os.environ.get("TELEGRAM_CHAT_ID", "")
        ).strip()
        if token.startswith("${") and token.endswith("}"):
            token = str(os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
        if resolved_chat_id.startswith("${") and resolved_chat_id.endswith("}"):
            resolved_chat_id = str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
        return token, resolved_chat_id

    def _get_bot(self):
        if not self._api_token:
            return None
        try:
            from telegram import Bot  # type: ignore
        except ImportError:
            logger.error("python-telegram-bot is not installed.")
            return None
        return Bot(token=self._api_token)

    def is_awaiting_approval(self, dna_id: str) -> bool:
        with self._lock:
            meta = self._pending_proposals.get(dna_id)
            return meta is not None and meta.get("status") == self.STATUS_PENDING

    def has_approved(self, dna_id: str) -> bool:
        with self._lock:
            meta = self._pending_proposals.get(dna_id)
            return meta is not None and meta.get("status") == self.STATUS_APPROVED

    def is_vetoed_or_expired(self, dna_id: str) -> bool:
        with self._lock:
            meta = self._pending_proposals.get(dna_id)
            if meta is None:
                return False
            status = meta.get("status", self.STATUS_PENDING)
            if status in (self.STATUS_VETOED, self.STATUS_EXPIRED):
                return True
            if status == self.STATUS_PENDING:
                try:
                    deadline = datetime.fromisoformat(meta.get("veto_deadline", ""))
                    if datetime.utcnow() > deadline:
                        meta["status"] = self.STATUS_EXPIRED
                        logger.info("DNA %s: veto window expired -> auto-VETO (fail-closed)", dna_id)
                        self._record_auto_veto(dna_id, float(meta.get("dna_fitness", 0.0)))
                        return True
                except (ValueError, KeyError):
                    pass
            return False

    def _record_auto_veto(self, dna_id: str, dna_fitness: float) -> None:
        try:
            from lumina_core.evolution.veto_registry import VetoRecord

            if self._veto_registry is None:
                return
            record = VetoRecord(
                veto_timestamp=datetime.utcnow().isoformat(),
                dna_id=dna_id,
                dna_fitness=dna_fitness,
                reason="Telegram veto window expired without APPROVE - auto-VETO (fail-closed)",
                issuer="telegram_auto_veto",
                metadata={"source": "auto_veto", "proposal_metadata": self._pending_proposals.get(dna_id, {})},
            )
            self._veto_registry.append_veto(record)
        except Exception as exc:
            logger.error("Failed to record auto-veto for %s: %s", dna_id, exc)

    def configure_workspace(self, workspace_root: Any) -> None:
        """Optional workspace for maturation phase advance replies + journal."""
        from pathlib import Path

        self._workspace_root = Path(workspace_root)
        get_telegram_gateway(workspace_root=self._workspace_root)

    def poll_for_replies(self) -> list[dict[str, Any]]:
        if not self._api_token or not self._chat_id:
            return []
        bot = self._get_bot()
        if bot is None:
            return []

        processed: list[dict[str, Any]] = []
        gateway = get_telegram_gateway(workspace_root=getattr(self, "_workspace_root", None))
        try:
            disk_offset = gateway.load_offset()
            with self._lock:
                mem_offset = self._last_update_id
            last_seen = max(disk_offset, mem_offset)
            offset = last_seen + 1 if last_seen > 0 else 0
            updates = _run_async(bot.get_updates(offset=offset, timeout=5))
            for update in updates or []:
                update_id = int(getattr(update, "update_id", 0) or 0)
                with self._lock:
                    if update_id > self._last_update_id:
                        self._last_update_id = update_id
                gateway.save_offset(update_id)
                message = getattr(update, "message", None)
                if message is None:
                    continue
                sender_chat_id = str(getattr(getattr(message, "chat", None), "id", ""))
                if sender_chat_id != self._chat_id:
                    continue
                raw_text = str(getattr(message, "text", "") or "").strip()
                if not raw_text:
                    continue
                telegram_mid = getattr(message, "message_id", None)
                mid = int(telegram_mid) if telegram_mid is not None else None
                record_inbound(
                    text=raw_text,
                    kind="operator",
                    source="telegram_poll",
                    telegram_update_id=update_id,
                    telegram_message_id=mid,
                    workspace_root=getattr(self, "_workspace_root", None),
                )
                text = raw_text.upper()
                # Twin decision feedback (OK / FIX A|V|M) before MC escalations
                twin_fb = self._try_twin_decision_feedback_reply(raw_text)
                if twin_fb is not None:
                    processed.append(
                        {
                            "update_id": update_id,
                            "action": "twin_decision_feedback",
                            "result": twin_fb,
                        }
                    )
                    continue
                # Twin MC (escalation / micro) before DNA APPROVE/VETO
                twin_mc = self._try_twin_mc_reply(raw_text)
                if twin_mc is not None:
                    processed.append(
                        {
                            "update_id": update_id,
                            "action": "twin_mc",
                            "result": twin_mc,
                        }
                    )
                    continue
                action, target_dna = self._parse_reply(text)
                if action:
                    self._apply_reply(action, target_dna)
                    processed.append({"update_id": update_id, "action": action, "dna_id": target_dna})
                    continue
                # OR5 champion freeze: ACCEPT / WIPE (remote autonomy)
                freeze_result = self._try_champion_freeze_reply(raw_text)
                if freeze_result is not None:
                    processed.append(
                        {
                            "update_id": update_id,
                            "action": "champion_freeze",
                            "result": freeze_result,
                        }
                    )
                    continue
                # Phase continuum advance: YES / CONFIRM / ADVANCE + token
                phase_result = self._try_phase_advance_reply(raw_text)
                if phase_result is not None:
                    processed.append(
                        {
                            "update_id": update_id,
                            "action": "phase_advance",
                            "result": phase_result,
                        }
                    )
                    continue
        except Exception as exc:
            logger.error("Telegram poll_for_replies error: %s", exc)
        return processed

    def _try_champion_freeze_reply(self, raw_text: str) -> dict[str, Any] | None:
        """Handle champion freeze ACCEPT/WIPE replies; returns None if not applicable."""
        try:
            from pathlib import Path

            from lumina_core.birth.champion_freeze_telegram import (
                try_handle_telegram_freeze_text,
            )

            root = getattr(self, "_workspace_root", None) or Path.cwd()
            return try_handle_telegram_freeze_text(root, raw_text, apply=True)
        except Exception as exc:
            logger.debug("Telegram champion freeze handle failed: %s", exc)
            return None

    def _try_phase_advance_reply(self, raw_text: str) -> dict[str, Any] | None:
        """Handle maturation advance replies; returns None if not applicable."""
        try:
            from pathlib import Path

            from lumina_core.maturity.advance_policy import try_handle_telegram_text

            root = getattr(self, "_workspace_root", None) or Path.cwd()
            result = try_handle_telegram_text(root, raw_text)
            if result is None:
                return None
            if result.get("ok"):
                phase = result.get("phase") or result.get("start_phase") or "next"
                self._send_telegram_message(f"Lumina: starting phase `{phase}` from Telegram confirm.")
            else:
                err = result.get("error") or "advance failed"
                self._send_telegram_message(
                    f"Lumina: phase advance failed ({err}). Open Phase Hub or check token."
                )
            return result
        except Exception as exc:
            logger.debug("Telegram phase advance handle failed: %s", exc)
            return None

    def _parse_reply(self, text: str) -> tuple[str | None, str | None]:
        parts = text.split()
        if not parts:
            return None, None
        command = parts[0]
        if command not in ("APPROVE", "VETO"):
            return None, None
        if len(parts) >= 2:
            return command, parts[1]
        with self._lock:
            pending = [
                key for key, value in self._pending_proposals.items() if value.get("status") == self.STATUS_PENDING
            ]
        return command, (pending[0] if pending else None)

    def _resolve_pending_proposal_key(self, dna_id: str | None) -> str | None:
        """Exact or prefix match so Telegram can show short DNA ids."""
        if not dna_id:
            return None
        target = str(dna_id).strip()
        if not target:
            return None
        with self._lock:
            if target in self._pending_proposals:
                return target
            # Prefix match (short id from operator message)
            for key in self._pending_proposals:
                if key.startswith(target) or target.startswith(key[: max(8, min(16, len(key)))]):
                    meta = self._pending_proposals.get(key) or {}
                    if meta.get("status") == self.STATUS_PENDING:
                        return key
            return None

    def _apply_reply(self, action: str, dna_id: str | None) -> None:
        resolved = self._resolve_pending_proposal_key(dna_id)
        if not resolved:
            logger.warning("Cannot apply %s: no target dna_id found for %s.", action, dna_id)
            return
        with self._lock:
            meta = self._pending_proposals.get(resolved)
            if meta is None or meta.get("status") != self.STATUS_PENDING:
                return
            if action == "APPROVE":
                meta["status"] = self.STATUS_APPROVED
            elif action == "VETO":
                meta["status"] = self.STATUS_VETOED
                self._record_veto_from_reply(resolved, float(meta.get("dna_fitness", 0.0)))

    def _record_veto_from_reply(self, dna_id: str, dna_fitness: float) -> None:
        try:
            from lumina_core.evolution.veto_registry import VetoRecord

            if self._veto_registry is None:
                return
            record = VetoRecord(
                veto_timestamp=datetime.utcnow().isoformat(),
                dna_id=dna_id,
                dna_fitness=dna_fitness,
                reason="Steve vetoed via Telegram VETO reply",
                issuer="telegram_steve",
                metadata={"source": "telegram_reply", "proposal_metadata": self._pending_proposals.get(dna_id, {})},
            )
            self._veto_registry.append_veto(record)
        except Exception as exc:
            logger.error("Failed to record VETO reply for %s: %s", dna_id, exc)

    def send_proposal_notification(
        self,
        dna_id: str,
        fitness: float,
        twin_confidence: float,
        proposal_summary: str,
        veto_window_minutes: int = 30,
        tags: list[str] | None = None,
        recommendation: bool | None = None,
        dashboard_url: str | None = None,
    ) -> bool:
        if not self._api_token or not self._chat_id:
            logger.warning("Telegram credentials missing. Proposal notification skipped.")
            return False
        recommendation_text = "YES" if recommendation is True else "NO" if recommendation is False else "UNKNOWN"
        cutoff_time = datetime.utcnow() + timedelta(minutes=veto_window_minutes)
        try:
            from lumina_core.evolution.twin_telegram_copy import (
                TwinOperatorBrief,
                format_dna_promotion_telegram,
            )

            message = format_dna_promotion_telegram(
                TwinOperatorBrief(
                    kind="dna_promotion",
                    message_id=str(dna_id),
                    dna_hash=str(dna_id),
                    recommendation=recommendation,
                    confidence=float(twin_confidence),
                    fitness=float(fitness),
                    proposal_summary=str(proposal_summary or ""),
                    veto_window_minutes=int(veto_window_minutes),
                    cutoff_label=cutoff_time.strftime("%H:%M UTC"),
                )
            )
            if dashboard_url:
                message += f"\n\nDashboard: {dashboard_url}"
            if tags:
                message += f"\nTags: {', '.join(tags)}"
        except Exception:
            message = (
                "LUMINA · DNA-promotie — goedkeuren of blokkeren\n"
                f"DNA: {dna_id}\n"
                f"Twin-neiging: {recommendation_text} ({twin_confidence:.0%})\n"
                f"Fitness: {fitness:.2f}\n"
                f"Samenvatting: {proposal_summary}\n"
                f"Antwoordtermijn: {veto_window_minutes} min (tot {cutoff_time.strftime('%H:%M UTC')})\n"
                f"Antwoord: APPROVE {dna_id}  of  VETO {dna_id}\n"
                "Geen antwoord = auto-VETO (fail-closed)"
            )
            if dashboard_url:
                message += f"\nDashboard: {dashboard_url}"
            if tags:
                message += f"\nTags: {', '.join(tags)}"
        success = self._send_telegram_message(
            message,
            kind="promotion",
            correlation_id=str(dna_id),
            expects_reply=True,
            source="telegram_notifier.send_proposal",
        )
        if success:
            with self._lock:
                self._pending_proposals[dna_id] = {
                    "sent_at": datetime.utcnow().isoformat(),
                    "dna_fitness": fitness,
                    "twin_confidence": twin_confidence,
                    "summary": proposal_summary,
                    "veto_window_minutes": veto_window_minutes,
                    "veto_deadline": cutoff_time.isoformat(),
                    "tags": tags or [],
                    "status": self.STATUS_PENDING,
                    "recommendation": recommendation_text,
                    "dashboard_url": dashboard_url or "",
                }
        return success

    def send_veto_confirmation(self, dna_id: str) -> bool:
        if not self._api_token or not self._chat_id:
            return True
        short = str(dna_id or "")[:12]
        return self._send_telegram_message(
            f"LUMINA · VETO genoteerd voor DNA {short}…\n"
            "Promotie is geblokkeerd (fail-closed).",
            kind="promotion",
            correlation_id=str(dna_id),
            source="telegram_notifier.veto_confirmation",
        )

    def send_veto_window_expired(self, dna_id: str) -> bool:
        if not self._api_token or not self._chat_id:
            return True
        short = str(dna_id or "")[:12]
        return self._send_telegram_message(
            f"LUMINA · Antwoordtermijn verstreken voor DNA {short}…\n"
            "Geen APPROVE ontvangen → auto-VETO (veilige kant).",
            kind="promotion",
            correlation_id=str(dna_id),
            source="telegram_notifier.veto_expired",
        )

    def send_attention_alert(
        self,
        title: str,
        body: str,
        *,
        severity: str = "high",
        kind: str = "attention",
        correlation_id: str = "",
        expects_reply: bool = False,
        source: str = "attention_notifier",
    ) -> bool:
        """Send a general Lumina attention alert (ADR-0024)."""
        if not self._api_token or not self._chat_id:
            logger.warning("Telegram attention alert skipped: credentials missing.")
            return False
        sev = str(severity or "high").strip().upper()
        message = f"LUMINA ATTENTION [{sev}] — {title}\n\n{body}"
        return self._send_telegram_message(
            message,
            kind=kind,
            correlation_id=correlation_id,
            expects_reply=expects_reply,
            source=source,
        )

    def send_milestone_alert(self, title: str, body: str) -> bool:
        """Send a positive birth milestone alert (ADR-0025)."""
        if not self._api_token or not self._chat_id:
            logger.warning("Telegram milestone alert skipped: credentials missing.")
            return False
        message = f"LUMINA MILESTONE — {title}\n\n{body}"
        return self._send_telegram_message(
            message,
            kind="milestone",
            source="milestone_notifier",
        )

    def send_message(
        self,
        message: str,
        *,
        kind: str = "operator",
        correlation_id: str = "",
        expects_reply: bool = False,
        source: str = "",
    ) -> bool:
        """Public plain-text send (Twin resolution acks, micro notices)."""
        return self._send_telegram_message(
            str(message or ""),
            kind=kind,
            correlation_id=correlation_id,
            expects_reply=expects_reply,
            source=source or "telegram_notifier.send_message",
        )

    def send_twin_mc_question(
        self,
        *,
        pending_id: str,
        question: dict[str, Any],
        resolve_token: str,
        kind: str = "escalation",
    ) -> bool:
        """Send Twin multiple-choice question (dual-channel). Base curriculum must never call this."""
        kind_l = str(kind or "").strip().lower()
        policy = str(question.get("channel_policy") or "").strip().lower()
        # Hard fail-closed: base curriculum is app-only (Operator Vault).
        if kind_l in {"base", "base_training", "curriculum"} or policy == "app_only":
            logger.warning(
                "Refusing Telegram for Twin base/app_only question pending=%s kind=%s policy=%s",
                pending_id,
                kind_l,
                policy,
            )
            return False
        try:
            from lumina_core.evolution.twin_telegram_copy import (
                TwinOperatorBrief,
                format_escalation_telegram,
            )

            conf_raw = question.get("metrics_hint") or ""
            conf = 0.0
            # metrics_hint often "conf=0.55 flags=..."
            try:
                import re as _re

                m = _re.search(r"conf\s*=\s*([0-9.]+)", str(conf_raw))
                if m:
                    conf = float(m.group(1))
            except (TypeError, ValueError):
                conf = 0.0
            brief = TwinOperatorBrief(
                kind="escalation" if kind_l == "escalation" else kind_l or "micro",
                message_id=str(pending_id),
                dna_hash=str(question.get("context_dna_hash") or ""),
                confidence=conf,
                explanation=str(question.get("scenario") or "")[:400],
                choices=list(question.get("choices") or []),
            )
            # Prefer full scenario already in base_v4 when present
            scenario = str(question.get("scenario") or "").strip()
            if scenario and "Live data:" in scenario:
                lines = [
                    "LUMINA · Twin is onzeker — jouw oordeel nodig"
                    if kind_l == "escalation"
                    else f"LUMINA · Twin oefening [{kind}]",
                    scenario,
                    "",
                ]
                for c in question.get("choices") or []:
                    if not isinstance(c, dict):
                        continue
                    cid = str(c.get("id") or "?").strip()
                    label = str(c.get("label") or "").strip()
                    parts = label.split("\n")
                    lines.append(f"{cid} — {parts[0]}")
                    for extra in parts[1:]:
                        e = extra.strip()
                        if e:
                            lines.append(f"   {e}")
                    lines.append("")
                token_short = str(resolve_token or pending_id)[:10]
                lines.append(f"Antwoord: A  of  TWIN {token_short} A")
                body = "\n".join(lines).rstrip()
            else:
                body = format_escalation_telegram(brief)
        except Exception:
            scenario = str(question.get("scenario") or "")[:600]
            lines = [
                f"LUMINA Twin [{kind}] id={pending_id[:10]}",
                scenario,
                "",
            ]
            for c in question.get("choices") or []:
                if isinstance(c, dict):
                    lines.append(f"{c.get('id')}: {c.get('label')}")
            token_short = str(resolve_token or "")[:10]
            lines.append("")
            lines.append(f"Antwoord: A / B / C / D (optioneel: {token_short})")
            lines.append(f"TWIN {pending_id[:10]} A")
            body = "\n".join(lines)
        journal_kind = "twin_escalation" if kind_l == "escalation" else "twin_micro"
        ok = self._send_telegram_message(
            body,
            kind=journal_kind,
            correlation_id=str(pending_id),
            expects_reply=True,
            source="telegram_notifier.send_twin_mc_question",
        )
        if ok:
            with self._lock:
                self._pending_twin_questions[pending_id] = {
                    "kind": kind,
                    "resolve_token": resolve_token,
                    "status": "pending",
                    "question": question,
                }
        return ok

    def send_twin_resolution(self, *, escalation_id: str, message: str) -> bool:
        return self._send_telegram_message(
            str(message or f"Twin {escalation_id} resolved"),
            kind="ack",
            correlation_id=str(escalation_id),
            source="telegram_notifier.send_twin_resolution",
        )

    def _try_twin_decision_feedback_reply(self, raw_text: str) -> dict[str, Any] | None:
        """Parse OK|FIX A/V/M on Twin decision feed messages."""
        try:
            from lumina_core.evolution.twin_decision_notify import (
                apply_decision_feedback,
                parse_decision_feedback_text,
            )

            parsed = parse_decision_feedback_text(raw_text)
            if parsed is None:
                return None
            action = str(parsed.get("action") or "OK")
            # Map FIX_A → A for apply_decision_feedback
            if action.startswith("FIX_"):
                letter = action.replace("FIX_", "")[:1]
                action = letter
            return apply_decision_feedback(
                str(parsed.get("decision_id") or ""),
                action=action,
                notes=str(parsed.get("notes") or ""),
                resolved_by="telegram",
            )
        except Exception as exc:
            logger.error("Twin decision feedback telegram parse failed: %s", exc)
            return {"error": str(exc)}

    def _try_twin_mc_reply(self, raw_text: str) -> dict[str, Any] | None:
        """Parse TWIN <id> A|B|C|D [token] or bare A/B/C/D when one pending."""
        text = str(raw_text or "").strip()
        if not text:
            return None
        upper = text.upper()
        pending_id = ""
        choice = ""
        token = ""
        # Format: TWIN <id> A [token]
        parts = text.split()
        if upper.startswith("TWIN") and len(parts) >= 3:
            pending_id = parts[1].strip()
            choice = parts[2].strip().upper()[:1]
            if len(parts) >= 4:
                token = parts[3].strip()
        elif upper in {"A", "B", "C", "D"} or upper.startswith(("A ", "B ", "C ", "D ")):
            choice = upper[0]
            pending_id = self._single_open_twin_pending_id()
            if not pending_id:
                return None
        else:
            return None
        if choice not in {"A", "B", "C", "D"} or not pending_id:
            return None
        # Resolve via training service
        try:
            from lumina_core.evolution.twin_pending_store import TwinPendingStore
            from lumina_core.evolution.twin_training_service import TwinTrainingService

            svc = TwinTrainingService()
            store = TwinPendingStore()
            rec = store.get_by_prefix(pending_id)
            full_id = rec.pending_id if rec is not None else pending_id
            kind = str(rec.kind if rec is not None else "")
            if not kind:
                with self._lock:
                    meta = dict(self._pending_twin_questions.get(full_id) or {})
                kind = str(meta.get("kind") or "escalation")
            tok = token or None
            if kind == "decision_feedback":
                from lumina_core.evolution.twin_decision_notify import apply_decision_feedback

                map_act = {"A": "A", "B": "V", "C": "M", "D": "OK"}.get(choice, choice)
                result = apply_decision_feedback(
                    full_id,
                    action=map_act,
                    resolved_by="telegram",
                )
            elif kind == "micro":
                result = svc.submit_micro(
                    pending_id=full_id,
                    choice_id=choice,
                    resolved_by="telegram",
                    resolve_token=tok,
                )
            else:
                result = svc.resolve_escalation(
                    full_id,
                    choice_id=choice,
                    resolved_by="telegram",
                    resolve_token=tok,
                )
            with self._lock:
                if full_id in self._pending_twin_questions:
                    self._pending_twin_questions[full_id]["status"] = "resolved"
            return {"pending_id": full_id, "choice": choice, "result": result}
        except Exception as exc:
            logger.error("Twin MC telegram resolve failed: %s", exc)
            return {"error": str(exc), "pending_id": pending_id, "choice": choice}

    def _single_open_twin_pending_id(self) -> str:
        try:
            from lumina_core.evolution.twin_pending_store import TwinPendingStore

            open_recs = TwinPendingStore().list_pending()
            if len(open_recs) == 1:
                return str(open_recs[0].pending_id)
        except Exception:
            logger.debug("twin pending store lookup failed", exc_info=True)
        with self._lock:
            pending_items = [
                (k, v)
                for k, v in self._pending_twin_questions.items()
                if v.get("status") == "pending"
            ]
        if len(pending_items) == 1:
            return str(pending_items[0][0])
        return ""

    def _send_telegram_message(
        self,
        message: str,
        dna_id: str | None = None,
        *,
        kind: str = "operator",
        correlation_id: str = "",
        expects_reply: bool = False,
        source: str = "",
    ) -> bool:
        del dna_id
        workspace = getattr(self, "_workspace_root", None)
        gateway = get_telegram_gateway(workspace_root=workspace)
        if not self._api_token or not self._chat_id:
            record_outbound(
                text=str(message or ""),
                kind=kind,
                correlation_id=correlation_id,
                expects_reply=expects_reply,
                source=source or "telegram_notifier",
                delivered=False,
                drop_reason="no_credentials",
                workspace_root=workspace,
            )
            return False
        bot = self._get_bot()
        if bot is None:
            record_outbound(
                text=str(message or ""),
                kind=kind,
                correlation_id=correlation_id,
                expects_reply=expects_reply,
                source=source or "telegram_notifier",
                delivered=False,
                drop_reason="no_bot",
                workspace_root=workspace,
            )
            return False
        allowed, drop_reason = gateway.try_reserve_send(kind)
        if not allowed:
            record_outbound(
                text=str(message or ""),
                kind=kind,
                correlation_id=correlation_id,
                expects_reply=expects_reply,
                source=source or "telegram_notifier",
                delivered=False,
                drop_reason=drop_reason,
                workspace_root=workspace,
            )
            return False
        try:
            result = _run_async(bot.send_message(chat_id=self._chat_id, text=message))
            mid_raw = getattr(result, "message_id", None) if result is not None else None
            mid = int(mid_raw) if mid_raw is not None else None
            ok = result is not None
            record_outbound(
                text=str(message or ""),
                kind=kind,
                correlation_id=correlation_id,
                expects_reply=expects_reply,
                source=source or "telegram_notifier",
                delivered=ok,
                drop_reason=None if ok else "api_error",
                telegram_message_id=mid,
                workspace_root=workspace,
            )
            return ok
        except Exception as exc:
            logger.error("Telegram API error: %s", exc)
            record_outbound(
                text=str(message or ""),
                kind=kind,
                correlation_id=correlation_id,
                expects_reply=expects_reply,
                source=source or "telegram_notifier",
                delivered=False,
                drop_reason="api_error",
                workspace_root=workspace,
            )
            return False

    def record_veto(self, dna_id: str, dna_fitness: float, reason: str = "Steve vetoed via Telegram") -> bool:
        if not self._veto_registry:
            logger.warning("No VetoRegistry configured. Veto not persisted.")
            return False
        try:
            from lumina_core.evolution.veto_registry import VetoRecord

            record = VetoRecord(
                veto_timestamp=datetime.utcnow().isoformat(),
                dna_id=dna_id,
                dna_fitness=dna_fitness,
                reason=reason,
                issuer="telegram_steve",
                metadata={"source": "telegram", "proposal_metadata": self._pending_proposals.get(dna_id, {})},
            )
            self._veto_registry.append_veto(record)
            with self._lock:
                self._pending_proposals.pop(dna_id, None)
            return True
        except Exception as exc:
            logger.error("Failed to record veto: %s", exc)
            return False

    def cleanup_expired_proposals(self, window_seconds: int = 1800) -> None:
        now = datetime.utcnow()
        with self._lock:
            for dna_id, metadata in list(self._pending_proposals.items()):
                if metadata.get("status") != self.STATUS_PENDING:
                    continue
                try:
                    deadline = datetime.fromisoformat(metadata["veto_deadline"])
                    if now > deadline:
                        metadata["status"] = self.STATUS_EXPIRED
                        self._record_auto_veto(dna_id, float(metadata.get("dna_fitness", 0.0)))
                except (KeyError, ValueError):
                    continue


__all__ = ["TelegramNotifier", "get_telegram_notifier", "reset_telegram_notifier_for_tests"]


def get_telegram_notifier() -> TelegramNotifier:
    global _NOTIFIER
    with _NOTIFIER_LOCK:
        if _NOTIFIER is None:
            _NOTIFIER = TelegramNotifier()
        return _NOTIFIER


def reset_telegram_notifier_for_tests() -> None:
    global _NOTIFIER
    with _NOTIFIER_LOCK:
        _NOTIFIER = None
