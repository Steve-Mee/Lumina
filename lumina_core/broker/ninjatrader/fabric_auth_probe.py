"""Live Fabric auth probe — classify connect failures (not paper GREEN)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.fabric.auth_probe")

FabricProbeCode = Literal[
    "OK",
    "CONNECTION_REFUSED",
    "AUTH_FAILED",
    "AUTH_TIMEOUT",
    "TOKEN_EMPTY",
    "ERROR",
]


@dataclass(slots=True)
class FabricProbeResult:
    ok: bool
    code: FabricProbeCode
    message: str
    target: str = ""
    session_id: str = ""
    account_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "target": self.target,
            "session_id": self.session_id,
            "account_name": self.account_name,
        }


def probe_fabric_auth(
    *,
    config: Any | None = None,
    mode_context: str = "sim",
    keep_connected: bool = False,
) -> FabricProbeResult:
    """Open a short-lived (or reusable) Fabric session and authenticate.

    Returns explicit codes so callers never map AUTH_FAILED → "start NT".
    When ``keep_connected`` is True and auth succeeds, leaves the client connected
    only if the caller takes ownership via supervisor — default disconnects.
    """
    try:
        from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient
    except ImportError as exc:
        return FabricProbeResult(
            ok=False,
            code="ERROR",
            message=f"Fabric client unavailable: {exc}",
        )

    fabric_cfg = (
        config
        if isinstance(config, FabricConfig)
        else FabricConfig.from_engine_config(config, mode_context=mode_context)
    )
    target = fabric_cfg.target
    token = fabric_cfg.resolve_token()
    if not token:
        return FabricProbeResult(
            ok=False,
            code="TOKEN_EMPTY",
            message=(
                "LUMINA_FABRIC_TOKEN is empty on the Brain side. "
                "Generate/set the token in Setup, then Repair connection."
            ),
            target=target,
        )

    client = FabricGrpcClient(fabric_cfg)
    try:
        ok = client.connect()
        if ok:
            return FabricProbeResult(
                ok=True,
                code="OK",
                message="Fabric authenticated",
                target=target,
                session_id=str(client.session_id or ""),
                account_name=str(client.account_name or ""),
            )

        code = str(getattr(client, "last_connect_code", "") or "").upper()
        err = str(getattr(client, "last_connect_error", "") or "")
        if code == "CONNECTION_REFUSED":
            provisional = FabricProbeResult(
                ok=False,
                code="CONNECTION_REFUSED",
                message=err or code,
                target=target,
            )
            provisional.message = remediation_for_probe(provisional) or provisional.message
            return provisional
        if code in {"AUTH_FAILED", "AUTH_TIMEOUT", "TOKEN_EMPTY"}:
            provisional = FabricProbeResult(
                ok=False,
                code=code,  # type: ignore[arg-type]
                message=err or code,
                target=target,
            )
            provisional.message = remediation_for_probe(provisional) or provisional.message
            return provisional

        # Fallback: port readiness second opinion
        detail = _classify_failed_connect(fabric_cfg)
        return FabricProbeResult(
            ok=False,
            code=detail[0],
            message=detail[1],
            target=target,
        )
    except Exception as exc:
        err = str(exc).lower()
        if any(x in err for x in ("connection refused", "10061", "unavailable", "failed to connect")):
            return FabricProbeResult(
                ok=False,
                code="CONNECTION_REFUSED",
                message=(
                    f"No Fabric host on {target}. Start NinjaTrader, open New → LUMINA "
                    "(host running)."
                ),
                target=target,
            )
        return FabricProbeResult(
            ok=False,
            code="ERROR",
            message=f"Fabric probe error: {exc}",
            target=target,
        )
    finally:
        if not keep_connected:
            try:
                client.disconnect()
            except Exception:
                pass


def _classify_failed_connect(fabric_cfg: Any) -> tuple[FabricProbeCode, str]:
    """Second opinion after connect() False — port open vs auth reject."""
    target = str(getattr(fabric_cfg, "target", "127.0.0.1:50051"))
    try:
        import grpc
        from lumina_core.broker.ninjatrader.generated import fabric_pb2, fabric_pb2_grpc

        try:
            from lumina_core.mtls_config import build_grpc_channel

            channel = build_grpc_channel(target)
        except Exception:
            channel = grpc.insecure_channel(target)
        try:
            grpc.channel_ready_future(channel).result(timeout=2.0)
        except Exception:
            try:
                channel.close()
            except Exception:
                pass
            return (
                "CONNECTION_REFUSED",
                (
                    f"Fabric port {target} not ready. Start NinjaTrader, open New → LUMINA "
                    "(host running on 127.0.0.1:50051)."
                ),
            )
        # Port is up — connect() failed likely auth/timeout.
        try:
            channel.close()
        except Exception:
            pass
        return (
            "AUTH_FAILED",
            (
                "Fabric host is running but Brain authentication failed (token mismatch). "
                "Align LUMINA_FABRIC_TOKEN (Setup → Repair connection), then restart "
                "NinjaTrader once so the AddOn reloads the token. "
                "Do not treat paper GREEN as live auth."
            ),
        )
    except Exception as exc:
        logger.debug("fabric probe classify failed: %s", exc, exc_info=True)
        return (
            "AUTH_FAILED",
            (
                "Fabric connect failed after host appeared reachable — likely auth token "
                "mismatch. Repair connection and restart NinjaTrader once."
            ),
        )


def remediation_for_probe(result: FabricProbeResult) -> str:
    """Operator-facing remediation (native Fabric only)."""
    if result.ok:
        return ""
    if result.code == "CONNECTION_REFUSED":
        return (
            "Geen verbinding met Execution Fabric (127.0.0.1:50051). "
            "Start NinjaTrader, wacht tot datafeed Connected is, open New → LUMINA (host running), "
            "controleer LUMINA_FABRIC_TOKEN, daarna Test connection (GREEN) en Retry birth."
        )
    if result.code in {"AUTH_FAILED", "AUTH_TIMEOUT"}:
        return (
            "Fabric host draait, maar Brain-auth faalt (token mismatch). "
            "In Lumina: Setup → Repair NinjaTrader connection (token sync). "
            "Herstart daarna NinjaTrader één keer zodat de AddOn de User-env / fabric.json token laadt. "
            "LUMINA Link moet Brain sessions ≥ 1 tonen (niet AMBER met 0 sessions)."
        )
    if result.code == "TOKEN_EMPTY":
        return (
            "LUMINA_FABRIC_TOKEN ontbreekt. Genereer/zet de token in Setup credentials, "
            "Repair connection, herstart NinjaTrader."
        )
    return result.message or "Fabric preflight mislukt."
