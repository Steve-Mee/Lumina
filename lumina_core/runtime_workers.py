"""Thin compat hub for runtime worker threads (D2 subs 4–18).

All non-trivial logic lives in bounded engine modules; this file re-exports callables
for bootstrap, tests, and SupervisorPhaseStateMachine lazy imports.
"""

from __future__ import annotations

import time  # noqa: F401 — tests monkeypatch runtime_workers.time
from datetime import datetime  # noqa: F401 — tests monkeypatch runtime_workers.datetime

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.price_dupe_resolver import PriceDupeResolver
from lumina_core.engine.pre_dream_daemon import PreDreamDaemon
from lumina_core.engine.voice_legacy_handler import VoiceLegacyHandler

TRADER_LEAGUE_WEBHOOK_URL = "http://localhost:8000/webhook/trade"


def _paper_instrument(app: RuntimeContext) -> str:
    return PriceDupeResolver(app=app).paper_instrument()


def _paper_sync_sim_from_broker(app: RuntimeContext, broker: object, instrument: str) -> None:
    return PriceDupeResolver(app=app).paper_sync_sim_from_broker(broker, instrument)


def _paper_store_round_ledger_from_last_fill(
    app: RuntimeContext, broker: object, instrument: str, open_signal: str
) -> None:
    return PriceDupeResolver(app=app).paper_store_round_ledger_from_last_fill(broker, instrument, open_signal)


def _paper_clear_round_ledger(app: RuntimeContext) -> None:
    return PriceDupeResolver(app=app).paper_clear_round_ledger()


def _compute_session_kpis(app: RuntimeContext) -> dict[str, float]:
    from lumina_core.engine.runtime_monitoring_service import RuntimeMonitoringService

    return RuntimeMonitoringService(app=app).compute_session_kpis()


def _publish_runtime_monitoring_snapshot(app: RuntimeContext) -> None:
    from lumina_core.engine.runtime_monitoring_service import RuntimeMonitoringService

    RuntimeMonitoringService(app=app).publish_snapshot()


def _push_trader_league_trade(app: RuntimeContext, **kwargs: object) -> None:
    from lumina_core.engine.trader_league_webhook import TraderLeagueWebhook

    TraderLeagueWebhook(app=app, webhook_url=TRADER_LEAGUE_WEBHOOK_URL).push(**kwargs)  # type: ignore[arg-type]


def _enforce_real_eod_force_close(app: RuntimeContext, price: float) -> bool:
    from lumina_core.engine.eod_force_close_service import EODForceCloseService

    container = getattr(app, "container", None)
    broker = getattr(container, "broker", None) if container is not None else None
    service = EODForceCloseService(app=app, broker=broker, container=container)
    return service.enforce_eod_force_close(price)


def pre_dream_daemon(app: RuntimeContext) -> None:
    PreDreamDaemon(app=app).run()


def voice_listener_thread(app: RuntimeContext) -> None:
    VoiceLegacyHandler(app=app).run_listener(app=app)


def _old_supervisor_loop(app: RuntimeContext) -> None:
    from lumina_core.engine.runtime_workers_facade import run_supervisor_loop

    run_supervisor_loop(app)


def _old_supervisor_loop_inner(app: RuntimeContext) -> None:
    from lumina_core.engine.runtime_workers_facade import SupervisorLoopRunner

    SupervisorLoopRunner(app=app).run_inner()


def run_forever_loop(app: RuntimeContext) -> None:
    from lumina_core.engine.runtime_workers_facade import run_forever

    run_forever(app)


def state_persist_daemon(app: RuntimeContext, interval_seconds: int = 30) -> None:
    from lumina_core.engine.state_persist_daemon import StatePersistDaemon

    StatePersistDaemon(app=app, interval_seconds=interval_seconds).run()


def supervisor_loop(app: RuntimeContext) -> None:
    _old_supervisor_loop(app)
