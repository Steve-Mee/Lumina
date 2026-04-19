"""Telegram notifier for DNA promotion proposals and veto window alerts.

Fail-closed approval model:
- When a proposal is sent, DNA is immediately marked PENDING APPROVAL.
- Steve must reply APPROVE within the veto window to allow promotion.
- VETO reply OR window expiry WITHOUT APPROVE -> promotion blocked (fail-closed).
- Missing credentials -> send returns False (no approval possible).
"""

import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send DNA promotion proposals to Steve via Telegram and read APPROVE/VETO replies.

    Fail-closed: no reply within 30 minutes = automatic VETO (blocked).
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_VETOED = "vetoed"
    STATUS_EXPIRED = "expired"

    def __init__(self, veto_registry=None, api_token=None, chat_id=None):
        self._veto_registry = veto_registry
        self._api_token = api_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._api_base_url = "https://api.telegram.org"
        self._pending_proposals: dict[str, dict[str, Any]] = {}
        self._last_update_id: int = 0
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Fail-closed approval state queries
    # ------------------------------------------------------------------

    def is_awaiting_approval(self, dna_id: str) -> bool:
        """Return True if a proposal was sent and Steve has not replied yet."""
        with self._lock:
            meta = self._pending_proposals.get(dna_id)
            if meta is None:
                return False
            return meta.get("status") == self.STATUS_PENDING

    def has_approved(self, dna_id: str) -> bool:
        """Return True if Steve explicitly approved this DNA via Telegram."""
        with self._lock:
            meta = self._pending_proposals.get(dna_id)
            if meta is None:
                return False
            return meta.get("status") == self.STATUS_APPROVED

    def is_vetoed_or_expired(self, dna_id: str) -> bool:
        """Return True if DNA is vetoed or window expired without APPROVE (fail-closed)."""
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
                        logger.info(f"DNA {dna_id}: veto window expired -> auto-VETO (fail-closed)")
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
        except Exception as e:
            logger.error(f"Failed to record auto-veto for {dna_id}: {e}")

    # ------------------------------------------------------------------
    # Telegram get_updates polling
    # ------------------------------------------------------------------

    def poll_for_replies(self) -> list[dict[str, Any]]:
        """Poll Telegram getUpdates for APPROVE/VETO messages from Steve."""
        if not self._api_token or not self._chat_id:
            return []
        processed: list[dict[str, Any]] = []
        try:
            import requests
            url = f"{self._api_base_url}/bot{self._api_token}/getUpdates"
            with self._lock:
                offset = self._last_update_id + 1 if self._last_update_id > 0 else 0
            params: dict[str, Any] = {"timeout": 5}
            if offset > 0:
                params["offset"] = offset
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                return []
            for update in data.get("result", []):
                update_id = int(update.get("update_id", 0))
                with self._lock:
                    if update_id > self._last_update_id:
                        self._last_update_id = update_id
                message = update.get("message", {})
                text = str(message.get("text", "")).strip()
                sender_chat_id = str(message.get("chat", {}).get("id", ""))
                if sender_chat_id != self._chat_id:
                    continue
                action, target_dna = self._parse_reply(text.upper())
                if action:
                    self._apply_reply(action, target_dna)
                    processed.append({"update_id": update_id, "action": action, "dna_id": target_dna})
        except Exception as e:
            logger.error(f"Telegram poll_for_replies error: {e}")
        return processed

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
            pending = [k for k, v in self._pending_proposals.items() if v.get("status") == self.STATUS_PENDING]
        return command, (pending[0] if pending else None)

    def _apply_reply(self, action: str, dna_id: str | None) -> None:
        if not dna_id:
            logger.warning(f"Cannot apply {action}: no target dna_id found.")
            return
        with self._lock:
            meta = self._pending_proposals.get(dna_id)
            if meta is None:
                logger.warning(f"DNA {dna_id} not in pending proposals. Reply ignored.")
                return
            if meta.get("status") != self.STATUS_PENDING:
                logger.warning(f"DNA {dna_id} already resolved. Reply ignored.")
                return
            if action == "APPROVE":
                meta["status"] = self.STATUS_APPROVED
                logger.info(f"DNA {dna_id}: APPROVED by Steve via Telegram")
                self._send_telegram_message(f"DNA {dna_id} promotion APPROVED. Proceeding.")
            elif action == "VETO":
                meta["status"] = self.STATUS_VETOED
                logger.info(f"DNA {dna_id}: VETOED by Steve via Telegram")
                self._record_veto_from_reply(dna_id, float(meta.get("dna_fitness", 0.0)))
                self._send_telegram_message(f"DNA {dna_id} promotion VETOED. Blocked.")

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
        except Exception as e:
            logger.error(f"Failed to record VETO reply for {dna_id}: {e}")

    # ------------------------------------------------------------------
    # Send methods
    # ------------------------------------------------------------------

    def send_proposal_notification(
        self,
        dna_id: str,
        fitness: float,
        twin_confidence: float,
        proposal_summary: str,
        veto_window_minutes: int = 30,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Send DNA proposal notification to Steve via Telegram (fail-closed)."""
        if not self._api_token or not self._chat_id:
            logger.warning("Telegram credentials missing. Proposal notification skipped.")
            return False
        try:
            cutoff_time = datetime.utcnow() + timedelta(minutes=veto_window_minutes)
            message = (
                f"DNA Promotion Proposal\n"
                f"DNA ID: {dna_id}\n"
                f"Fitness: {fitness:.2f}\n"
                f"Twin Confidence: {twin_confidence:.1%}\n"
                f"Summary: {proposal_summary}\n"
                f"Veto Window: {veto_window_minutes} min (until {cutoff_time.strftime('%H:%M UTC')})\n"
                f"Reply APPROVE {dna_id} to allow or VETO {dna_id} to block.\n"
                f"WARNING: No reply = auto-VETO (fail-closed)\n"
            )
            if tags:
                message += f"Tags: {', '.join(tags)}\n"
            success = self._send_telegram_message(message)
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
                    }
                logger.info(f"DNA proposal {dna_id} sent via Telegram (veto window: {veto_window_minutes}min)")
            return success
        except Exception as e:
            logger.error(f"Failed to send proposal notification: {e}")
            return False

    def send_veto_confirmation(self, dna_id: str) -> bool:
        if not self._api_token or not self._chat_id:
            return True
        try:
            return self._send_telegram_message(f"Veto recorded for DNA {dna_id}. Promotion blocked.")
        except Exception as e:
            logger.error(f"Failed to send veto confirmation: {e}")
            return False

    def send_veto_window_expired(self, dna_id: str) -> bool:
        if not self._api_token or not self._chat_id:
            return True
        try:
            return self._send_telegram_message(f"Veto window expired for DNA {dna_id}. Proceeding.")
        except Exception as e:
            logger.error(f"Failed to send veto window expiration message: {e}")
            return False

    def _send_telegram_message(self, message: str, dna_id: Optional[str] = None) -> bool:
        if not self._api_token or not self._chat_id:
            return False
        try:
            import requests
            url = f"{self._api_base_url}/bot{self._api_token}/sendMessage"
            payload = {"chat_id": self._chat_id, "text": message, "parse_mode": "Markdown"}
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.status_code == 200
        except ImportError:
            logger.error("requests library not installed.")
            return False
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
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
        except Exception as e:
            logger.error(f"Failed to record veto: {e}")
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
                        logger.info(f"DNA {dna_id}: auto-expired (fail-closed)")
                        self._record_auto_veto(dna_id, float(metadata.get("dna_fitness", 0.0)))
                except (KeyError, ValueError):
                    pass
