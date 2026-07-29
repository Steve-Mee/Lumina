"""Emergency flatten / cancel-all order endpoints."""
from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app_auth import verify_admin_role
from lumina_core.broker.broker_bridge import Order, broker_factory
from lumina_core.engine.engine_config import EngineConfig

logger = logging.getLogger(__name__)
_EMERGENCY_LOCK = threading.Lock()
_SECURITY: dict[str, Any] | None = None

router = APIRouter()


def configure_emergency_security(security: dict[str, Any]) -> None:
    global _SECURITY
    _SECURITY = security


def _sec() -> dict[str, Any]:
    if _SECURITY is None:
        raise RuntimeError("configure_emergency_security not called")
    return _SECURITY


def _create_emergency_broker() -> Any:
    """Build a minimal broker instance for emergency actions."""
    try:
        cfg = EngineConfig()
        return broker_factory(config=cfg, engine=None, logger=logger)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Emergency broker setup failed: {exc}") from exc


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
                        metadata={"reason": "api_emergency_stop"},
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


@router.post("/orders/emergency-stop")
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
    _sec()["audit_log"].log_admin_action(
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


@router.post("/orders/flatten")
def flatten_orders_alias(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    result = _execute_emergency_flatten()
    _sec()["audit_log"].log_admin_action(
        username=admin_auth["metadata"].get("name", "unknown"),
        action="flatten_open_positions",
        resource="/orders/flatten",
        details={"flattened_count": int(result.get("flattened_count", 0) or 0)},
    )
    return result


@router.post("/orders/cancel-all")
def cancel_all_orders_alias(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    result = _execute_cancel_all_orders()
    _sec()["audit_log"].log_admin_action(
        username=admin_auth["metadata"].get("name", "unknown"),
        action="cancel_all_orders",
        resource="/orders/cancel-all",
        details={"cancelled_count": int(result.get("cancelled_count", 0) or 0)},
    )
    return result


@router.delete("/orders")
def delete_orders_alias(
    admin_auth: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    result = _execute_cancel_all_orders()
    _sec()["audit_log"].log_admin_action(
        username=admin_auth["metadata"].get("name", "unknown"),
        action="cancel_all_orders",
        resource="/orders",
        details={"cancelled_count": int(result.get("cancelled_count", 0) or 0)},
    )
    return result
