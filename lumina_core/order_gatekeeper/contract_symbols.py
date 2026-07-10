"""Futures contract symbol parsing and roll helpers."""

from __future__ import annotations

from datetime import datetime, timezone

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
