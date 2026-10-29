"""client_order_id → strategy_id map (S2). Unmapped fills never observe a random signal."""

from __future__ import annotations

from dataclasses import dataclass


class FillIndexRefused(ValueError):
    """Index write refused. Missing ids are not stored as empty keys."""


@dataclass(frozen=True, slots=True)
class FillIndexEntry:
    strategy_id: str
    expected_horizon: int


class FillIndex:
    """In-process map. S0 hypothetical ids and S3 client_order_id share this type."""

    def __init__(self) -> None:
        self._items: dict[str, FillIndexEntry] = {}

    def remember(self, client_order_id: str, strategy_id: str, expected_horizon: int) -> FillIndexEntry:
        cid = str(client_order_id or "").strip()
        sid = str(strategy_id or "").strip()
        if not cid:
            raise FillIndexRefused("client_order_id_missing")
        if not sid:
            raise FillIndexRefused("strategy_id_missing")
        if isinstance(expected_horizon, bool) or not isinstance(expected_horizon, int):
            raise FillIndexRefused("expected_horizon_missing")
        if expected_horizon < 1:
            raise FillIndexRefused("expected_horizon_missing")
        entry = FillIndexEntry(strategy_id=sid, expected_horizon=int(expected_horizon))
        self._items[cid] = entry
        return entry

    def lookup(self, client_order_id: str) -> FillIndexEntry | None:
        cid = str(client_order_id or "").strip()
        if not cid:
            return None
        return self._items.get(cid)

    def __len__(self) -> int:
        return len(self._items)
