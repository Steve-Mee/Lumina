"""Fabric JSON defaults + token environment side-effects."""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

# One writer. Concurrent User-env updates must not pile up on startup.
_USER_ENV_LOCK = threading.Lock()

DEFAULT_FABRIC_JSON: dict[str, Any] = {
    "BindHost": "127.0.0.1",
    "BindPort": 50051,
    "AuthTokenEnv": "LUMINA_FABRIC_TOKEN",
    "AccountName": "Sim101",
    "GatewayMode": "nt",
    "HeartbeatTimeoutMs": 5000,
    "FlattenGraceMs": 15000,
    "FlattenOnTimeout": True,
    "BindLocalhostOnly": True,
    "MaxPositionSize": 2,
    "MaxOrdersPerMinute": 30,
    "DailyLossLimit": 0,
}



def fabric_json_path() -> Path:
    """Return %APPDATA%/LUMINA/fabric.json (Windows) or ~/.config/LUMINA/fabric.json."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric.json"
    return Path.home() / ".config" / "LUMINA" / "fabric.json"


def write_fabric_json_defaults(
    *,
    path: Path | None = None,
    auth_token: str | None = None,
    account_name: str | None = None,
) -> Path:
    """Write operator fabric.json defaults. Creates parent dirs.

    When ``auth_token`` is provided, dual-writes plaintext AuthToken so the NT
    AddOn can load the same secret as Brain without waiting only on User env
    inheritance (still requires NT/AddOn restart to re-read the file).

    Patch-compatible: looks up fabric_json_path via façade module to respect test monkeypatches.
    """
    if path is None:
        # Late-bind via façade so tests can monkeypatch lumina_launcher.services.setup_persist.fabric_json_path
        import lumina_launcher.services.setup_persist as facade
        path = facade.fabric_json_path()
    target = path
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(DEFAULT_FABRIC_JSON)
    existing_token = ""
    # Preserve operator GatewayMode / ports if file already exists.
    if target.is_file():
        try:
            existing = json.loads(target.read_text(encoding="utf-8-sig"))
            if isinstance(existing, dict):
                for key in (
                    "GatewayMode",
                    "BindHost",
                    "BindPort",
                    "AccountName",
                    "RealAccountName",
                    "AuthTokenEnv",
                ):
                    if key in existing and existing[key] is not None:
                        payload[key] = existing[key]
                existing_token = str(existing.get("AuthToken") or "").strip()
                # Legacy product default "sim" meant Sim101 account intent, not memory gateway.
                # Migrate to explicit "nt" so status/ops match NtAccountOrderGateway.
                gw = str(payload.get("GatewayMode") or "").strip().lower()
                if gw in {"sim", "sim101", ""}:
                    payload["GatewayMode"] = "nt"
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not merge existing fabric.json; rewriting defaults", exc_info=True)
    # Caller passes the operator account from config.yaml. That name wins over
    # the product default Sim101. A token heal that omits it keeps the file's name.
    chosen_account = str(account_name or "").strip()
    if chosen_account:
        payload["AccountName"] = chosen_account
    token = str(auth_token or "").strip() or existing_token
    if token:
        # Local APPDATA only — required so NT AddOn ResolveToken matches Brain.
        payload["AuthToken"] = token
    else:
        payload.pop("AuthToken", None)
    # Write UTF-8 without BOM so C# and Python parsers agree.
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def _broadcast_environment_change() -> None:
    """Tell other processes the user environment changed.

    Runs off the caller thread. ``Environment.SetEnvironmentVariable`` does this
    broadcast on the caller and waits on every top-level window. A window that
    is not pumping messages holds that call, and a 15s PowerShell timeout then
    leaves the child alive. Fabric bootstrap runs on the uvicorn loop, so the
    whole API stops answering and cold start looks like a dead Fabric link.
    """

    def _run() -> None:
        try:
            import ctypes

            hwnd_broadcast = 0xFFFF
            wm_settingchange = 0x001A
            smto_abortifhung = 0x0002
            result = ctypes.c_size_t()
            ctypes.windll.user32.SendMessageTimeoutW(
                hwnd_broadcast,
                wm_settingchange,
                0,
                "Environment",
                smto_abortifhung,
                1000,
                ctypes.byref(result),
            )
        except Exception:
            logger.debug("User env broadcast skipped", exc_info=True)

    threading.Thread(target=_run, name="lumina-env-broadcast", daemon=True).start()


def _write_windows_user_env(name: str, value: str) -> bool:
    """Persist HKCU\\Environment. Skip when the value is already stored."""
    import winreg

    with _USER_ENV_LOCK:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE,
        ) as key:
            try:
                current, _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                current = None
            if str(current or "") == value:
                return True
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    _broadcast_environment_change()
    return True


def set_user_environment_variable(name: str, value: str) -> bool:
    """Best-effort set User-level env var so NT8 can read it after process restart.

    Process env is updated immediately. On Windows the durable copy is
    ``HKCU\\Environment`` via the registry API. A matching value is not rewritten.
    Returns True when the process env is set and the registry write succeeded
    or was already current.
    """
    name = str(name or "").strip()
    value = str(value or "").strip()
    if not name or not value:
        return False
    # Current process (so Brain/backend in this session can use it immediately).
    os.environ[name] = value
    if sys.platform != "win32":
        return True
    try:
        return _write_windows_user_env(name, value)
    except Exception:
        logger.warning("User env set failed for %s", name, exc_info=True)
        return False


def apply_fabric_token_side_effects(token: str) -> dict[str, Any]:
    """Write fabric.json + process/User env via Fabric Secret Bus (single writer)."""
    from lumina_core.broker.ninjatrader.fabric_secret import write as fabric_secret_write

    out = fabric_secret_write(token, source="apply_fabric_token_side_effects")
    return {
        "fabric_json": out.get("fabric_json"),
        "user_env": bool(out.get("user_env")),
        "process_env": bool(out.get("process_env")),
        "ok": bool(out.get("ok")),
        "fingerprint": out.get("fingerprint"),
        "error": out.get("error"),
    }


def read_fabric_json_auth_token(path: Path | None = None) -> str:
    """Read AuthToken from fabric.json (host SSOT for NT AddOn). Empty if missing."""
    from lumina_core.broker.ninjatrader.fabric_secret import _read_json_auth_token

    return _read_json_auth_token(path)


def resolve_fabric_token_ssot(
    *,
    heal_process_env: bool = True,
    prefer_host_json: bool = True,
) -> dict[str, Any]:
    """Resolve token via Fabric Secret Bus (single reader)."""
    from lumina_core.broker.ninjatrader.fabric_secret import resolve_fabric_token_ssot as _ssot

    return _ssot(
        heal_process_env=heal_process_env,
        prefer_host_json=prefer_host_json,
    )


def generate_fabric_token() -> str:
    """Cryptographically strong url-safe token for LUMINA_FABRIC_TOKEN."""
    from lumina_core.broker.ninjatrader.fabric_secret import generate_token

    return generate_token()


