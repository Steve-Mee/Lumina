from datetime import datetime, timezone
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional, cast

import yaml
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.types import ASGIApp

from backend.database import CommunityBible, CommunityReflection, Participant, SessionLocal, TradeEntry
from backend.models import BibleUpload, ReflectionUpload, TradeSubmit
from backend.monitoring_endpoints import router as monitoring_router, set_observability_service
from backend.evolution_endpoints import router as evolution_router
from backend.evolution_endpoints import set_observability_service as set_evolution_obs_service
from backend.evolution_endpoints import set_security_module as set_evolution_security_module
from lumina_core.broker.broker_bridge import broker_factory
from lumina_core.broker.broker_bridge import Order
from lumina_core.engine.engine_config import EngineConfig

# Import security module — lumina_core is installed as a package, no sys.path needed
from lumina_core.security import get_security_module
from lumina_core.monitoring import ObservabilityService

logger = logging.getLogger(__name__)
_EMERGENCY_LOCK = threading.Lock()

_LUMINA_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Ensure backend sees the same env as launcher/runtime.
load_dotenv(_LUMINA_REPO_ROOT / ".env")
load_dotenv()


def _embedded_ui_dist_dir() -> Path:
    override = os.getenv("LUMINA_EMBEDDED_UI_DIST", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (_LUMINA_REPO_ROOT / "frontend" / "dist").resolve()


_UI_DIST = _embedded_ui_dist_dir()


class LuminaEmbeddedUIMiddleware(BaseHTTPMiddleware):
    """Serve `frontend/dist` under `/ui` on every request (no import-time gate).

    Avoids 404 after `npm run build:embedded` when the backend was started before `dist/` existed.
    """

    def __init__(self, app: ASGIApp, *, dist_dir: Path):
        super().__init__(app)
        self._dist = dist_dir.resolve()

    @staticmethod
    def _apply_ui_cache_headers(*, response: FileResponse, is_index: bool) -> FileResponse:
        if is_index:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.scope["type"] != "http":
            return await call_next(request)
        if request.method not in ("GET", "HEAD"):
            return await call_next(request)
        path = request.url.path
        if path != "/ui" and not path.startswith("/ui/"):
            return await call_next(request)

        idx = self._dist / "index.html"
        if not idx.is_file():
            return JSONResponse(
                {
                    "detail": "Embedded React UI not built",
                    "hint": (
                        "Run from repo root: cd frontend && npm ci && npm run build:embedded "
                        "(or scripts/build_embedded_ui.ps1). Reload this URL after the build."
                    ),
                },
                status_code=503,
            )

        tail = path[len("/ui") :].lstrip("/")
        if not tail:
            return self._apply_ui_cache_headers(response=FileResponse(idx), is_index=True)

        target = (self._dist / tail).resolve()
        root = self._dist.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        if target.is_file():
            return self._apply_ui_cache_headers(response=FileResponse(target), is_index=False)
        return self._apply_ui_cache_headers(response=FileResponse(idx), is_index=True)


RECONCILIATION_STATUS_FILE = os.getenv(
    "TRADER_LEAGUE_RECONCILIATION_STATUS_FILE",
    os.getenv("TRADE_RECONCILER_STATUS_FILE", "state/trade_reconciler_status.json"),
)

# Load config
CONFIG_PATH = os.getenv("LUMINA_CONFIG", "config.yaml")
with open(CONFIG_PATH, "r") as f:
    FULL_CONFIG = yaml.safe_load(f)
SECURITY_CONFIG = FULL_CONFIG.get("security", {})

# Initialize security module
SECURITY = get_security_module(SECURITY_CONFIG)
set_evolution_security_module(SECURITY)

# Validate dangerous configs at startup
validator = SECURITY["config_validator"]
violations = validator.validate(FULL_CONFIG)
if violations:
    logger.error(f"Dangerous config values detected: {violations}")
    raise ValueError(f"Startup validation failed: {violations}")

app = FastAPI(title="Trader League Live - Powered by LUMINA")

# ── Observability layer ────────────────────────────────────────────────────────
_obs = ObservabilityService.from_config(FULL_CONFIG)
_obs.start()
set_observability_service(_obs)
set_evolution_obs_service(_obs)
app.include_router(monitoring_router)
app.include_router(evolution_router)

app.add_middleware(LuminaEmbeddedUIMiddleware, dist_dir=_UI_DIST)
if (_UI_DIST / "index.html").is_file():
    logger.info("Embedded React monitoring UI served under /ui from %s", _UI_DIST)
else:
    logger.info(
        "Embedded React UI not present at %s; GET /ui returns 503 until built "
        "(cd frontend && npm ci && npm run build:embedded)",
        _UI_DIST,
    )

# Apply strict CORS middleware (no wildcard) + lokale Vite dev (:5173) origins
try:
    from api.monitoring import extend_cors_origins_with_local_vite_dev

    cors_origins = extend_cors_origins_with_local_vite_dev(SECURITY["config"].cors_allowed_origins)
except ImportError:  # pragma: no cover
    cors_origins = list(SECURITY["config"].cors_allowed_origins)

if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info(
        "CORS configured for %s origins (Vite :5173 merged via api.monitoring when available)",
        len(cors_origins),
    )
else:
    logger.warning("CORS is disabled (allow_origins is empty)")


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> dict[str, Any]:
    """Dependency to verify API key authentication."""
    if not x_api_key:
        SECURITY["audit_log"].log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="API key required")

    key_meta = SECURITY["api_key"].verify_api_key(x_api_key)
    if not key_meta:
        SECURITY["audit_log"].log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    SECURITY["audit_log"].log_auth_attempt(key_meta.get("name", "api_key"), True, "api_key")
    return {"api_key": x_api_key, "metadata": key_meta}


async def verify_admin_role(auth: dict[str, Any] = Depends(verify_api_key)) -> dict[str, Any]:
    """Dependency to verify admin role for destructive operations."""
    if not SECURITY["config"].admin_role_required:
        return auth

    role = auth["metadata"].get("role", "user")
    if role != "admin":
        SECURITY["audit_log"].log_unauthorized_access(
            auth["metadata"].get("name", "unknown"),
            "admin_operation",
            f"insufficient_role_{role}",
        )
        raise HTTPException(status_code=403, detail="Admin role required")

    return auth


async def check_rate_limit(x_api_key: Optional[str] = Header(None)) -> None:
    """Dependency to check rate limiting."""
    client_id = x_api_key or "anonymous"
    if not SECURITY["rate_limiter"].is_allowed(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _execute_emergency_flatten() -> dict[str, Any]:
    if not _EMERGENCY_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Emergency stop already in progress")
    try:
        broker = _create_emergency_broker()
        try:
            broker.connect()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Broker connect failed: {exc}") from exc

        try:
            try:
                positions = broker.get_positions()
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"Broker positions unavailable: {exc}") from exc

            flattened: list[dict[str, Any]] = []
            for pos in positions:
                qty = int(getattr(pos, "quantity", 0) or 0)
                if qty == 0:
                    continue
                symbol = str(getattr(pos, "symbol", "") or "").strip()
                if not symbol:
                    continue
                close_side = "SELL" if qty > 0 else "BUY"
                result = broker.submit_order(
                    Order(
                        symbol=symbol,
                        side=close_side,
                        quantity=abs(qty),
                        order_type="MARKET",
                        stop_loss=0.0,
                        take_profit=0.0,
                        metadata={
                            "reason": "api_emergency_stop",
                            "skip_admission_chain_recheck": True,
                        },
                    )
                )
                if not bool(getattr(result, "accepted", False)):
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            f"Emergency flatten rejected for {symbol}: "
                            f"{getattr(result, 'status', 'rejected')} {getattr(result, 'message', '')}"
                        ),
                    )
                flattened.append(
                    {
                        "symbol": symbol,
                        "closed_qty": abs(qty),
                        "side": close_side,
                        "order_id": str(getattr(result, "order_id", "") or ""),
                        "status": str(getattr(result, "status", "accepted") or "accepted"),
                    }
                )

            return {
                "status": "ok",
                "flattened_count": len(flattened),
                "flattened": flattened,
                "message": "Emergency flatten executed.",
            }
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass
    finally:
        _EMERGENCY_LOCK.release()


def _execute_cancel_all_orders() -> dict[str, Any]:
    if not _EMERGENCY_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Emergency stop already in progress")
    try:
        broker = _create_emergency_broker()
        try:
            broker.connect()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Broker connect failed: {exc}") from exc
        try:
            try:
                result = broker.cancel_all_orders()
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"Cancel-all failed: {exc}") from exc
            cancelled_count = int(result.get("cancelled_count", 0) or 0)
            return {
                "status": "ok",
                "cancelled_count": cancelled_count,
                "cancelled": result.get("cancelled", []),
                "message": "Cancel-all executed.",
            }
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass
    finally:
        _EMERGENCY_LOCK.release()


def _create_emergency_broker() -> Any:
    """Build a minimal broker instance for emergency actions.

    Do not bootstrap the full ApplicationContainer here: emergency endpoints must
    remain available even when optional inference/runtime subsystems are degraded.
    """
    try:
        cfg = EngineConfig()
        return broker_factory(config=cfg, engine=None, logger=logger)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Emergency broker setup failed: {exc}") from exc


@app.post("/webhook/trade")
def submit_trade(
    trade: TradeSubmit,
    _auth: dict[str, Any] = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
) -> dict[str, int | str]:
    return _ingest_trade(trade)


@app.post("/orders/emergency-stop")
def emergency_stop_orders(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    cancel_result = _execute_cancel_all_orders()
    flatten_result = _execute_emergency_flatten()
    result = {
        "status": "ok",
        "cancelled_count": int(cancel_result.get("cancelled_count", 0) or 0),
        "flattened_count": int(flatten_result.get("flattened_count", 0) or 0),
        "cancelled": cancel_result.get("cancelled", []),
        "flattened": flatten_result.get("flattened", []),
        "message": "Emergency stop executed (cancel-all + flatten).",
    }
    SECURITY["audit_log"].log_admin_action(
        username=admin_auth["metadata"].get("name", "unknown"),
        action="emergency_stop_orders",
        resource="/orders/emergency-stop",
        details={
            "cancelled_count": int(result.get("cancelled_count", 0) or 0),
            "flattened_count": int(result.get("flattened_count", 0) or 0),
        },
    )
    logger.warning(
        "Admin emergency stop executed by %s; cancelled=%s flattened=%s",
        admin_auth["metadata"].get("name", "unknown"),
        int(result.get("cancelled_count", 0) or 0),
        int(result.get("flattened_count", 0) or 0),
    )
    return result


@app.post("/orders/flatten")
def flatten_orders_alias(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    result = _execute_emergency_flatten()
    SECURITY["audit_log"].log_admin_action(
        username=admin_auth["metadata"].get("name", "unknown"),
        action="flatten_open_positions",
        resource="/orders/flatten",
        details={"flattened_count": int(result.get("flattened_count", 0) or 0)},
    )
    return result


@app.post("/orders/cancel-all")
def cancel_all_orders_alias(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    result = _execute_cancel_all_orders()
    SECURITY["audit_log"].log_admin_action(
        username=admin_auth["metadata"].get("name", "unknown"),
        action="cancel_all_orders",
        resource="/orders/cancel-all",
        details={"cancelled_count": int(result.get("cancelled_count", 0) or 0)},
    )
    return result


@app.delete("/orders")
def delete_orders_alias(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    result = _execute_cancel_all_orders()
    SECURITY["audit_log"].log_admin_action(
        username=admin_auth["metadata"].get("name", "unknown"),
        action="cancel_all_orders",
        resource="/orders",
        details={"cancelled_count": int(result.get("cancelled_count", 0) or 0)},
    )
    return result


def _ingest_trade(trade: TradeSubmit) -> dict[str, int | str]:
    """Persist a trade payload. Separated to keep alias behavior identical under auth deps."""
    db = SessionLocal()
    try:
        participant = db.query(Participant).filter_by(name=trade.participant).first()
        if not participant:
            participant = Participant(
                name=trade.participant,
                mode=trade.mode,
                is_lumina=1 if "LUMINA" in trade.participant.upper() else 0,
            )
            db.add(participant)
            db.commit()
            db.refresh(participant)

        entry = TradeEntry(
            participant_id=participant.id,
            symbol=trade.symbol,
            signal=trade.signal,
            entry=trade.entry,
            exit=trade.exit,
            qty=trade.qty,
            pnl=trade.pnl,
            broker_fill_id=trade.broker_fill_id,
            commission=trade.commission,
            slippage_points=trade.slippage_points,
            fill_latency_ms=trade.fill_latency_ms,
            reconciliation_status=trade.reconciliation_status,
            reflection=trade.reflection,
            chart_base64=trade.chart_base64,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {"status": "ok", "trade_id": int(getattr(entry, "id", 0) or 0)}
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_os/backend/app.py:154")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Trade ingest failed: {exc}") from exc
    finally:
        db.close()


@app.post("/trades")
def submit_trade_alias(
    trade: TradeSubmit,
    _auth: dict[str, Any] = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
) -> dict[str, int | str]:
    # Compatibility endpoint used by dashboard/tests; same behavior as webhook.
    return _ingest_trade(trade)


@app.get("/trades")
def get_trades(
    limit: int = Query(default=100, ge=1, le=1000),
    participant: str | None = None,
    _auth: dict[str, Any] = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = db.query(TradeEntry).order_by(TradeEntry.ts.desc()).limit(limit)
        rows = query.all()
        participant_map = {p.id: p for p in db.query(Participant).all()}

        output: list[dict[str, Any]] = []
        participant_filter = participant.strip().lower() if participant else None
        for row in rows:
            row_any = cast(Any, row)
            p = participant_map.get(row.participant_id)
            p_name = p.name if p else "unknown"
            if participant_filter and p_name.lower() != participant_filter:
                continue
            ts_value = getattr(row_any, "ts", None)
            ts_iso = ts_value.isoformat() if isinstance(ts_value, datetime) else None
            output.append(
                {
                    "id": int(getattr(row_any, "id", 0) or 0),
                    "participant": p_name,
                    "mode": p.mode if p else "unknown",
                    "ts": ts_iso,
                    "symbol": getattr(row_any, "symbol", None),
                    "signal": getattr(row_any, "signal", None),
                    "entry": getattr(row_any, "entry", None),
                    "exit": getattr(row_any, "exit", None),
                    "qty": getattr(row_any, "qty", None),
                    "pnl": getattr(row_any, "pnl", None),
                    "broker_fill_id": getattr(row_any, "broker_fill_id", None),
                    "commission": getattr(row_any, "commission", None),
                    "slippage_points": getattr(row_any, "slippage_points", None),
                    "fill_latency_ms": getattr(row_any, "fill_latency_ms", None),
                    "reconciliation_status": getattr(row_any, "reconciliation_status", None),
                    "sharpe": getattr(row_any, "sharpe", None),
                    "maxdd": getattr(row_any, "maxdd", None),
                    "reflection": getattr(row_any, "reflection", None),
                    "chart_base64": getattr(row_any, "chart_base64", None),
                }
            )
        return output
    finally:
        db.close()


@app.get("/leaderboard")
def get_leaderboard() -> dict[str, list[dict[str, int | float | str]] | str]:
    """Public read-only endpoint for aggregated rankings.

    Security policy exception: this endpoint is intentionally public to support
    anonymous dashboard consumption.
    """
    db = SessionLocal()
    try:
        trades = db.query(TradeEntry).all()
        participants = {p.id: p for p in db.query(Participant).all()}

        grouped: dict[int, dict[str, int | float | str]] = {}
        for trade in trades:
            trade_any = cast(Any, trade)
            participant_id = int(getattr(trade_any, "participant_id", 0) or 0)
            participant = participants.get(trade.participant_id)
            if participant is None:
                continue
            participant_any = cast(Any, participant)
            if participant_id not in grouped:
                grouped[participant_id] = {
                    "participant": str(getattr(participant_any, "name", "unknown")),
                    "mode": str(getattr(participant_any, "mode", "unknown")),
                    "is_lumina": int(getattr(participant_any, "is_lumina", 0) or 0),
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0.0,
                    "avg_pnl": 0.0,
                    "win_rate": 0.0,
                }

            row = grouped[participant_id]
            row["trades"] = int(row["trades"]) + 1
            pnl_value = float(getattr(trade_any, "pnl", 0.0) or 0.0)
            row["total_pnl"] = float(row["total_pnl"]) + pnl_value
            if pnl_value > 0:
                row["wins"] = int(row["wins"]) + 1
            elif pnl_value < 0:
                row["losses"] = int(row["losses"]) + 1

        leaderboard: list[dict[str, int | float | str]] = []
        for row in grouped.values():
            trades_count = int(row["trades"])
            total_pnl = float(row["total_pnl"])
            wins = int(row["wins"])
            row["avg_pnl"] = round(total_pnl / trades_count, 4) if trades_count else 0.0
            row["win_rate"] = round((wins / trades_count) * 100, 2) if trades_count else 0.0
            row["total_pnl"] = round(total_pnl, 4)
            leaderboard.append(row)

        leaderboard.sort(key=lambda item: float(item["total_pnl"]), reverse=True)
        return {
            "leaderboard": leaderboard[:50],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        db.close()


@app.get("/reconciliation-status")
def get_reconciliation_status(
    _auth: dict[str, Any] = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        if not os.path.exists(RECONCILIATION_STATUS_FILE):
            return {
                "status": "unavailable",
                "connection_state": "offline",
                "pending_count": 0,
                "pending_symbols": [],
                "last_error": None,
                "last_message_ts": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        with open(RECONCILIATION_STATUS_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Invalid reconciliation status payload")
        return payload
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_os/backend/app.py:303")
        raise HTTPException(status_code=500, detail=f"Reconciliation status unavailable: {exc}") from exc


@app.delete("/trades")
def delete_all_trades(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, int]:
    """Delete all trades. Requires admin authentication."""
    db = SessionLocal()
    try:
        deleted = db.query(TradeEntry).delete()
        db.commit()

        # Audit log
        SECURITY["audit_log"].log_admin_action(
            username=admin_auth["metadata"].get("name", "unknown"),
            action="delete_all_trades",
            resource="/trades",
            details={"deleted_count": deleted},
        )
        logger.info(f"Admin action: deleted {deleted} trades")

        return {"deleted": deleted}
    finally:
        db.close()


@app.delete("/demo-data")
def delete_demo_data(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, int]:
    """Delete demo data. Requires admin authentication."""
    db = SessionLocal()
    try:
        demo_participants = db.query(Participant).filter(Participant.name.like("DEMO_%")).all()
        demo_ids = [item.id for item in demo_participants]

        deleted_trades = 0
        if demo_ids:
            deleted_trades = (
                db.query(TradeEntry).filter(TradeEntry.participant_id.in_(demo_ids)).delete(synchronize_session=False)
            )
        deleted_participants = (
            db.query(Participant).filter(Participant.name.like("DEMO_%")).delete(synchronize_session=False)
        )
        db.commit()

        # Audit log
        SECURITY["audit_log"].log_admin_action(
            username=admin_auth["metadata"].get("name", "unknown"),
            action="delete_demo_data",
            resource="/demo-data",
            details={
                "deleted_participants": deleted_participants,
                "deleted_trades": deleted_trades,
            },
        )
        logger.info(f"Admin action: deleted {deleted_participants} demo participants and {deleted_trades} trades")

        return {
            "deleted_participants": deleted_participants,
            "deleted_trades": deleted_trades,
        }
    finally:
        db.close()


@app.post("/upload/bible")
def upload_bible(
    upload: BibleUpload,
    _auth: dict[str, Any] = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
) -> dict[str, str]:
    db = SessionLocal()
    try:
        bible = db.query(CommunityBible).filter_by(trader_name=upload.trader_name).first()
        if bible:
            bible_any = cast(Any, bible)
            bible_any.evolvable_layer = upload.evolvable_layer
            bible_any.performance_score = float(upload.backtest_results.get("sharpe", 0.0) or 0.0)
        else:
            bible = CommunityBible(
                trader_name=upload.trader_name,
                bible_hash=str(hash(str(upload.evolvable_layer))),
                performance_score=float(upload.backtest_results.get("sharpe", 0.0) or 0.0),
                evolvable_layer=upload.evolvable_layer,
            )
            db.add(bible)
        db.commit()
        return {"status": "ok", "message": "Bible added to global wisdom"}
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_os/backend/app.py:394")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bible upload failed: {exc}") from exc
    finally:
        db.close()


@app.post("/upload/reflection")
def upload_reflection(
    upload: ReflectionUpload,
    _auth: dict[str, Any] = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
) -> dict[str, str]:
    db = SessionLocal()
    try:
        bible = db.query(CommunityBible).filter_by(trader_name=upload.trader_name).first()
        if not bible:
            raise HTTPException(status_code=404, detail="Bible not found")

        ref = CommunityReflection(
            bible_id=bible.id,
            reflection=upload.reflection,
            key_lesson=upload.key_lesson,
            suggested_update=upload.suggested_update,
            pnl_impact=upload.pnl_impact,
        )
        db.add(ref)
        bible_any = cast(Any, bible)
        bible_any.reflection_count = int(getattr(bible_any, "reflection_count", 0) or 0) + 1
        db.commit()
        return {"status": "ok"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_os/backend/app.py:428")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Reflection upload failed: {exc}") from exc
    finally:
        db.close()


@app.get("/global_wisdom")
def get_global_wisdom() -> dict[str, Any]:
    """Public read-only endpoint for top community wisdom snapshots.

    Security policy exception: this endpoint is intentionally public to support
    anonymous dashboard consumption.
    """
    db = SessionLocal()
    try:
        bibles = db.query(CommunityBible).order_by(CommunityBible.performance_score.desc()).limit(20).all()
        total = len(bibles)
        average_score = (
            round(sum(float(getattr(cast(Any, item), "performance_score", 0.0) or 0.0) for item in bibles) / total, 2)
            if total
            else 0.0
        )
        return {
            "top_bibles": [
                {
                    "trader": getattr(cast(Any, item), "trader_name", ""),
                    "sharpe": float(getattr(cast(Any, item), "performance_score", 0.0) or 0.0),
                    "reflections": int(getattr(cast(Any, item), "reflection_count", 0) or 0),
                }
                for item in bibles
            ],
            "global_wisdom_score": average_score,
        }
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
