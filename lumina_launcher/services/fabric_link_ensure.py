"""Ensure Fabric token SSOT + live authenticated session (always-on path)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def ensure_fabric_token_aligned_and_live(
    *,
    config_manager: Any | None = None,
    engine_config: Any | None = None,
    workspace_root: Path | str | None = None,
    mode_context: str = "sim",
    connect_timeout_seconds: float = 10.0,
    start_supervisor: bool = True,
) -> dict[str, Any]:
    """Align token targets and prove live Fabric auth.

    Steps:
    1. Resolve token (.env / process / engine / generate via config_manager)
    2. Dual-write process env + User env + fabric.json AuthToken
    3. Optional supervisor ensure-connected
    4. Live auth probe if still down

    Returns dict:
      ok, code, message, needs_nt_restart, token_len, live (supervisor status)
    """
    from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read
    from lumina_core.broker.ninjatrader.fabric_secret import write as fabric_secret_write

    token = ""
    if config_manager is not None:
        try:
            from lumina_launcher.services.fabric_bootstrap import ensure_fabric_token_in_env

            token = str(ensure_fabric_token_in_env(config_manager) or "").strip()
        except Exception as exc:
            logger.warning("fabric.ensure.token_from_manager_failed: %s", exc)
    if not token:
        token = str(fabric_secret_read(heal=True).token or "").strip()
    if not token and engine_config is not None:
        token = str(getattr(engine_config, "ninjatrader_nt8_api_key", "") or "").strip()
    if not token:
        return {
            "ok": False,
            "code": "TOKEN_EMPTY",
            "message": (
                "LUMINA_FABRIC_TOKEN ontbreekt. Genereer de token in Setup credentials, "
                "daarna Repair connection."
            ),
            "needs_nt_restart": False,
            "token_len": 0,
            "live": {},
        }

    side = fabric_secret_write(
        token, source="fabric_link_ensure", config_manager=config_manager
    )
    logger.info(
        "fabric.ensure.token_aligned process=%s user_env=%s fabric_json=%s",
        side.get("process_env"),
        side.get("user_env"),
        bool(side.get("fabric_json")),
    )

    live: dict[str, Any] = {}
    if start_supervisor and engine_config is not None:
        try:
            from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                ensure_fabric_link_supervisor,
            )

            sup = ensure_fabric_link_supervisor(engine_config, mode_context=mode_context)
            if sup.ensure_connected(timeout_seconds=float(connect_timeout_seconds)):
                live = sup.status().to_dict()
                return {
                    "ok": True,
                    "code": "OK",
                    "message": "Fabric link live (supervisor authenticated)",
                    "needs_nt_restart": False,
                    "token_len": len(token),
                    "live": live,
                }
            live = sup.status().to_dict()
        except Exception as exc:
            logger.warning("fabric.ensure.supervisor_failed: %s", exc, exc_info=True)

    # Probe one-shot for classification when supervisor cannot connect.
    try:
        from lumina_core.broker.ninjatrader.fabric_auth_probe import (
            probe_fabric_auth,
            remediation_for_probe,
        )

        probe = probe_fabric_auth(config=engine_config, mode_context=mode_context)
        if probe.ok:
            # Start supervisor after successful one-shot so link stays up.
            if start_supervisor and engine_config is not None:
                try:
                    from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                        ensure_fabric_link_supervisor,
                    )

                    ensure_fabric_link_supervisor(engine_config, mode_context=mode_context)
                except Exception:
                    pass
            return {
                "ok": True,
                "code": "OK",
                "message": probe.message or "Fabric authenticated",
                "needs_nt_restart": False,
                "token_len": len(token),
                "live": live,
                "probe": probe.to_dict(),
            }

        needs_restart = probe.code in {"AUTH_FAILED", "AUTH_TIMEOUT"}
        if needs_restart:
            # Re-push token targets (NT may still hold stale process env until restart).
            fabric_secret_write(
                token, source="fabric_link_ensure_reauth", config_manager=config_manager
            )
            try:
                from lumina_launcher.services.fabric_link_certificate import (
                    invalidate_certificate,
                )

                root = Path(workspace_root) if workspace_root else None
                invalidate_certificate(root, reason=f"ensure_{probe.code.lower()}")
            except Exception:
                pass

        return {
            "ok": False,
            "code": probe.code,
            "message": remediation_for_probe(probe) or probe.message,
            "needs_nt_restart": needs_restart,
            "token_len": len(token),
            "live": live,
            "probe": probe.to_dict(),
        }
    except Exception as exc:
        logger.warning("fabric.ensure.probe_failed: %s", exc, exc_info=True)
        return {
            "ok": False,
            "code": "ERROR",
            "message": f"Fabric ensure failed: {exc}",
            "needs_nt_restart": False,
            "token_len": len(token),
            "live": live,
        }
