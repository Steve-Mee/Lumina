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
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any

from lumina_core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


def _run_async(awaitable: Any) -> Any:
	try:
		asyncio.get_running_loop()
	except RuntimeError:
		return asyncio.run(awaitable)

	loop = asyncio.new_event_loop()
	try:
		return loop.run_until_complete(awaitable)
	finally:
		loop.close()


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
		self._last_update_id: int = 0
		self._lock = threading.RLock()

	@staticmethod
	def _resolve_credentials(*, api_token: str | None, chat_id: str | None) -> tuple[str, str]:
		webhook_cfg = ConfigLoader.section("monitoring", "webhook", default={})
		if not isinstance(webhook_cfg, dict):
			webhook_cfg = {}
		token = str(
			api_token
			or webhook_cfg.get("telegram_bot_token")
			or os.environ.get("TELEGRAM_BOT_TOKEN", "")
		).strip()
		resolved_chat_id = str(
			chat_id
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

	def poll_for_replies(self) -> list[dict[str, Any]]:
		if not self._api_token or not self._chat_id:
			return []
		bot = self._get_bot()
		if bot is None:
			return []

		processed: list[dict[str, Any]] = []
		try:
			with self._lock:
				offset = self._last_update_id + 1 if self._last_update_id > 0 else 0
			updates = _run_async(bot.get_updates(offset=offset, timeout=5))
			for update in updates or []:
				update_id = int(getattr(update, "update_id", 0) or 0)
				with self._lock:
					if update_id > self._last_update_id:
						self._last_update_id = update_id
				message = getattr(update, "message", None)
				if message is None:
					continue
				sender_chat_id = str(getattr(getattr(message, "chat", None), "id", ""))
				if sender_chat_id != self._chat_id:
					continue
				text = str(getattr(message, "text", "") or "").strip().upper()
				action, target_dna = self._parse_reply(text)
				if action:
					self._apply_reply(action, target_dna)
					processed.append({"update_id": update_id, "action": action, "dna_id": target_dna})
		except Exception as exc:
			logger.error("Telegram poll_for_replies error: %s", exc)
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
			pending = [key for key, value in self._pending_proposals.items() if value.get("status") == self.STATUS_PENDING]
		return command, (pending[0] if pending else None)

	def _apply_reply(self, action: str, dna_id: str | None) -> None:
		if not dna_id:
			logger.warning("Cannot apply %s: no target dna_id found.", action)
			return
		with self._lock:
			meta = self._pending_proposals.get(dna_id)
			if meta is None or meta.get("status") != self.STATUS_PENDING:
				return
			if action == "APPROVE":
				meta["status"] = self.STATUS_APPROVED
			elif action == "VETO":
				meta["status"] = self.STATUS_VETOED
				self._record_veto_from_reply(dna_id, float(meta.get("dna_fitness", 0.0)))

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
		message = (
			"DNA Promotion Proposal\n"
			f"DNA ID: {dna_id}\n"
			f"Recommendation: {recommendation_text} ({twin_confidence:.1%} confidence)\n"
			f"Fitness: {fitness:.2f}\n"
			f"Summary: {proposal_summary}\n"
			f"Veto Window: {veto_window_minutes} min (until {cutoff_time.strftime('%H:%M UTC')})\n"
			f"Reply APPROVE {dna_id} to allow or VETO {dna_id} to block.\n"
			"WARNING: No reply = auto-VETO (fail-closed)"
		)
		if dashboard_url:
			message += f"\nDashboard: {dashboard_url}"
		if tags:
			message += f"\nTags: {', '.join(tags)}"
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
					"recommendation": recommendation_text,
					"dashboard_url": dashboard_url or "",
				}
		return success

	def send_veto_confirmation(self, dna_id: str) -> bool:
		if not self._api_token or not self._chat_id:
			return True
		return self._send_telegram_message(f"Veto recorded for DNA {dna_id}. Promotion blocked.")

	def send_veto_window_expired(self, dna_id: str) -> bool:
		if not self._api_token or not self._chat_id:
			return True
		return self._send_telegram_message(f"Veto window expired for DNA {dna_id}. Proceeding.")

	def _send_telegram_message(self, message: str, dna_id: str | None = None) -> bool:
		del dna_id
		if not self._api_token or not self._chat_id:
			return False
		bot = self._get_bot()
		if bot is None:
			return False
		try:
			result = _run_async(bot.send_message(chat_id=self._chat_id, text=message))
			return result is not None
		except Exception as exc:
			logger.error("Telegram API error: %s", exc)
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


__all__ = ["TelegramNotifier"]
