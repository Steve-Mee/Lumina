"""Historical bar fetch/post helpers for MarketDataHistoryMixin (Wave B3 PR-D0).

Owns ``_fetch_historical_bars`` / ``_post_historical_bars`` and supporting helpers.
Uses late-bound ``_mds()`` so monkeypatches on ``market_data_service`` still apply.

Market data plane:
- ``broker.live_provider=ninjatrader`` → Fabric RequestHistoricalData (native NT)
- else → CrossTrade REST (legacy emergency only)
"""

from __future__ import annotations

import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pandas as pd

from .errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.first_boot_ui import HISTORICAL_BAR_LIMIT_SAFETY_CAP
from lumina_core.engine.market_data_history_helpers import MarketDataHistoryHelpersMixin


def _is_ninjatrader_exe_running() -> bool:
    """Lightweight Windows process probe — no launcher imports (Code Red telemetry only)."""
    import subprocess
    import sys

    if sys.platform != "win32":
        return False
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq NinjaTrader.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return "ninjatrader.exe" in (r.stdout or "").lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


def pd_to_utc(raw: Any) -> datetime | None:
    """Parse bar timestamp to UTC datetime (or None)."""
    if raw is None:
        return None
    try:
        ts = pd.to_datetime(raw, utc=True)
        if hasattr(ts, "to_pydatetime"):
            return ts.to_pydatetime()
        return ts  # type: ignore[return-value]
    except Exception:
        return None


def _mds():
    """Late-bind façade module so monkeypatches on market_data_service apply."""
    from lumina_core.engine import market_data_service as mds

    return mds


class MarketDataHistoryFetchMixin(MarketDataHistoryHelpersMixin):
    """Historical bars fetch (helpers in MarketDataHistoryHelpersMixin)."""

    def _resolve_historical_instrument(self, instrument: str, app: Any) -> str:
        normalized = self._normalize_symbol(instrument)
        rolled = _mds().roll_stale_contract_symbol(normalized)
        if rolled != normalized:
            app.logger.warning(
                "birth.history.stale_contract_roll from=%s to=%s",
                normalized,
                rolled,
            )
        return rolled

    def _history_provider(self) -> str:
        """Return ``fabric`` | ``crosstrade`` based on engine config + yaml SSOT.

        Defense-in-depth: engine.broker_live_provider can be poisoned to crosstrade
        when yaml was first loaded from the wrong cwd (lru cache). Always re-check
        LUMINA_CONFIG / config.yaml live_provider for ninjatrader.
        """
        cfg = getattr(self.engine, "config", None)
        provider = str(getattr(cfg, "broker_live_provider", "") or "").strip().lower()
        explicit = str(getattr(cfg, "market_data_provider", "") or "").strip().lower()
        if explicit in {"fabric", "ninjatrader", "nt"}:
            return "fabric"
        if explicit in {"crosstrade", "ct"}:
            # Explicit CT only when not overridden by yaml ninjatrader SSOT.
            yaml_lp = self._yaml_live_provider()
            if yaml_lp in {"ninjatrader", "nt", "fabric"}:
                return "fabric"
            return "crosstrade"
        if provider in {"ninjatrader", "nt", "fabric"}:
            return "fabric"
        yaml_lp = self._yaml_live_provider()
        if yaml_lp in {"ninjatrader", "nt", "fabric"}:
            return "fabric"
        env_lp = str(__import__("os").getenv("BROKER_LIVE_PROVIDER") or "").strip().lower()
        if env_lp in {"ninjatrader", "nt", "fabric"}:
            return "fabric"
        # Explicit Crosstrade only — default foundation is Fabric (ADR-0040).
        if provider == "crosstrade" or yaml_lp == "crosstrade" or env_lp == "crosstrade":
            return "crosstrade"
        return "fabric"

    def _yaml_live_provider(self) -> str:
        try:
            from lumina_core.engine.engine_config_helpers import (
                _config_yaml_nested,
                clear_yaml_config_cache,
            )

            # Prefer fresh yaml after birth chdir / LUMINA_CONFIG set.
            clear_yaml_config_cache()
            return str(_config_yaml_nested("", "broker", "live_provider") or "").strip().lower()
        except Exception:
            return ""

    def _allow_crosstrade_history_fallback(self) -> bool:
        """Emergency MD hop only when process EngineConfig flag is true.

        EngineConfig is loaded from YAML/env at boot and updated when Vault
        writes ``broker.fallback_on_fabric_failure``. Prefer the live config
        object so a stale process env cannot force a silent CrossTrade hop.
        """
        cfg = getattr(self.engine, "config", None)
        if cfg is not None and hasattr(cfg, "fallback_on_fabric_failure"):
            return bool(getattr(cfg, "fallback_on_fabric_failure", False))
        try:
            from lumina_core.broker.emergency_opt_in import read_emergency_opt_in

            return bool(read_emergency_opt_in(engine_config=cfg).market_data_fallback)
        except Exception:
            return False

    def _fabric_bars_to_ct_shape(self, bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize Fabric bar dicts to CrossTrade-like shape expected by history loaders."""
        out: list[dict[str, Any]] = []
        for b in bars:
            if not isinstance(b, dict):
                continue
            ts_ms = int(b.get("timestamp_unix_ms") or 0)
            epoch = int(b.get("epoch") or (ts_ms // 1000 if ts_ms else 0))
            ts_iso = b.get("timestamp") or b.get("time")
            if not ts_iso and epoch > 0:
                ts_iso = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif not ts_iso and ts_ms > 0:
                ts_iso = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            if not ts_iso:
                continue
            out.append(
                {
                    "timestamp": ts_iso,
                    "time": ts_iso,
                    "epoch": epoch,
                    "open": float(b.get("open") or b.get("last") or 0.0),
                    "high": float(b.get("high") or b.get("last") or 0.0),
                    "low": float(b.get("low") or b.get("last") or 0.0),
                    "close": float(b.get("close") or b.get("last") or 0.0),
                    "volume": int(b.get("volume") or 0),
                    "last": float(b.get("last") or b.get("close") or 0.0),
                }
            )
        return out

    def _fetch_historical_bars_via_fabric(
        self,
        *,
        instrument: str,
        days_back: int,
        limit: int | None,
        on_chunk: Callable[..., None] | None = None,
    ) -> list[dict[str, Any]]:
        """Load bars via Fabric RequestHistoricalData (NT8 AddOn data plane).

        Birth training-window SLA needs full calendar coverage (e.g. 56 days).
        NT ``barsBack`` only returns the *most recent* N bars (~few days at 1m).
        We therefore page **backward** in calendar chunks with explicit from/to
        so older sessions are filled — never stop after one 8k recent slice.
        """
        app = self._app()
        cfg = getattr(self.engine, "config", None)
        try:
            from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient
        except ImportError as exc:
            app.logger.error("Fabric client unavailable for historical data: %s", exc)
            return []

        fabric_cfg = FabricConfig.from_engine_config(cfg, mode_context="sim")
        # Prefer always-on supervisor client (heartbeats keep SAFE_MODE clear).
        owns_client = True
        client: Any = None
        try:
            from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                ensure_fabric_link_supervisor,
                get_fabric_link_supervisor,
            )

            ensure_fabric_link_supervisor(cfg, mode_context="sim")
            shared = get_fabric_link_supervisor().get_client()
            if shared is not None and getattr(shared, "is_connected", False):
                client = shared
                owns_client = False
                app.logger.info(
                    "Historical bars via Fabric supervisor session target=%s session=%s",
                    fabric_cfg.target,
                    getattr(shared, "session_id", ""),
                )
        except Exception:
            app.logger.debug("fabric.history.supervisor_unavailable", exc_info=True)

        if client is None:
            # One-shot session; keep heartbeats so NT Link shows Brain sessions during long load.
            fabric_cfg.heartbeat_interval_ms = max(
                1000, int(getattr(fabric_cfg, "heartbeat_interval_ms", 1000) or 1000)
            )
            client = FabricGrpcClient(fabric_cfg)
            owns_client = True

        days_back_i = max(1, int(days_back))
        uncapped = limit is None
        target_cap: int | None
        if uncapped:
            target_cap = HISTORICAL_BAR_LIMIT_SAFETY_CAP
        else:
            target_cap = max(1, min(int(limit), HISTORICAL_BAR_LIMIT_SAFETY_CAP))

        # ~23h nearly continuous futures → ~1400 1m bars/day. Budget high for birth SLA.
        est_bars_per_day = 1_500
        need_bars = min(
            target_cap if target_cap is not None else HISTORICAL_BAR_LIMIT_SAFETY_CAP,
            max(est_bars_per_day * days_back_i, 2_000),
        )
        # Per-chunk bar budget: enough for ~1 week of 1m futures, but NOT a HDS storm.
        # Code Red: rapid multi-k bars storms correlated with NT/Tradovate process exits.
        per_chunk = min(8_000, max(need_bars // max(1, days_back_i // 7), 4_000))
        if target_cap is not None:
            per_chunk = min(per_chunk, target_cap)
        # Calendar chunk width for from/to pagination (full trading days).
        chunk_days = 5 if days_back_i >= 21 else (7 if days_back_i >= 14 else max(2, min(7, days_back_i)))
        # Minimum settle between BarsRequest RPCs (seconds) — protect NT process.
        chunk_settle_sec = 2.0 if days_back_i >= 14 else 1.0
        # Only abort if NT was observed alive earlier this fetch, then disappeared.
        # Lightweight process check — never import lumina_launcher (heavy import graph).
        nt_seen_alive = bool(_is_ninjatrader_exe_running())

        now_utc = datetime.now(timezone.utc)
        window_end = now_utc
        window_start = now_utc - timedelta(days=days_back_i)

        app.logger.info(
            "Historical bars via Fabric instrument=%s daysBack=%s need_bars≈%s "
            "chunk_days=%s per_chunk=%s target=%s",
            instrument,
            days_back_i,
            need_bars,
            chunk_days,
            per_chunk,
            fabric_cfg.target,
        )
        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message=(
                    f"[fabric] Loading historical 1-min bars for {instrument} "
                    f"(last {days_back_i} days via Execution Fabric / NT8, "
                    f"backward chunks of {chunk_days}d)..."
                ),
                context={
                    "instrument": instrument,
                    "days_back": days_back_i,
                    "provider": "fabric",
                    "need_bars": need_bars,
                    "chunk_days": chunk_days,
                },
            )
        )

        merged: list[dict[str, Any]] = []
        seen_epoch: set[int] = set()
        seen_time: set[str] = set()
        try:
            if owns_client and not client.connect():
                code = str(getattr(client, "last_connect_code", "") or "")
                err = str(getattr(client, "last_connect_error", "") or "")
                if code in {"AUTH_FAILED", "AUTH_TIMEOUT", "TOKEN_EMPTY"}:
                    app.logger.error(
                        "Fabric auth failed for historical data target=%s code=%s detail=%s — "
                        "token mismatch: Repair connection + restart NT once "
                        "(LUMINA Link Brain sessions must be ≥ 1)",
                        fabric_cfg.target,
                        code,
                        err[:200],
                    )
                else:
                    app.logger.error(
                        "Fabric connect failed for historical data target=%s code=%s — "
                        "start NT8 LUMINA AddOn on 127.0.0.1:50051 or fix auth token",
                        fabric_cfg.target,
                        code or "UNKNOWN",
                    )
                return []

            # Walk backward: [T-5d, T], [T-10d, T-5d], ... covering full days_back.
            cursor_end = window_end
            chunk_index = 0
            max_chunks = max(12, int(days_back_i / chunk_days) + 6)
            empty_streak = 0
            # Soft pad for TZ / session edges when filtering bars into the chunk.
            pad = timedelta(hours=18)

            while cursor_end > window_start and chunk_index < max_chunks:
                if target_cap is not None and len(merged) >= target_cap:
                    break
                chunk_index += 1
                chunk_start = max(window_start, cursor_end - timedelta(days=chunk_days))
                start_ms = int(chunk_start.timestamp() * 1000)
                end_ms = int(cursor_end.timestamp() * 1000)
                remaining = None if target_cap is None else max(0, target_cap - len(merged))
                max_bars = per_chunk if remaining is None else min(per_chunk, remaining)
                if max_bars <= 0:
                    break

                hist = client.request_historical_data(
                    instrument=instrument,
                    bar_period="1m",
                    start_unix_ms=start_ms,
                    end_unix_ms=end_ms,
                    max_bars=max_bars,
                    timeout_seconds=120.0,
                )
                code = str(hist.get("code") or "")
                raw_bars = hist.get("bars") if isinstance(hist.get("bars"), list) else []
                shaped = self._fabric_bars_to_ct_shape(raw_bars)

                # Drop bars outside this calendar chunk (rejects barsBack-poisoned replies).
                lo = chunk_start - pad
                hi = cursor_end + pad
                in_window: list[dict[str, Any]] = []
                for b in shaped:
                    ep = b.get("epoch")
                    if isinstance(ep, (int, float)) and int(ep) > 0:
                        ts = datetime.fromtimestamp(int(ep), tz=timezone.utc)
                    else:
                        try:
                            ts = pd_to_utc(b.get("timestamp") or b.get("time"))
                        except Exception:
                            continue
                    if ts is None:
                        continue
                    if lo <= ts <= hi:
                        in_window.append(b)

                if code.lower() != "ok" or not in_window:
                    app.logger.warning(
                        "Fabric historical chunk failed/empty code=%s message=%s "
                        "instrument=%s window=%s→%s raw=%s in_window=%s merged=%s",
                        code,
                        hist.get("message"),
                        instrument,
                        chunk_start.date(),
                        cursor_end.date(),
                        len(shaped),
                        len(in_window),
                        len(merged),
                    )
                    empty_streak += 1
                    if empty_streak >= 3 and not merged:
                        app.logger.error(
                            "Fabric historical: first chunks empty — abort "
                            "(NT data feed / BarsRequest issue)"
                        )
                        return []
                    # Allow more empty older chunks (weekends / missing history) before stop.
                    if empty_streak >= max(8, max_chunks // 2):
                        app.logger.warning(
                            "Fabric historical: too many empty chunks — stop pagination "
                            "merged=%s empty_streak=%s",
                            len(merged),
                            empty_streak,
                        )
                        break
                    cursor_end = chunk_start
                    continue

                empty_streak = 0
                before = len(merged)
                self._merge_bars_into(
                    merged,
                    in_window,
                    seen_epoch=seen_epoch,
                    seen_time=seen_time,
                    target_cap=target_cap,
                )
                added = len(merged) - before
                # If NT returned bars but all were duplicates of the recent slice, treat as empty.
                if added <= 0:
                    empty_streak += 1
                    app.logger.warning(
                        "Fabric historical chunk=%s window=%s→%s got=%s added=0 (dupes) total=%s",
                        chunk_index,
                        chunk_start.date(),
                        cursor_end.date(),
                        len(in_window),
                        len(merged),
                    )
                else:
                    app.logger.info(
                        "Fabric historical chunk=%s window=%s→%s got=%s added=%s total=%s",
                        chunk_index,
                        chunk_start.date(),
                        cursor_end.date(),
                        len(in_window),
                        added,
                        len(merged),
                    )
                if on_chunk is not None:
                    try:
                        on_chunk(
                            chunk_index=chunk_index,
                            chunk_total=max_chunks,
                            bars_merged=len(merged),
                            chunk_bars=added,
                            chunk_phase="fabric",
                        )
                    except Exception:
                        app.logger.warning("birth.history.on_chunk_failed", exc_info=True)

                cursor_end = chunk_start
                if chunk_start <= window_start:
                    break

                # Code Red: pace BarsRequest so Tradovate/HDS is not flooded (NT crash risk).
                alive_now = bool(_is_ninjatrader_exe_running())
                if alive_now:
                    nt_seen_alive = True
                elif nt_seen_alive and not alive_now:
                    app.logger.error(
                        "CODE_RED ninjatrader_process_gone during fabric history "
                        "merged=%s chunks=%s — stopping pagination (not a Lumina taskkill)",
                        len(merged),
                        chunk_index,
                    )
                    break
                # Only settle when talking to a live NT process (unit tests stay fast).
                if nt_seen_alive:
                    try:
                        time.sleep(float(chunk_settle_sec))
                    except Exception:
                        pass

            # Coverage hint for birth SLA debugging
            if merged:
                epochs = [
                    int(b["epoch"])
                    for b in merged
                    if isinstance(b.get("epoch"), (int, float)) and int(b["epoch"]) > 0
                ]
                if epochs:
                    span_days = max(1, int((max(epochs) - min(epochs)) / 86_400) + 1)
                    app.logger.info(
                        "Fabric historical done bars=%s calendar_span≈%sd requested=%sd chunks=%s",
                        len(merged),
                        span_days,
                        days_back_i,
                        chunk_index,
                    )
                    if span_days < max(1, int(days_back_i * 0.9)):
                        app.logger.warning(
                            "Fabric historical thin span: got ≈%s days of %s requested — "
                            "birth training_window_sla may fail; check NT HDS / expand chunks",
                            span_days,
                            days_back_i,
                        )
        finally:
            if owns_client:
                try:
                    client.disconnect()
                except Exception:
                    pass

        return self._sort_and_cap_bars(merged, target_cap)

    def _is_mds_client_not_ready(self, status_code: int, body: str) -> bool:
        """True for HTTP 408 / disconnected client readiness (H2)."""
        text = (body or "").lower()
        if int(status_code) == 408:
            return True
        return any(
            needle in text
            for needle in (
                "client not ready",
                "disconnected",
                "not connected",
                "connection closed",
            )
        )

    def _post_historical_bars(
        self,
        *,
        instrument: str,
        token: str,
        payload: dict[str, Any],
        app: Any,
        daysback_fallback: int | None = None,
        _retry_attempt: int = 0,
    ) -> list[dict[str, Any]]:
        safe_payload = self._sanitize_historical_payload_dates(payload)
        # H2: bounded retry/backoff on 408 / client-not-ready before empty return
        max_ready_retries = 3
        try:
            response = _mds().requests.post(
                "https://app.crosstrade.io/v1/api/market/bars",
                headers={"Authorization": f"Bearer {token}"},
                json=safe_payload,
                timeout=(10, 45),
            )
            if response.status_code != 200:
                body = response.text[:400]
                if (
                    daysback_fallback is not None
                    and daysback_fallback > 0
                    and ("from" in safe_payload or "to" in safe_payload)
                    and self._is_historical_date_format_error(body)
                ):
                    fallback_payload = {
                        "instrument": safe_payload.get("instrument", instrument),
                        "periodType": safe_payload.get("periodType", "minute"),
                        "period": safe_payload.get("period", 1),
                        "daysBack": int(daysback_fallback),
                        "limit": max(100, int(safe_payload.get("limit", 8000) or 8000)),
                    }
                    app.logger.warning(
                        "birth.history.date_format_fallback daysBack=%s instrument=%s",
                        daysback_fallback,
                        instrument,
                    )
                    return self._post_historical_bars(
                        instrument=instrument,
                        token=token,
                        payload=fallback_payload,
                        app=app,
                        daysback_fallback=None,
                        _retry_attempt=0,
                    )
                if (
                    self._is_mds_client_not_ready(response.status_code, body)
                    and int(_retry_attempt) < max_ready_retries
                ):
                    import time as _time

                    delay = min(8.0, 0.5 * (2 ** int(_retry_attempt)))
                    app.logger.warning(
                        "birth.history.mds_not_ready_retry status=%s attempt=%s/%s delay=%.1fs body=%s",
                        response.status_code,
                        int(_retry_attempt) + 1,
                        max_ready_retries,
                        delay,
                        body[:120],
                    )
                    try:
                        _time.sleep(delay)
                    except Exception:
                        pass
                    return self._post_historical_bars(
                        instrument=instrument,
                        token=token,
                        payload=safe_payload,
                        app=app,
                        daysback_fallback=daysback_fallback,
                        _retry_attempt=int(_retry_attempt) + 1,
                    )
                if self._is_mds_client_not_ready(response.status_code, body):
                    log_structured(
                        LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                            code="MDS_HIST_API_004",
                            message=(
                                f"API error {response.status_code} after {max_ready_retries} "
                                f"readiness retries: {body}"
                            ),
                            context={
                                "status_code": response.status_code,
                                "retries": max_ready_retries,
                                "circuit": "open",
                            },
                        )
                    )
                    app.logger.error(
                        "birth.history.mds_circuit_open status=%s instrument=%s — "
                        "not treating bootstrap as clean",
                        response.status_code,
                        instrument,
                    )
                    return []
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                        code="MDS_HIST_API_004",
                        message=f"API error {response.status_code}: {body}",
                        context={"status_code": response.status_code},
                    )
                )
                return []
            return self._bars_response_to_list(response.json())
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="MDS_HIST_LOAD_005",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"Historical load error: {exc}")
            return []

    def _fetch_historical_bars(
        self,
        instrument: str,
        days_back: int,
        limit: int | None,
        on_chunk: Callable[..., None] | None = None,
        prefer_daysback_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Load 1-min bars from Fabric (native NT) or CrossTrade (legacy).

        When ``broker.live_provider=ninjatrader``, uses Execution Fabric
        ``RequestHistoricalData`` only — no CrossTrade cloud hop unless
        ``fallback_on_fabric_failure`` is explicitly true.
        """
        app = self._app()
        requested_instrument = self._normalize_symbol(instrument)
        instrument = self._resolve_historical_instrument(requested_instrument, app)
        self.last_requested_instrument = str(requested_instrument or "")
        self.last_resolved_instrument = str(instrument or "")

        provider = self._history_provider()
        if provider == "fabric":
            bars = self._fetch_historical_bars_via_fabric(
                instrument=instrument,
                days_back=days_back,
                limit=limit,
                on_chunk=on_chunk,
            )
            if bars:
                return bars
            if not self._allow_crosstrade_history_fallback():
                app.logger.error(
                    "Fabric historical returned empty for %s — fail-closed "
                    "(no CrossTrade fallback; set broker.fallback_on_fabric_failure=true only as emergency)",
                    instrument,
                )
                return []
            try:
                from lumina_core.broker.emergency_opt_in import assert_crosstrade_plugin_allowed

                assert_crosstrade_plugin_allowed(
                    engine_config=getattr(self.engine, "config", None),
                    purpose="history_fallback",
                )
            except RuntimeError as exc:
                app.logger.error(
                    "Fabric historical empty for %s — CrossTrade plugin blocked: %s",
                    instrument,
                    exc,
                )
                return []
            app.logger.warning(
                "Fabric historical empty for %s — emergency CrossTrade fallback enabled",
                instrument,
            )
        elif provider == "crosstrade":
            # Full CT history path still requires deliberate opt-in (live_provider=crosstrade).
            try:
                from lumina_core.broker.emergency_opt_in import assert_crosstrade_plugin_allowed

                assert_crosstrade_plugin_allowed(
                    engine_config=getattr(self.engine, "config", None),
                    purpose="history_crosstrade_provider",
                )
            except RuntimeError as exc:
                app.logger.error("CrossTrade history blocked: %s", exc)
                return []

        token = getattr(app, "CROSSTRADE_TOKEN", self.engine.config.crosstrade_token or "")
        uncapped = limit is None
        if uncapped:
            target_cap: int | None = HISTORICAL_BAR_LIMIT_SAFETY_CAP
            limit_label = f"all bars in window (safety cap {HISTORICAL_BAR_LIMIT_SAFETY_CAP:,})"
        else:
            target_cap = max(1, min(int(limit), HISTORICAL_BAR_LIMIT_SAFETY_CAP))
            limit_label = str(target_cap)
        days_back_i = max(1, int(days_back))
        per_chunk_limit = 8_000

        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message=(
                    f"[v21.7/crosstrade] Loading {limit_label} real 1-min OHLC bars for {instrument} "
                    f"(last {days_back_i} days, requested={requested_instrument})..."
                ),
                context={
                    "instrument": instrument,
                    "requested_instrument": requested_instrument,
                    "limit": target_cap,
                    "days_back": days_back_i,
                    "uncapped": uncapped,
                    "provider": "crosstrade",
                },
            )
        )

        merged: list[dict[str, Any]] = []
        seen_epoch: set[int] = set()
        seen_time: set[str] = set()

        def _emit_chunk(
            *,
            chunk_index: int,
            chunk_total: int,
            chunk_bars: int,
            chunk_phase: str = "fetch",
        ) -> None:
            if on_chunk is None:
                return
            try:
                on_chunk(
                    chunk_index=chunk_index,
                    chunk_total=chunk_total,
                    bars_merged=len(merged),
                    chunk_bars=chunk_bars,
                    chunk_phase=chunk_phase,
                )
            except Exception:
                app.logger.warning("birth.history.on_chunk_failed", exc_info=True)

        # 1) daysBack-only (CrossTrade docs default; avoids from/to parse failures on some NT8 hosts).
        simple_limit = min(per_chunk_limit, target_cap if target_cap is not None else per_chunk_limit)
        payload_days_back = {
            "instrument": instrument,
            "periodType": "minute",
            "period": 1,
            "daysBack": days_back_i,
            "limit": max(100, simple_limit),
        }
        app.logger.info(
            "Historical bars daysBack-first instrument=%s daysBack=%s limit=%s",
            instrument,
            days_back_i,
            payload_days_back["limit"],
        )
        days_back_bars = self._post_historical_bars(
            instrument=instrument,
            token=token,
            payload=payload_days_back,
            app=app,
        )
        if days_back_bars:
            self._merge_bars_into(
                merged,
                days_back_bars,
                seen_epoch=seen_epoch,
                seen_time=seen_time,
                target_cap=target_cap,
            )
            _emit_chunk(chunk_index=1, chunk_total=1, chunk_bars=len(days_back_bars))
            short_window = days_back_i <= 7
            preflight_probe = target_cap is not None and target_cap <= 1_000
            cap_satisfied = target_cap is not None and len(merged) >= target_cap
            # One daysBack chunk is capped ~8k bars (~5–7 calendar days of 1-min).
            # Long birth windows must paginate when the first chunk is thin.
            expected_min = max(per_chunk_limit, int(days_back_i) * 200)
            if target_cap is not None:
                expected_min = min(expected_min, int(target_cap))
            thin_for_window = days_back_i > 14 and len(merged) < expected_min
            if merged and (
                short_window
                or preflight_probe
                or (cap_satisfied and not thin_for_window)
                or (prefer_daysback_only and not thin_for_window)
            ):
                return self._sort_and_cap_bars(merged, target_cap)
            if merged and thin_for_window:
                app.logger.warning(
                    "birth.history.daysback_thin_continuing_pagination "
                    "bars=%s expected_min=%s days_back=%s prefer_daysback_only=%s",
                    len(merged),
                    expected_min,
                    days_back_i,
                    prefer_daysback_only,
                )

        if prefer_daysback_only:
            # Thin long-window loads fall through to pagination above; only
            # return early here when the first chunk was accepted as complete.
            if merged and days_back_i <= 14:
                return self._sort_and_cap_bars(merged, target_cap)
            if not merged:
                app.logger.warning(
                    "birth.history.daysback_only_empty instrument=%s days_back=%s",
                    instrument,
                    days_back_i,
                )

        # 2) Day-aligned UTC pagination (midnight boundaries per CrossTrade examples).
        # Fail-fast: if MDS circuit is open (408), do not burn 15×3 retries (~4 min).
        utc_now = _mds().datetime.now(_mds().timezone.utc)
        range_start = self._utc_day_floor(utc_now - _mds().timedelta(days=days_back_i))
        range_end = self._utc_day_floor(utc_now) + _mds().timedelta(days=1)
        chunk_days = 4
        max_chunks = max(1, min(256, (days_back_i // chunk_days) + 48))

        windows: list[tuple[datetime, datetime]] = []
        cursor = range_start
        while cursor < range_end and len(windows) < max_chunks:
            nxt = min(cursor + _mds().timedelta(days=chunk_days), range_end)
            if nxt <= cursor:
                break
            windows.append((cursor, nxt))
            cursor = nxt

        empty_circuit_streak = 0
        for idx, (win_from, win_to) in enumerate(windows):
            if target_cap is not None and len(merged) >= target_cap:
                break
            if target_cap is None:
                chunk_limit = per_chunk_limit
            else:
                chunk_limit = min(per_chunk_limit, target_cap - len(merged))
            payload = {
                "instrument": instrument,
                "periodType": "minute",
                "period": 1,
                "from": self._utc_iso_z(win_from),
                "to": self._utc_iso_z(win_to),
                "limit": max(100, chunk_limit),
            }
            app.logger.info(
                "Historical bars chunk %s/%s from=%s to=%s limit=%s",
                idx + 1,
                len(windows),
                payload["from"],
                payload["to"],
                chunk_limit,
            )
            chunk_days_span = max(1, (win_to - win_from).days)
            bars = self._post_historical_bars(
                instrument=instrument,
                token=token,
                payload=payload,
                app=app,
                daysback_fallback=chunk_days_span,
            )
            _emit_chunk(
                chunk_index=idx + 1,
                chunk_total=len(windows),
                chunk_bars=len(bars),
            )
            if not bars:
                empty_circuit_streak += 1
                # Two consecutive empty MDS chunks → abort (prevents 4-minute birth hang).
                if empty_circuit_streak >= 2 and not merged:
                    app.logger.error(
                        "birth.history.crosstrade_fail_fast empty_streak=%s instrument=%s — "
                        "abort pagination (use Fabric when live_provider=ninjatrader)",
                        empty_circuit_streak,
                        instrument,
                    )
                    break
            else:
                empty_circuit_streak = 0
            before = len(merged)
            self._merge_bars_into(
                merged,
                bars,
                seen_epoch=seen_epoch,
                seen_time=seen_time,
                target_cap=target_cap,
            )
            if len(merged) > before and target_cap is not None and len(merged) >= target_cap:
                break

        if merged:
            return self._sort_and_cap_bars(merged, target_cap)

        # 3) Legacy single-shot daysBack fallback (smaller limit for provider timeouts).
        fallback_limit = min(8_000, target_cap if target_cap is not None else HISTORICAL_BAR_LIMIT_SAFETY_CAP)
        payload_fb = {
            "instrument": instrument,
            "periodType": "minute",
            "period": 1,
            "daysBack": days_back_i,
            "limit": fallback_limit,
        }
        app.logger.warning(
            "birth.history.paginated_empty fallback=daysBack limit=%s daysBack=%s instrument=%s",
            fallback_limit,
            days_back_i,
            instrument,
        )
        fallback_bars = self._post_historical_bars(
            instrument=instrument, token=token, payload=payload_fb, app=app
        )
        if fallback_bars:
            return self._sort_and_cap_bars(fallback_bars, target_cap)

        stale_hint = ""
        if requested_instrument != instrument:
            stale_hint = f" (rolled from stale {requested_instrument})"
        elif _mds().is_stale_contract_symbol(requested_instrument):
            stale_hint = f" (contract {requested_instrument} appears expired)"
        app.logger.error(
            "birth.history.load_failed instrument=%s days_back=%s limit=%s%s "
            "(0 bars after daysBack+paginated+fallback; check Crosstrade token, NT8 connection, instrument)",
            instrument,
            days_back_i,
            target_cap,
            stale_hint,
        )
        return []
