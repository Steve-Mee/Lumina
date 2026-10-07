"""Futures contract symbol parsing and roll helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

# CME-style quarterly roots (MES/ES/NQ/MNQ) roll MAR → JUN → SEP → DEC.
QUARTERLY_MONTH_CODES = ("MAR", "JUN", "SEP", "DEC")
MONTH_CODE_BY_NUM = {num: code for code, num in MONTHS.items()}
# Volume typically leaves the expiring listing ~8 calendar days before 3rd Friday.
VOLUME_ROLL_LEAD_DAYS = 8

def parse_contract_symbol(symbol: str) -> tuple[str | None, int | None, int | None]:
    text = str(symbol or "").strip().upper()
    parts = text.split()
    if len(parts) < 2:
        return None, None, None

    code = parts[1]
    if len(code) != 5:
        return None, None, None

    month = MONTHS.get(code[:3])
    if month is None:
        return None, None, None

    try:
        year = 2000 + int(code[3:5])
    except ValueError:
        return None, None, None

    root = parts[0] if parts else None
    return root, month, year


def third_friday(year: int, month: int) -> datetime:
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    weekday = first.weekday()  # Monday=0
    days_to_friday = (4 - weekday) % 7
    first_friday_day = 1 + days_to_friday
    third_friday_day = first_friday_day + 14
    return datetime(year, month, third_friday_day, 23, 59, 59, tzinfo=timezone.utc)


def volume_roll_utc(year: int, month: int) -> datetime:
    """Approximate CME volume-roll instant (3rd Friday minus lead days)."""
    return third_friday(int(year), int(month)) - timedelta(days=VOLUME_ROLL_LEAD_DAYS)


def _prior_quarterly(month_code: str, year: int) -> tuple[str, int]:
    idx = QUARTERLY_MONTH_CODES.index(month_code)
    prev_code = QUARTERLY_MONTH_CODES[(idx - 1) % len(QUARTERLY_MONTH_CODES)]
    prev_year = int(year) - (1 if month_code == "MAR" else 0)
    return prev_code, prev_year


def next_quarterly_contract(symbol: str) -> str:
    """Advance one CME quarterly listing. Unparseable input is returned unchanged."""
    normalized = str(symbol or "").strip().upper()
    root, month, year = parse_contract_symbol(normalized)
    if root is None or month is None or year is None:
        return normalized
    month_code = MONTH_CODE_BY_NUM.get(int(month))
    if month_code not in QUARTERLY_MONTH_CODES:
        return normalized
    idx = QUARTERLY_MONTH_CODES.index(month_code)
    next_code = QUARTERLY_MONTH_CODES[(idx + 1) % len(QUARTERLY_MONTH_CODES)]
    next_year = int(year) + (1 if next_code == "MAR" else 0)
    return f"{root} {next_code}{next_year % 100:02d}"


def is_past_volume_roll(symbol: str, *, now_utc: datetime | None = None) -> bool:
    """True when the listing is past the volume-roll instant (still listed until expiry)."""
    _root, month, year = parse_contract_symbol(symbol)
    if month is None or year is None:
        return False
    now = now_utc or datetime.now(timezone.utc)
    return now > volume_roll_utc(int(year), int(month))


def roll_to_liquid_front_month(symbol: str, *, now_utc: datetime | None = None) -> str:
    """Advance to the liquid front-month using volume-roll, not expiry.

    Order-gate stale checks stay on 3rd-Friday expiry so a still-listed contract
    is not blocked. Birth history must not train the thin next-quarter book.
    """
    current = str(symbol or "").strip().upper()
    now = now_utc or datetime.now(timezone.utc)
    seen: set[str] = set()
    for _ in range(8):
        if not current or current in seen:
            return current
        seen.add(current)
        if not is_past_volume_roll(current, now_utc=now):
            return current
        nxt = next_quarterly_contract(current)
        if nxt == current:
            return current
        current = nxt
    return current


def front_month_tenure(
    symbol: str,
) -> tuple[datetime | None, datetime | None]:
    """Liquid-front window ``[prior_volume_roll, this_volume_roll)``."""
    _root, month, year = parse_contract_symbol(symbol)
    if month is None or year is None:
        return None, None
    month_code = MONTH_CODE_BY_NUM.get(int(month))
    if month_code not in QUARTERLY_MONTH_CODES:
        return None, None
    end = volume_roll_utc(int(year), int(month))
    prev_code, prev_year = _prior_quarterly(month_code, int(year))
    prev_month = MONTHS[prev_code]
    start = volume_roll_utc(int(prev_year), int(prev_month))
    return start, end


def is_stale_contract_symbol(symbol: str, *, now_utc: datetime | None = None) -> bool:
    """Return True when a futures contract symbol is clearly past expiry month.

    Expected format example: "MES JUN26".
    If parsing fails, return False to avoid false blocking.
    """
    _root, month, year = parse_contract_symbol(symbol)
    if month is None or year is None:
        return False

    now = now_utc or datetime.now(timezone.utc)
    # Calendar-aware expiry approximation (3rd Friday of contract month, CME style futures).
    expiry_utc = third_friday(int(year), int(month))
    return now > expiry_utc


_KNOWN_ROOTS = frozenset({"MES", "ES", "MNQ", "NQ", "MYM", "YM", "M2K", "RTY", "CL", "GC"})


def front_month_symbol(root: str, *, now_utc: datetime | None = None) -> str:
    """Liquid quarterly listing for a bare root. ``MES`` on 28 Sep 2026 is ``MES DEC26``."""
    token = str(root or "").strip().upper().split()[0]
    if not token:
        return ""
    now = now_utc or datetime.now(timezone.utc)
    seed = f"{token} MAR{now.year % 100:02d}"
    return roll_to_liquid_front_month(seed, now_utc=now)


def live_listing(symbol: str, *, now_utc: datetime | None = None) -> str:
    """Contract NT can actually serve. Rolls past the volume roll. A bare root becomes the front month.

    An open chart on the liquid month is the book. A configured expired month is not.
    """
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    root, month, year = parse_contract_symbol(raw)
    if root and month is not None and year is not None:
        return roll_to_liquid_front_month(raw, now_utc=now_utc)
    token = raw.split()[0]
    if token in _KNOWN_ROOTS:
        return front_month_symbol(token, now_utc=now_utc)
    return raw


def roll_stale_contract_symbol(symbol: str, *, now_utc: datetime | None = None) -> str:
    """Return the next quarterly contract when *symbol* is stale; otherwise unchanged."""
    normalized = str(symbol or "").strip().upper()
    root, month, year = parse_contract_symbol(normalized)
    if root is None or month is None or year is None:
        return normalized

    now = now_utc or datetime.now(timezone.utc)
    if now <= third_friday(int(year), int(month)):
        return normalized

    month_code = MONTH_CODE_BY_NUM.get(int(month))
    if month_code not in QUARTERLY_MONTH_CODES:
        return normalized

    idx = QUARTERLY_MONTH_CODES.index(month_code)
    next_code = QUARTERLY_MONTH_CODES[(idx + 1) % len(QUARTERLY_MONTH_CODES)]
    next_year = int(year) + (1 if next_code == "MAR" else 0)
    return f"{root} {next_code}{next_year % 100:02d}"
