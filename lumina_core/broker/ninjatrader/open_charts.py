"""Open NinjaTrader chart listings.

The instrument selector on a chart window is the book. A configured month that
the chart is not showing is not. Calendar roll is only the fallback when no
chart selector can be read. Nothing here invents a symbol.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Sequence
from datetime import datetime

from lumina_core.order_gatekeeper.contract_symbols import (
    MONTHS,
    MONTH_CODE_BY_NUM,
    live_listing,
)

logger = logging.getLogger(__name__)

_CONTRACT = re.compile(r"^([A-Z0-9]{1,6})\s+([A-Z]{3})(\d{2})$")
_NUMERIC = re.compile(r"^([A-Z0-9]{1,6})\s+(\d{2})-(\d{2})$")
_SELECTOR_IDS = (
    "ChartWindowInstrumentSelectorEdit",
    "ChartWindowInstrumentSelector",
)
_UIA_AUTOMATION_ID = 30011
_UIA_VALUE_PATTERN = 10002
_TREE_DESCENDANTS = 4
# Chart rescan period. A walk every few seconds re-enters NinjaTrader's UI
# thread (login dialog included) and stalls Fabric auth.
_CACHE_TTL_SEC = 30.0
_LOCK = threading.Lock()
_CACHE: tuple[float, list[str]] = (0.0, [])
_WALKING = False


def normalize_chart_label(text: str) -> str:
    """``MES DEC26`` and ``MES 12-26`` become ``MES DEC26``. Anything else is empty."""
    raw = " ".join(str(text or "").upper().split())
    named = _CONTRACT.match(raw)
    if named:
        root, month, year = named.group(1), named.group(2), named.group(3)
        if month not in MONTHS:
            return ""
        return f"{root} {month}{year}"
    numeric = _NUMERIC.match(raw)
    if not numeric:
        return ""
    root, month_num, year = numeric.group(1), int(numeric.group(2)), numeric.group(3)
    month = MONTH_CODE_BY_NUM.get(month_num)
    if month is None:
        return ""
    return f"{root} {month}{year}"


def contract_root(symbol: str) -> str:
    label = normalize_chart_label(symbol)
    if label:
        return label.split()[0]
    parts = str(symbol or "").strip().upper().split()
    return parts[0] if parts else ""


def choose_listing(
    configured: str,
    observed: Sequence[str],
    *,
    now_utc: datetime | None = None,
) -> tuple[str, str]:
    """Pick the listing to trade.

    Source is ``chart`` when an open chart matches the configured root,
    ``other_charts`` when charts are open for other roots, ``calendar`` when
    no selector was read, and ``none`` when there is nothing to name.
    """
    charts = _dedupe(observed)
    wanted = contract_root(configured)
    for chart in charts:
        if wanted and contract_root(chart) == wanted:
            return chart, "chart"
    if charts and not wanted:
        return charts[0], "chart"
    if charts and wanted:
        return "", "other_charts"
    rolled = live_listing(configured, now_utc=now_utc)
    if rolled:
        return rolled, "calendar"
    return "", "none"


def subscription_plan(
    configured: str,
    swarm: Sequence[str],
    observed: Sequence[str],
    *,
    now_utc: datetime | None = None,
) -> tuple[str, list[str], str]:
    """Primary listing, subscribe list, and source.

    Open charts replace the configured month list. Calendar roll is used only
    when the selector could not be read.
    """
    charts = _dedupe(observed)
    listing, source = choose_listing(configured, charts, now_utc=now_utc)
    if source in {"chart", "other_charts"}:
        symbols = list(charts)
        if listing and listing in symbols:
            symbols = [listing, *[item for item in symbols if item != listing]]
        return listing, symbols, source
    symbols: list[str] = []
    for raw in [configured, *list(swarm)]:
        rolled = live_listing(str(raw or ""), now_utc=now_utc)
        if rolled and rolled not in symbols:
            symbols.append(rolled)
    if listing and listing not in symbols:
        symbols.insert(0, listing)
    return listing, symbols, source


def _age_words(seconds: float) -> str:
    sec = int(max(0.0, seconds))
    if sec >= 48 * 3600:
        return f"{sec // 86400} dagen"
    if sec >= 3600:
        return f"{sec // 3600} uur {(sec % 3600) // 60} min"
    if sec >= 60:
        return f"{sec // 60} min"
    return f"{sec} s"


def world_sentence(
    *,
    charts: Sequence[str],
    source: str,
    listing: str,
    seal_note: str,
    last_px: float | None,
    price_age_sec: float | None = None,
    bar_quiet: bool = False,
    hand_note: str = "",
) -> str:
    """One Dutch line for the Playground screen."""
    names = _dedupe(charts)
    if source == "chart" and listing:
        head = f"Chart {listing}."
    elif names:
        head = "Geen chart van het ingestelde contract. Open: " + ", ".join(names) + "."
    else:
        head = "Geen open chart gelezen."
    parts = [head]
    note = str(seal_note or "").strip()
    if note:
        parts.append(note)
    if last_px is not None and last_px > 0.0:
        if price_age_sec is None or price_age_sec <= 30.0:
            parts.append(f"Live prijs {last_px:.2f}.")
        elif price_age_sec < 0.0:
            parts.append(f"Tick zonder tijdstempel. Laatste prijs {last_px:.2f}.")
        else:
            parts.append(f"Tick {_age_words(price_age_sec)} oud. Laatste prijs {last_px:.2f}.")
    if bar_quiet:
        parts.append("Supervisor-loop publiceert geen nieuwe bar.")
    hand = str(hand_note or "").strip()
    if hand:
        parts.append(hand)
    return " ".join(parts)


def _is_chart_window_name(name: str) -> bool:
    """True for a floating or tabbed chart window. Login is not a chart."""
    return "chart" in str(name or "").lower()


def _is_control_center_name(name: str) -> bool:
    """Docked charts live here when no window is titled Chart."""
    return "control center" in str(name or "").lower()


def _selector_hwnds(windows: list[tuple[int, str]]) -> list[int]:
    """Chart windows win. Control Center is the fallback. Login is neither."""
    charts = [hwnd for hwnd, title in windows if _is_chart_window_name(title)]
    if charts:
        return charts
    return [hwnd for hwnd, title in windows if _is_control_center_name(title)]


def read_open_charts(*, now: float | None = None) -> list[str]:
    """Listings currently selected on NinjaTrader chart windows. Empty if unread."""
    global _CACHE, _WALKING
    stamp = time.time() if now is None else float(now)
    with _LOCK:
        cached_at, cached = _CACHE
        if stamp - cached_at < _CACHE_TTL_SEC and cached_at > 0.0:
            return list(cached)
        if _WALKING:
            return list(cached)
        _WALKING = True
    labels: list[str] | None = None
    try:
        try:
            raw = _read_uia_values()
        except Exception:
            logger.debug("open_charts.uia_failed", exc_info=True)
            raw = []
        labels = _dedupe(raw)
    finally:
        with _LOCK:
            _WALKING = False
            if labels is not None:
                _CACHE = (stamp, labels)
    return list(_CACHE[1])


def clear_open_chart_cache() -> None:
    global _CACHE, _WALKING
    with _LOCK:
        _CACHE = (0.0, [])
        _WALKING = False


def _dedupe(values: Sequence[str]) -> list[str]:
    found: list[str] = []
    for raw in values:
        label = normalize_chart_label(raw)
        if label and label not in found:
            found.append(label)
    return found


def _nt_pids() -> set[int]:
    import psutil

    pids: set[int] = set()
    for proc in psutil.process_iter(["name"]):
        name = str((proc.info or {}).get("name") or "")
        if name.lower().startswith("ninjatrader"):
            pids.add(int(proc.pid))
    return pids


def _top_level_nt_windows() -> list[tuple[int, str]]:
    """Visible NinjaTrader window titles via Win32. This does not start UI Automation."""
    import sys

    if sys.platform != "win32":
        return []
    pids = _nt_pids()
    if not pids:
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) not in pids:
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = str(buf.value or "")
        if title:
            found.append((int(hwnd), title))
        return True

    user32.EnumWindows(_enum, 0)
    return found


def _read_uia_values() -> list[str]:
    """Selector text. UI Automation starts only for a chart window, never the login dialog."""
    hwnds = _selector_hwnds(_top_level_nt_windows())
    if not hwnds:
        return []
    return _read_chart_selectors(hwnds)


def _read_chart_selectors(hwnds: list[int]) -> list[str]:
    """Instrument selector inside the already chosen windows. Fails closed per window."""
    import comtypes
    import comtypes.client

    try:
        comtypes.CoInitialize()
    except OSError:
        pass
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as uia_types

    automation = comtypes.CoCreateInstance(
        uia_types.CUIAutomation._reg_clsid_,
        interface=uia_types.IUIAutomation,
        clsctx=comtypes.CLSCTX_INPROC_SERVER,
    )
    values: list[str] = []
    for hwnd in hwnds:
        window = _element_from_handle(automation, hwnd)
        if window is None:
            continue
        try:
            values.extend(_selector_texts(automation, window, uia_types))
        except Exception:
            logger.debug("open_charts.selector_failed hwnd=%s", hwnd, exc_info=True)
    return values


def _selector_texts(automation: object, window: object, uia_types: object) -> list[str]:
    values: list[str] = []
    for selector_id in _SELECTOR_IDS:
        condition = automation.CreatePropertyCondition(_UIA_AUTOMATION_ID, selector_id)  # type: ignore[attr-defined]
        found = window.FindAll(_TREE_DESCENDANTS, condition)  # type: ignore[attr-defined]
        count = int(getattr(found, "Length", 0) or 0)
        for child_index in range(count):
            text = _element_value(found.GetElement(child_index), uia_types)
            if text:
                values.append(text)
    return values


def _element_from_handle(automation: object, hwnd: int) -> object | None:
    import ctypes

    for handle in (hwnd, ctypes.c_void_p(hwnd)):
        try:
            window = automation.ElementFromHandle(handle)  # type: ignore[attr-defined]
        except Exception:
            continue
        if window is not None:
            return window
    return None


def _element_value(element: object, uia_types: object) -> str:
    try:
        unknown = element.GetCurrentPattern(_UIA_VALUE_PATTERN)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return ""
    if unknown is None:
        return ""
    try:
        pattern = unknown.QueryInterface(uia_types.IUIAutomationValuePattern)  # type: ignore[attr-defined]
        return str(pattern.CurrentValue or "")
    except (AttributeError, OSError, TypeError, ValueError):
        return ""
