"""Single Telegram I/O door: disk-backed rate limit + poll offset (ADR-0043).

Launcher and backend are separate processes, so quota and getUpdates offset
live on disk. REAL promotion / freeze / REAL-safety never fail closed on quota.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.notifications.telegram_journal import resolve_state_relative
from lumina_core.state.state_manager import safe_with_file_lock

DEFAULT_BYPASS_KINDS: tuple[str, ...] = ("promotion", "freeze", "real_safety")
DEFAULT_MIN_INTERVAL_SEC = 20.0
DEFAULT_MAX_PER_HOUR = 12
GATE_RELATIVE = "state/telegram_outbound_gate.json"
OFFSET_RELATIVE = "state/telegram_poll_offset.json"

_INSTANCE: TelegramGateway | None = None
_INSTANCE_LOCK = threading.Lock()


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _hour_bucket(now_unix: float) -> str:
    return datetime.fromtimestamp(now_unix, tz=timezone.utc).strftime("%Y-%m-%dT%H")


def kind_for_attention_event(event: Any) -> tuple[str, bool]:
    """Map AttentionEvent → (journal kind, expects_reply)."""
    category = str(getattr(getattr(event, "category", None), "value", "") or "")
    reason = str(getattr(event, "reason_code", "") or "")
    if category == "real":
        return "real_safety", False
    if "freeze" in reason:
        return "freeze", True
    return "attention", False


class TelegramGateway:
    """Process + disk choke point for Telegram send quota and poll offset."""

    def __init__(
        self,
        *,
        workspace_root: Path | str | None = None,
        min_interval_sec: float | None = None,
        max_per_hour: int | None = None,
        bypass_kinds: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        if workspace_root is not None:
            self._workspace_root = Path(workspace_root)
        else:
            env = os.getenv("LUMINA_STATE_DIR", "").strip()
            self._workspace_root = Path(env).parent if env else Path.cwd()
        cfg = ConfigLoader.section("telegram", default={})
        outbound: dict[str, Any] = {}
        if isinstance(cfg, dict) and isinstance(cfg.get("outbound"), dict):
            outbound = dict(cfg["outbound"])
        self.min_interval_sec = (
            float(min_interval_sec)
            if min_interval_sec is not None
            else max(0.0, _coerce_float(outbound.get("min_interval_sec"), DEFAULT_MIN_INTERVAL_SEC))
        )
        self.max_per_hour = (
            int(max_per_hour)
            if max_per_hour is not None
            else max(0, _coerce_int(outbound.get("max_per_hour"), DEFAULT_MAX_PER_HOUR))
        )
        raw_bypass = bypass_kinds
        if raw_bypass is None:
            raw_bypass = outbound.get("bypass_kinds")
        if isinstance(raw_bypass, (list, tuple)) and raw_bypass:
            self.bypass_kinds = tuple(str(x).strip() for x in raw_bypass if str(x).strip())
        else:
            self.bypass_kinds = DEFAULT_BYPASS_KINDS

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def set_workspace(self, workspace_root: Path | str) -> None:
        self._workspace_root = Path(workspace_root)

    def _gate_path(self) -> Path:
        return resolve_state_relative(GATE_RELATIVE, self._workspace_root)

    def _offset_path(self) -> Path:
        return resolve_state_relative(OFFSET_RELATIVE, self._workspace_root)

    def bypasses_rate_limit(self, kind: str) -> bool:
        return str(kind or "").strip().lower() in {k.lower() for k in self.bypass_kinds}

    def try_reserve_send(self, kind: str) -> tuple[bool, str | None]:
        """Reserve an outbound slot. Bypass kinds always succeed."""
        if self.bypasses_rate_limit(kind):
            self._touch_last_sent(count_hour=False)
            return True, None
        path = self._gate_path()

        def _locked(target: Path) -> tuple[bool, str | None]:
            now = datetime.now(timezone.utc).timestamp()
            state = _load_json(target)
            last = _coerce_float(state.get("last_sent_unix"), 0.0)
            bucket = str(state.get("hour_bucket") or "")
            count = _coerce_int(state.get("hour_count"), 0)
            current_bucket = _hour_bucket(now)
            if bucket != current_bucket:
                bucket = current_bucket
                count = 0
            if self.min_interval_sec > 0 and last > 0 and (now - last) < self.min_interval_sec:
                return False, "rate_limited"
            if self.max_per_hour > 0 and count >= self.max_per_hour:
                return False, "rate_limited"
            state = {
                "last_sent_unix": now,
                "hour_bucket": bucket,
                "hour_count": count + 1,
            }
            _dump_json(target, state)
            return True, None

        try:
            return safe_with_file_lock(path, _locked)
        except Exception:
            # Fail-open for non-capital Telegram would spam; fail-closed drops the send.
            return False, "rate_limited"

    def _touch_last_sent(self, *, count_hour: bool) -> None:
        path = self._gate_path()

        def _locked(target: Path) -> None:
            now = datetime.now(timezone.utc).timestamp()
            state = _load_json(target)
            bucket = str(state.get("hour_bucket") or "")
            count = _coerce_int(state.get("hour_count"), 0)
            current_bucket = _hour_bucket(now)
            if bucket != current_bucket:
                bucket = current_bucket
                count = 0
            if count_hour:
                count += 1
            _dump_json(
                target,
                {
                    "last_sent_unix": now,
                    "hour_bucket": bucket,
                    "hour_count": count,
                },
            )

        try:
            safe_with_file_lock(path, _locked)
        except Exception:
            return

    def load_offset(self) -> int:
        path = self._offset_path()

        def _locked(target: Path) -> int:
            state = _load_json(target)
            return max(0, _coerce_int(state.get("last_update_id"), 0))

        try:
            return int(safe_with_file_lock(path, _locked))
        except Exception:
            return 0

    def save_offset(self, update_id: int) -> None:
        uid = int(update_id)
        if uid <= 0:
            return
        path = self._offset_path()

        def _locked(target: Path) -> None:
            state = _load_json(target)
            current = _coerce_int(state.get("last_update_id"), 0)
            if uid > current:
                _dump_json(
                    target,
                    {
                        "last_update_id": uid,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

        try:
            safe_with_file_lock(path, _locked)
        except Exception:
            return


def get_telegram_gateway(*, workspace_root: Path | str | None = None) -> TelegramGateway:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = TelegramGateway(workspace_root=workspace_root)
        elif workspace_root is not None:
            _INSTANCE.set_workspace(workspace_root)
        return _INSTANCE


def reset_telegram_gateway_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
