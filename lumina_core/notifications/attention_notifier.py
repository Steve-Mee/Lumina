"""Unified attention notification dispatcher (Telegram + progress fields)."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.notifications.attention_events import AttentionEvent, AttentionSeverity
from lumina_core.notifications.notification_scheduler import NotificationScheduler
from lumina_core.notifications.telegram_notifier import TelegramNotifier

logger = logging.getLogger("lumina.notifications.attention")

_INSTANCE: AttentionNotifier | None = None
_INSTANCE_LOCK = threading.Lock()


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class AttentionNotifier:
    """Route attention events to Telegram with dedupe and waking-hours scheduling."""

    def __init__(
        self,
        *,
        workspace_root: Path | str | None = None,
        telegram: TelegramNotifier | None = None,
        scheduler: NotificationScheduler | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        tg_cfg = ConfigLoader.section("telegram", default={})
        tg_cfg = tg_cfg if isinstance(tg_cfg, dict) else {}
        self._enabled = _coerce_bool(tg_cfg.get("attention_alerts_enabled"), True)
        self._dedupe_sec = max(60, _coerce_int(tg_cfg.get("attention_dedupe_sec"), 1800))
        self._critical_bypass = _coerce_bool(tg_cfg.get("attention_critical_bypass_quiet_hours"), True)
        waking_start = _coerce_int(tg_cfg.get("waking_hour_start"), 8)
        waking_end = _coerce_int(tg_cfg.get("waking_hour_end"), 22)
        self._telegram = telegram or TelegramNotifier()
        self._scheduler = scheduler or NotificationScheduler(
            waking_hour_start=waking_start,
            waking_hour_end=waking_end,
        )
        self._lock = threading.RLock()
        self._dedupe_path = self._workspace_root / "state" / "attention_dedupe.json"

    def notify(self, event: AttentionEvent, *, workspace_root: Path | str | None = None) -> bool:
        """Send attention alert if enabled and not deduped. Updates progress attention fields."""
        if workspace_root is not None:
            self._workspace_root = Path(workspace_root)
            self._dedupe_path = self._workspace_root / "state" / "attention_dedupe.json"

        self._write_progress_attention(event)

        if not self._enabled:
            logger.debug("attention.disabled reason=%s", event.reason_code)
            return False

        if self._is_deduped(event):
            logger.debug("attention.deduped key=%s", event.dedupe_key)
            return False

        bypass_quiet = (
            self._critical_bypass and event.severity == AttentionSeverity.CRITICAL
        )

        def _send() -> bool:
            ok = self._telegram.send_attention_alert(
                event.title,
                event.telegram_body(),
                severity=event.severity.value,
            )
            if ok:
                self._record_dedupe(event)
            return ok

        if bypass_quiet:
            sent = _send()
            logger.info(
                "attention.sent critical=%s reason=%s sent=%s",
                event.reason_code,
                event.title,
                sent,
            )
            return sent

        result = self._scheduler.schedule_notification(
            callback=_send,
            description=f"attention:{event.dedupe_key}",
        )
        if result.get("sent_now"):
            logger.info("attention.sent reason=%s", event.reason_code)
            return bool(result.get("sent_now"))
        logger.info(
            "attention.scheduled reason=%s for=%s",
            event.reason_code,
            result.get("scheduled_for"),
        )
        return bool(result.get("accepted"))

    def _write_progress_attention(self, event: AttentionEvent) -> None:
        if event.category.value != "birth":
            return
        if event.reason_code == "birth_interrupted":
            from lumina_core.birth.checkpoint import read_checkpoint_payload

            if read_checkpoint_payload(self._workspace_root):
                logger.debug(
                    "attention.skip_progress_write reason=recoverable_checkpoint reason_code=%s",
                    event.reason_code,
                )
                return
        try:
            from lumina_core.birth.progress import (
                merge_birth_progress_extra,
                read_birth_progress,
                write_birth_progress,
            )

            prev = read_birth_progress(self._workspace_root)
            attention_fields = {
                "needs_attention": True,
                "attention_reason_code": event.reason_code,
                "attention_summary": event.summary,
                "attention_recommended_actions": list(event.recommended_actions),
                "attention_notified_at": datetime.now(timezone.utc).isoformat(),
            }
            merged = merge_birth_progress_extra(prev, attention_fields)
            # Raptor v9: do not pass keys already set as explicit kwargs.
            reserved = {
                "stage",
                "phase",
                "message",
                "progress_pct",
                "cumulative_trades",
                "trades_done",
                "total_trades",
                "target_trades",
                "ppo_steps",
                "birth_start_time",
                "timestamp",
                "elapsed_sec",
            }
            extra = {k: v for k, v in merged.items() if k not in reserved}
            write_birth_progress(
                self._workspace_root,
                stage=str(prev.get("stage", "attention") or "attention"),
                phase=str(prev.get("phase", "attention") or "attention"),
                message=str(prev.get("message") or event.summary),
                progress_pct=float(prev.get("progress_pct", 0) or 0),
                cumulative_trades=int(
                    prev.get("cumulative_trades", prev.get("trades_done", 0)) or 0
                ),
                target_trades=int(prev.get("target_trades", 0) or 0),
                ppo_steps=int(prev.get("ppo_steps", 0) or 0),
                birth_start_time=float(prev.get("birth_start_time", 0) or 0),
                **extra,
            )
        except Exception as exc:
            logger.warning("attention.progress_write_failed: %s", exc)

    def _load_dedupe(self) -> dict[str, float]:
        if not self._dedupe_path.is_file():
            return {}
        try:
            raw = json.loads(self._dedupe_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {str(k): float(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return {}

    def _save_dedupe(self, data: dict[str, float]) -> None:
        self._dedupe_path.parent.mkdir(parents=True, exist_ok=True)
        self._dedupe_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")

    def _is_deduped(self, event: AttentionEvent) -> bool:
        with self._lock:
            store = self._load_dedupe()
            last = store.get(event.dedupe_key, 0.0)
            return (time.time() - last) < float(self._dedupe_sec)

    def _record_dedupe(self, event: AttentionEvent) -> None:
        with self._lock:
            store = self._load_dedupe()
            store[event.dedupe_key] = time.time()
            # prune old entries
            cutoff = time.time() - max(self._dedupe_sec * 4, 86400)
            store = {k: v for k, v in store.items() if v >= cutoff}
            self._save_dedupe(store)


def get_attention_notifier(*, workspace_root: Path | str | None = None) -> AttentionNotifier:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = AttentionNotifier(workspace_root=workspace_root)
        elif workspace_root is not None:
            _INSTANCE._workspace_root = Path(workspace_root)
            _INSTANCE._dedupe_path = _INSTANCE._workspace_root / "state" / "attention_dedupe.json"
        return _INSTANCE


def notify_attention(event: AttentionEvent, *, workspace_root: Path | str | None = None) -> bool:
    return get_attention_notifier(workspace_root=workspace_root).notify(event, workspace_root=workspace_root)
