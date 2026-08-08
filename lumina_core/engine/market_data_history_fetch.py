"""Historical bar fetch/post helpers for MarketDataHistoryMixin (Wave B3 PR-D0).

Owns ``_fetch_historical_bars`` / ``_post_historical_bars`` and supporting helpers.
Uses late-bound ``_mds()`` so monkeypatches on ``market_data_service`` still apply.
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any, Callable

import pandas as pd

from .errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.first_boot_ui import HISTORICAL_BAR_LIMIT_SAFETY_CAP

if TYPE_CHECKING:
    from datetime import datetime


def _mds():
    """Late-bind façade module so monkeypatches on market_data_service apply."""
    from lumina_core.engine import market_data_service as mds

    return mds


from lumina_core.engine.market_data_history_helpers import MarketDataHistoryHelpersMixin

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

    def _post_historical_bars(
        self,
        *,
        instrument: str,
        token: str,
        payload: dict[str, Any],
        app: Any,
        daysback_fallback: int | None = None,
    ) -> list[dict[str, Any]]:
        safe_payload = self._sanitize_historical_payload_dates(payload)
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
                    )
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
        """Load 1-min bars from CrossTrade with daysBack-first and day-aligned pagination.

        CrossTrade accepts ISO-8601 UTC for ``from``/``to`` but NT8 backends are more reliable
        with midnight-aligned windows. Expired contract symbols are rolled to the next quarter.
        """
        app = self._app()
        requested_instrument = self._normalize_symbol(instrument)
        instrument = self._resolve_historical_instrument(requested_instrument, app)
        self.last_requested_instrument = str(requested_instrument or "")
        self.last_resolved_instrument = str(instrument or "")
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
                    f"[v21.7] Loading {limit_label} real 1-min OHLC bars for {instrument} "
                    f"(last {days_back_i} days, requested={requested_instrument})..."
                ),
                context={
                    "instrument": instrument,
                    "requested_instrument": requested_instrument,
                    "limit": target_cap,
                    "days_back": days_back_i,
                    "uncapped": uncapped,
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
