"""Fabric connection diagnostics — live gRPC checks (Wave B2 PR-C1)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from lumina_launcher.services.fabric_diag_preflight import DiagnosticCheck

# NOTE: nested helpers may rebind ``client`` after prefer_nt_addon_host recovery.


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
    allow_live_order_probe: bool = False,
) -> None:
    """Append live gRPC + audit checks. Never submits NT orders.

    ``include_safe_mode`` / ``allow_live_order_probe`` are accepted for API
    compatibility and are always refused (constitution: no diagnostic place).
    """
    try:
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

    # 5 auth ok — heal token SSOT first, then SimHost realign if still failing
    t = time.perf_counter()
    client: FabricGrpcClient | None = None
    auth_detail = ""
    try:
        # Re-resolve via Fabric Secret Bus (single pipe).
        try:
            from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

            sec = fabric_secret_read(heal=True)
            healed_tok = str(sec.token or "").strip()
            if healed_tok:
                if healed_tok != token or sec.mismatch or sec.healed:
                    auth_detail = (
                        f"token_ssot source={sec.source} "
                        f"env_len={sec.env_len} json_len={sec.json_len} "
                        f"mismatch={sec.mismatch} healed={sec.healed} "
                        f"fp={sec.fingerprint}"
                    )
                token = healed_tok
        except Exception as ssot_exc:
            auth_detail = f"token_ssot_failed:{ssot_exc}"

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
                    align_msg = str(align.get("message") or align.get("status") or "")
                    auth_detail = (
                        f"{auth_detail}; simhost_align={align_msg}".strip("; ")
                        if auth_detail
                        else align_msg
                    )
                    try:
                        client.disconnect()
                    except Exception:
                        pass
                    client = make_client(token)
                    connected = bool(client.connect())
            except Exception as align_exc:
                auth_detail = (
                    f"{auth_detail}; realign_failed:{align_exc}".strip("; ")
                    if auth_detail
                    else f"realign_failed:{align_exc}"
                )

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

    # 7b historical bars — market data plane (critical; SimHost must fail closed)
    t = time.perf_counter()
    min_bars = 10
    try:
        assert client is not None

        def _do_hist() -> dict[str, Any]:
            # Wider window + more bars — NT BarsRequest is more reliable with barsBack/lookback.
            end_ms = int(time.time() * 1000)
            start_ms = end_ms - (14 * 24 * 60 * 60 * 1000)
            return client.request_historical_data(
                instrument=instrument,
                bar_period="1m",
                start_unix_ms=start_ms,
                end_unix_ms=end_ms,
                max_bars=max(min_bars, 200),
                timeout_seconds=90.0,
            )

        hist = _do_hist()
        hist_code = str(hist.get("code") or "").strip()
        # SimHost often stole :50051 — yield to NT AddOn once and reconnect.
        recover_detail = ""
        if hist_code in {"HOST_NO_NT_DATA", "NOT_IMPLEMENTED"}:
            try:
                from lumina_launcher.services.fabric_simhost import (
                    is_ninjatrader_running,
                    prefer_nt_addon_host,
                )

                if is_ninjatrader_running():
                    prefer = prefer_nt_addon_host(host=host, port=port, wait_sec=8.0)
                    recover_detail = str(prefer.get("message") or prefer.get("status") or "")
                    try:
                        client.disconnect()
                    except Exception:
                        pass
                    client = make_client(token)
                    if client.connect() and prefer.get("listening"):
                        hist = _do_hist()
                        hist_code = str(hist.get("code") or "").strip()
            except Exception as recover_exc:
                recover_detail = f"prefer_nt_failed:{recover_exc}"

        bars = hist.get("bars") if isinstance(hist.get("bars"), list) else []
        bar_count = len(bars)
        hist_ok = hist_code.lower() == "ok" and bar_count >= min_bars
        detail = json.dumps(
            {
                "code": hist_code,
                "message": hist.get("message"),
                "instrument": hist.get("instrument"),
                "bar_count": bar_count,
                "recover": recover_detail or None,
            },
            default=str,
        )[:500]
        if hist_ok:
            checks.append(
                DiagnosticCheck(
                    id="historical_bars",
                    title="Historical bars via Fabric (market data plane)",
                    status="pass",
                    message=f"{bar_count} bars for {hist.get('instrument') or instrument}",
                    detail=detail,
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    id="historical_bars",
                    title="Historical bars via Fabric (market data plane)",
                    status="fail",
                    message=(
                        f"code={hist_code} bars={bar_count} (need ≥{min_bars}). "
                        f"{hist.get('message') or ''}"
                    ).strip(),
                    detail=detail,
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
            if hist_code in {"HOST_NO_NT_DATA", "NOT_IMPLEMENTED"}:
                remediation.append(
                    "Market data plane missing: SimHost/stub cannot load real bars. "
                    "NinjaTrader must own 127.0.0.1:50051 (not SimHost). "
                    "1) Lumina → Repair NinjaTrader connection (auto-deploy + build Custom). "
                    "2) Check %APPDATA%\\LUMINA\\fabric-nt-host.log and New → LUMINA status. "
                    "3) Re-run diagnostic (auto-kills SimHost when NT is running)."
                )
            elif hist_code in {"NO_BARS", "INSTRUMENT_NOT_FOUND", "NT_BARS_ERROR", "HISTORICAL_TIMEOUT"}:
                remediation.append(
                    f"Fabric historical failed ({hist_code}): check NT instrument mapping "
                    f"for '{instrument}', data feed connection, and NinjaScript [FabricData] logs."
                )
            else:
                remediation.append(
                    f"RequestHistoricalData failed: code={hist_code} message={hist.get('message')}"
                )
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="historical_bars",
                title="Historical bars via Fabric (market data plane)",
                status="fail",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        remediation.append(
            "Historical bars check crashed — ensure FabricGrpcClient.request_historical_data "
            "and NT AddOn historical provider are deployed."
        )

    try:
        if client is not None:
            client.disconnect()
    except Exception:
        pass
    client = None

    # Constitution: diagnostics must never submit, flatten, or cancel NT orders.
    skip_msg = (
        "Skipped: diagnostic NT place/flatten is forbidden "
        f"(include_safe_mode={include_safe_mode}, allow_live_order_probe={allow_live_order_probe}). "
        "GREEN is auth + historical bars, not a live order."
    )
    checks.append(
        DiagnosticCheck(
            id="place_order",
            title="Place order (disabled)",
            status="skip",
            message=skip_msg,
        )
    )
    checks.append(
        DiagnosticCheck(
            id="flatten",
            title="Flatten (disabled)",
            status="skip",
            message=skip_msg,
        )
    )
    checks.append(
        DiagnosticCheck(
            id="safe_mode_enter",
            title="SAFE_MODE probe (disabled)",
            status="skip",
            message=skip_msg,
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
            ok_audit = has_auth
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
