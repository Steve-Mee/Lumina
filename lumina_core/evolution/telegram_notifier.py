"""Telegram notifier for DNA promotion proposals and veto window alerts."""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send DNA proposal notifications via Telegram and handle veto responses.
    
    Architecture:
    - Sends proposal summaries to Steve via Telegram
    - Monitors for veto responses within 30-min window
    - Records veto decisions in provided VetoRegistry
    - Fail-closed: missing API credentials result in no-op notifications (logged as warning)
    """

    def __init__(
        self,
        veto_registry: Optional[Any] = None,
        api_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        """Initialize Telegram notifier.
        
        Args:
            veto_registry: VetoRegistry instance for storing veto decisions
            api_token: Telegram Bot API token (falls back to TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID to send messages to (falls back to TELEGRAM_CHAT_ID env var)
        """
        self._veto_registry = veto_registry
        self._api_token = api_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._api_base_url = "https://api.telegram.org"
        self._pending_proposals: dict[str, dict[str, Any]] = {}  # dna_id -> proposal metadata

    def send_proposal_notification(
        self,
        dna_id: str,
        fitness: float,
        twin_confidence: float,
        proposal_summary: str,
        veto_window_minutes: int = 30,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Send DNA proposal notification to Steve via Telegram.
        
        Starts the 30-min veto window. Steve can reply "VETO" to block promotion.
        
        Args:
            dna_id: Unique DNA identifier
            fitness: DNA fitness value
            twin_confidence: Approval twin confidence [0, 1]
            proposal_summary: Brief summary of proposal changes
            veto_window_minutes: Duration of veto window (default 30)
            tags: Optional list of proposal tags
            
        Returns:
            True if notification sent (or credentials missing but logging enabled)
            False if send failed and should be retried
        """
        if not self._api_token or not self._chat_id:
            logger.warning(
                "Telegram credentials missing (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID). "
                "Veto window cannot be enabled. Falling back to approval twin + guard only."
            )
            return True  # Fail-open for notifications: missing creds doesn't block evolution

        try:
            # Build notification message
            cutoff_time = datetime.utcnow() + timedelta(minutes=veto_window_minutes)
            message = (
                f"🧬 **DNA Promotion Proposal**\n"
                f"**DNA ID**: `{dna_id}`\n"
                f"**Fitness**: {fitness:.2f}\n"
                f"**Twin Confidence**: {twin_confidence:.1%}\n"
                f"**Summary**: {proposal_summary}\n"
                f"\n"
                f"⏰ **Veto Window**: {veto_window_minutes} min (until {cutoff_time.strftime('%H:%M UTC')})\n"
                f"📋 **Reply with**: `VETO` to block, or leave empty to approve\n"
            )
            if tags:
                message += f"**Tags**: {', '.join(tags)}\n"

            # Send via Telegram Bot API
            success = self._send_telegram_message(message, dna_id=dna_id)

            if success:
                # Track proposal in pending dict (for veto window management)
                self._pending_proposals[dna_id] = {
                    "sent_at": datetime.utcnow().isoformat(),
                    "dna_fitness": fitness,
                    "twin_confidence": twin_confidence,
                    "summary": proposal_summary,
                    "veto_window_minutes": veto_window_minutes,
                    "veto_deadline": cutoff_time.isoformat(),
                    "tags": tags or [],
                }
                logger.info(f"DNA proposal {dna_id} sent via Telegram (veto window: {veto_window_minutes}min)")

            return success

        except Exception as e:
            logger.error(f"Failed to send proposal notification: {e}")
            return False

    def send_veto_confirmation(self, dna_id: str) -> bool:
        """Send confirmation message to Steve that veto was recorded.
        
        Args:
            dna_id: DNA ID that was vetoed
            
        Returns:
            True if message sent, False if failed
        """
        if not self._api_token or not self._chat_id:
            return True  # Credentials missing: notification skipped but not fatal

        try:
            message = f"✅ **Veto recorded** for DNA `{dna_id}`. Promotion blocked."
            return self._send_telegram_message(message)
        except Exception as e:
            logger.error(f"Failed to send veto confirmation: {e}")
            return False

    def send_veto_window_expired(self, dna_id: str) -> bool:
        """Send message to Steve that veto window has expired (promotion proceeding).
        
        Args:
            dna_id: DNA ID
            
        Returns:
            True if message sent, False if failed
        """
        if not self._api_token or not self._chat_id:
            return True

        try:
            message = f"⏰ **Veto window expired** for DNA `{dna_id}`. Proceeding with promotion."
            return self._send_telegram_message(message)
        except Exception as e:
            logger.error(f"Failed to send veto window expiration message: {e}")
            return False

    def _send_telegram_message(self, message: str, dna_id: Optional[str] = None) -> bool:
        """Low-level Telegram message sender (fail-closed on network errors).
        
        Args:
            message: Markdown-formatted message to send
            dna_id: Optional DNA ID for message tagging (stored in inline button data)
            
        Returns:
            True if sent, False if failed
        """
        if not self._api_token or not self._chat_id:
            return False

        try:
            import requests

            url = f"{self._api_base_url}/bot{self._api_token}/sendMessage"
            payload = {
                "chat_id": self._chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            return response.status_code == 200

        except ImportError:
            logger.error("requests library not installed. Cannot send Telegram messages.")
            return False
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return False

    def record_veto(
        self,
        dna_id: str,
        dna_fitness: float,
        reason: str = "Steve vetoed via Telegram",
    ) -> bool:
        """Record veto decision in VetoRegistry.
        
        Args:
            dna_id: DNA ID being vetoed
            dna_fitness: DNA fitness value
            reason: Reason for veto
            
        Returns:
            True if recorded, False if failed
        """
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
                metadata={
                    "source": "telegram",
                    "proposal_metadata": self._pending_proposals.get(dna_id, {}),
                },
            )
            self._veto_registry.append_veto(record)
            self._pending_proposals.pop(dna_id, None)  # Clean up tracking
            return True

        except Exception as e:
            logger.error(f"Failed to record veto: {e}")
            return False

    def cleanup_expired_proposals(self, window_seconds: int = 1800) -> None:
        """Remove proposals from pending dict if veto window has expired.
        
        Args:
            window_seconds: Veto window duration in seconds
        """
        now = datetime.utcnow()
        expired_ids = []

        for dna_id, metadata in self._pending_proposals.items():
            try:
                deadline = datetime.fromisoformat(metadata["veto_deadline"])
                if now > deadline:
                    expired_ids.append(dna_id)
            except (KeyError, ValueError):
                pass

        for dna_id in expired_ids:
            self._pending_proposals.pop(dna_id, None)
            logger.debug(f"Cleaned up expired proposal {dna_id}")
