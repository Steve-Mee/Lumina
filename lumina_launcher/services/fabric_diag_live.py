"""Fabric connection diagnostics — live gRPC checks (Wave B2 PR-C1)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from lumina_launcher.services.fabric_diag_preflight import DiagnosticCheck


def run_live_checks(
    *,
    host: str,
    port: int,
    token: str,
    instrument: str,
    include_safe_mode: bool,
    checks: list[DiagnosticCheck],
    remediation: list[str],
    audit_path: Any,
) -> None:
    """Append live gRPC + SAFE_MODE + audit checks. Mutates checks/remediation in place."""
    try:
        from lumina_core.broker.broker_bridge.schemas import Order
        from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient
    except ImportError as exc:
        checks.append(
            DiagnosticCheck(
                id="auth_ok",
                title="Fabric auth (correct token)",
                status="fail",
                message=f"grpc / fabric client unavailable: {exc}",
            )
        )
        remediation.append("Install grpcio and generate fabric stubs (scripts/generate_fabric_proto.py).")
        return

    def make_client(auth: str, *, hb_ms: int = 500) -> FabricGrpcClient:
        return FabricGrpcClient(
            FabricConfig(
                host=host,
                port=port,
                auth_token=auth,
                mode_context="sim",
                heartbeat_interval_ms=hb_ms,
                connect_timeout_seconds=5.0,
                command_timeout_seconds=8.0,
            )
        )

    # 5 auth ok — one auto-realign retry for stale SimHost token (SIM only)
    t = time.perf_counter()
    client: FabricGrpcClient | None = None
    auth_detail = ""
    try:
        client = make_client(token)
        connected = bool(client.connect())
        if not connected:
            # Stale SimHost often holds :50051 with an old --token; realign once.
            try:
                from lumina_launcher.services.fabric_simhost import (
                    ensure_simhost_token_aligned,
                    is_localhost,
                )

                if is_localhost(host):
                    align = ensure_simhost_token_aligned(
                        host=host,
                        port=port,
                        token=token,
                        wait_sec=8.0,
                    )
                    auth_detail = str(align.get("message") or align.get("status") or "")
                    try:
                        client.disconnect()
                    except Exception:
                        pass
                    client = make_client(token)
                    connected = bool(client.connect())
            except Exception as align_exc:
                auth_detail = f"realign_failed:{align_exc}"

        if connected:
            checks.append(
                DiagnosticCheck(
                    id="auth_ok",
                    title="Fabric auth (correct token)",
                    status="pass",
                    message=f"Authenticated session={client.session_id} account={client.account_name}",
                    detail=auth_detail or None,
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    id="auth_ok",
                    title="Fabric auth (correct token)",
                    status="fail",
                    message="Auth failed with configured token",
                    detail=auth_detail or None,
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
            remediation.append(
                "Token mismatch: Brain LUMINA_FABRIC_TOKEN must match the Fabric host. "
                "SIM: diagnostics auto-restarts SimHost with the Brain token. "
                "NT8 AddOn: set the same token as User env and restart NinjaTrader."
            )
            try:
                client.disconnect()
            except Exception:
                pass
            return
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="auth_ok",
                title="Fabric auth (correct token)",
                status="fail",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        return

    # 6 auth reject (wrong token)
    t = time.perf_counter()
    bad = make_client("definitely-wrong-token-" + uuid.uuid4().hex[:8], hb_ms=0)
    try:
        bad_ok = bad.connect()
        if bad_ok:
            checks.append(
                DiagnosticCheck(
                    id="auth_reject",
                    title="Auth rejects wrong token",
                    status="fail",
                    message="Wrong token was accepted — security fail-closed broken",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
            remediation.append("Fabric host must reject invalid AuthToken.")
        else:
            checks.append(
                DiagnosticCheck(
                    id="auth_reject",
                    title="Auth rejects wrong token",
                    status="pass",
                    message="Invalid token correctly rejected",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
    finally:
        try:
            bad.disconnect()
        except Exception:
            pass

    # 7 account state
    t = time.perf_counter()
    try:
        assert client is not None
        account, _positions, code = client.get_account_state()
        if code == "ok" and account is not None:
            checks.append(
                DiagnosticCheck(
                    id="account_state",
                    title="Account state snapshot",
                    status="pass",
                    message=f"equity={getattr(account, 'equity', None)}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    id="account_state",
                    title="Account state snapshot",
                    status="warn",
                    message=f"GetAccountState code={code}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="account_state",
                title="Account state snapshot",
                status="warn",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )

    # 8 place
    t = time.perf_counter()
    try:
        assert client is not None
        cid = f"diag-place-{uuid.uuid4().hex[:8]}"
        place = client.place_order_sync(
            Order(symbol=instrument, side="BUY", quantity=1, order_type="MARKET"),
            client_order_id=cid,
            correlation_id=f"corr-{cid}",
        )
        place_ok = place.get("type") != "error"
        checks.append(
            DiagnosticCheck(
                id="place_order",
                title=f"Place SIM order ({instrument})",
                status="pass" if place_ok else "fail",
                message=str(place.get("message") or place.get("type") or place),
                detail=json.dumps(place, default=str)[:500],
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        if not place_ok:
            remediation.append(f"Place failed: {place}. Check SAFE_MODE and host logs.")
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="place_order",
                title=f"Place SIM order ({instrument})",
                status="fail",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )

    # 9 flatten
    t = time.perf_counter()
    try:
        assert client is not None
        flat = client.flatten_sync(instrument=instrument)
        flat_ok = flat.get("type") != "error"
        checks.append(
            DiagnosticCheck(
                id="flatten",
                title="Flatten position",
                status="pass" if flat_ok else "fail",
                message=str(flat.get("type") or flat),
                detail=json.dumps(flat, default=str)[:500],
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        if not flat_ok:
            remediation.append(f"Flatten failed: {flat}")
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="flatten",
                title="Flatten position",
                status="fail",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )

    try:
        assert client is not None
        client.disconnect()
    except Exception:
        pass
    client = None

    # 10–12 SAFE_MODE path
    if include_safe_mode:
        t = time.perf_counter()
        c2 = make_client(token, hb_ms=0)
        try:
            if not c2.connect():
                checks.append(
                    DiagnosticCheck(
                        id="safe_mode_enter",
                        title="SAFE_MODE blocks new orders",
                        status="skip",
                        message="Could not reconnect for SAFE_MODE probe",
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
            else:
                # Wait past default 5s heartbeat timeout
                time.sleep(6.2)
                rej = c2.place_order_sync(
                    Order(symbol=instrument, side="BUY", quantity=1, order_type="MARKET"),
                    client_order_id=f"diag-safe-{uuid.uuid4().hex[:6]}",
                )
                safe_hit = (
                    str(rej.get("code", "")).upper() == "SAFE_MODE"
                    or "SAFE" in str(rej).upper()
                )
                checks.append(
                    DiagnosticCheck(
                        id="safe_mode_enter",
                        title="SAFE_MODE blocks new orders",
                        status="pass" if safe_hit else "fail",
                        message=(
                            "Place rejected with SAFE_MODE after heartbeat timeout"
                            if safe_hit
                            else f"Expected SAFE_MODE reject, got {rej}"
                        ),
                        detail=json.dumps(rej, default=str)[:500],
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
                if not safe_hit:
                    remediation.append(
                        "Heartbeat watchdog did not enter SAFE_MODE — check Fabric host HeartbeatTimeoutMs."
                    )

                t2 = time.perf_counter()
                flat_safe = c2.flatten_sync(instrument=instrument)
                flat_safe_ok = flat_safe.get("type") != "error"
                checks.append(
                    DiagnosticCheck(
                        id="safe_mode_flatten_allowed",
                        title="Flatten allowed in SAFE_MODE",
                        status="pass" if flat_safe_ok else "fail",
                        message=str(flat_safe.get("type") or flat_safe),
                        duration_ms=int((time.perf_counter() - t2) * 1000),
                    )
                )
        finally:
            try:
                c2.disconnect()
            except Exception:
                pass

        # 12 reauth clears
        t = time.perf_counter()
        c3 = make_client(token, hb_ms=500)
        try:
            if c3.connect():
                time.sleep(0.6)
                place2 = c3.place_order_sync(
                    Order(symbol=instrument, side="BUY", quantity=1, order_type="MARKET"),
                    client_order_id=f"diag-reauth-{uuid.uuid4().hex[:6]}",
                )
                reauth_ok = place2.get("type") != "error"
                checks.append(
                    DiagnosticCheck(
                        id="reauth_clears_safe",
                        title="Re-auth recovers trading",
                        status="pass" if reauth_ok else "warn",
                        message=(
                            "Place accepted after re-auth"
                            if reauth_ok
                            else f"Still blocked after re-auth: {place2}"
                        ),
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
                try:
                    c3.flatten_sync(instrument=instrument)
                except Exception:
                    pass
            else:
                checks.append(
                    DiagnosticCheck(
                        id="reauth_clears_safe",
                        title="Re-auth recovers trading",
                        status="warn",
                        message="Reconnect after SAFE_MODE failed",
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
        finally:
            try:
                c3.disconnect()
            except Exception:
                pass
    else:
        checks.append(
            DiagnosticCheck(
                id="safe_mode_enter",
                title="SAFE_MODE blocks new orders",
                status="skip",
                message="Skipped (include_safe_mode=false)",
            )
        )

    # 13 audit trail
    t = time.perf_counter()
    audit = audit_path()
    if audit.is_file():
        try:
            lines = audit.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            joined = "\n".join(lines)
            has_auth = "auth_ok" in joined or "authenticated" in joined
            has_place = "place_order" in joined
            has_safe = "SafeMode" in joined or "HeartbeatTimeout" in joined or "safety_alert" in joined
            ok_audit = has_auth or has_place
            checks.append(
                DiagnosticCheck(
                    id="audit_trail",
                    title="Audit log evidence",
                    status="pass" if ok_audit else "warn",
                    message=f"{audit.name}: auth={has_auth} place={has_place} safety={has_safe}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
        except OSError as exc:
            checks.append(
                DiagnosticCheck(
                    id="audit_trail",
                    title="Audit log evidence",
                    status="warn",
                    message=f"Could not read audit: {exc}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
    else:
        checks.append(
            DiagnosticCheck(
                id="audit_trail",
                title="Audit log evidence",
                status="warn",
                message=f"No audit file at {audit}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
