"""Ensure SIM Fabric gRPC host (SimHost) is listening *and* token-aligned.

Elon rules:
- Diagnostics must not fail because the operator forgot to start a host.
- Diagnostics must not fail because an old SimHost still holds the port with a
  stale token — restart SimHost with the Brain token and re-auth once.
- Never bind or kill non-localhost / foreign NT8 hosts blindly when not SimHost.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SIMHOST_PROC: subprocess.Popen[Any] | None = None
_SIMHOST_TOKEN: str | None = None

SIMHOST_RELATIVE_CANDIDATES = (
    Path(
        "integrations/ninjatrader8/Lumina.Execution.Fabric.SimHost/bin/Release/net48/"
        "Lumina.Execution.Fabric.SimHost.exe"
    ),
    Path(
        "integrations/ninjatrader8/Lumina.Execution.Fabric.SimHost/bin/Debug/net48/"
        "Lumina.Execution.Fabric.SimHost.exe"
    ),
    Path("tauri-app/src-tauri/resources/fabric/Lumina.Execution.Fabric.SimHost.exe"),
    Path("integrations/ninjatrader8/deploy/SimHost/Lumina.Execution.Fabric.SimHost.exe"),
)

SIMHOST_IMAGE_MARKERS = (
    "lumina.execution.fabric.simhost",
    "simhost",
)


def resolve_workspace_root(explicit: Path | str | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    env = str(os.getenv("LUMINA_WORKSPACE") or "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def resolve_simhost_exe(workspace_root: Path | str | None = None) -> Path | None:
    root = resolve_workspace_root(workspace_root)
    for rel in SIMHOST_RELATIVE_CANDIDATES:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    which = shutil_which("Lumina.Execution.Fabric.SimHost.exe")
    return Path(which) if which else None


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def tcp_open(host: str, port: int, timeout: float = 0.75) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_localhost(host: str) -> bool:
    h = str(host or "").strip().lower()
    return h in {"127.0.0.1", "localhost", "::1"}


def _simhost_still_running() -> bool:
    global _SIMHOST_PROC
    if _SIMHOST_PROC is None:
        return False
    code = _SIMHOST_PROC.poll()
    if code is not None:
        logger.warning("fabric.simhost.exited code=%s", code)
        _SIMHOST_PROC = None
        return False
    return True


def probe_fabric_auth(
    host: str,
    port: int,
    token: str,
    *,
    timeout_sec: float = 4.0,
) -> tuple[bool, str]:
    """Return (ok, detail). Uses Fabric gRPC AuthHello against the live host."""
    tok = str(token or "").strip()
    if not tok:
        return False, "empty_token"
    try:
        from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient
    except ImportError as exc:
        return False, f"client_unavailable:{exc}"

    client = FabricGrpcClient(
        FabricConfig(
            host=host,
            port=int(port),
            auth_token=tok,
            mode_context="sim",
            heartbeat_interval_ms=0,
            connect_timeout_seconds=timeout_sec,
            command_timeout_seconds=timeout_sec,
        )
    )
    try:
        ok = bool(client.connect())
        return ok, "authenticated" if ok else "auth_rejected"
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def _pids_on_port_windows(port: int) -> list[int]:
    """Best-effort PIDs with LISTENING socket on port (Windows)."""
    pids: set[int] = set()
    try:
        # -a -n -o: all, numeric, owning PID
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    needle = f":{int(port)}"
    for line in (completed.stdout or "").splitlines():
        if "LISTENING" not in line.upper():
            continue
        if needle not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        # Proto  Local  Foreign  State  PID
        local = parts[1] if len(parts) > 1 else ""
        if not local.endswith(needle) and needle not in local:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return sorted(pids)


def _windows_image_name(pid: int) -> str:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    line = (completed.stdout or "").strip().splitlines()
    if not line:
        return ""
    # "image.exe","pid","session","num","mem"
    raw = line[0].strip().strip('"')
    if raw.startswith('"'):
        # CSV quoted
        parts = line[0].split('","')
        return parts[0].strip('"') if parts else ""
    return raw.split(",")[0].strip().strip('"')


def _is_simhost_image(name: str) -> bool:
    n = str(name or "").strip().lower()
    return any(m in n for m in SIMHOST_IMAGE_MARKERS)


def find_simhost_pids_on_port(port: int) -> list[int]:
    if sys.platform != "win32":
        # Best-effort: only track our child on non-Windows.
        if _SIMHOST_PROC is not None and _simhost_still_running():
            return [_SIMHOST_PROC.pid]
        return []
    out: list[int] = []
    for pid in _pids_on_port_windows(port):
        if _is_simhost_image(_windows_image_name(pid)):
            out.append(pid)
    return out


def stop_simhost(*, port: int | None = None, force_port_simhosts: bool = True) -> dict[str, Any]:
    """Stop tracked SimHost and optionally any SimHost.exe listeners on port."""
    global _SIMHOST_PROC, _SIMHOST_TOKEN
    killed: list[int] = []

    if _SIMHOST_PROC is not None:
        pid = _SIMHOST_PROC.pid
        try:
            _SIMHOST_PROC.terminate()
            try:
                _SIMHOST_PROC.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _SIMHOST_PROC.kill()
            killed.append(pid)
        except OSError as exc:
            logger.warning("fabric.simhost.terminate_failed pid=%s err=%s", pid, exc)
        _SIMHOST_PROC = None

    if force_port_simhosts and port is not None and sys.platform == "win32":
        for pid in find_simhost_pids_on_port(int(port)):
            if pid in killed:
                continue
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                killed.append(pid)
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.warning("fabric.simhost.taskkill_failed pid=%s err=%s", pid, exc)

    _SIMHOST_TOKEN = None
    # Brief settle so OS releases the port.
    if killed:
        time.sleep(0.35)
    return {"ok": True, "killed": killed}


def start_simhost(
    *,
    host: str = "127.0.0.1",
    port: int = 50051,
    token: str = "",
    account: str = "Sim101",
    workspace_root: Path | str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Spawn SimHost detached. Returns status dict."""
    global _SIMHOST_PROC, _SIMHOST_TOKEN

    if not is_localhost(host):
        return {
            "ok": False,
            "status": "rejected",
            "message": f"Refuse to start SimHost on non-localhost host={host}",
        }

    if token:
        tok = str(token).strip()
    else:
        try:
            from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

            tok = str(fabric_secret_read(heal=True).token or "").strip()
        except Exception:
            tok = ""

    if tcp_open(host, port) and not force:
        return {
            "ok": True,
            "status": "already_listening",
            "message": f"{host}:{port} already accepts TCP",
            "exe": None,
            "pid": None,
            "token_set": bool(tok),
        }

    if force and tcp_open(host, port):
        stop_simhost(port=port, force_port_simhosts=True)

    if _simhost_still_running() and not force:
        return {
            "ok": True,
            "status": "starting",
            "message": "SimHost process already spawned; waiting for port",
            "exe": None,
            "pid": _SIMHOST_PROC.pid if _SIMHOST_PROC else None,
            "token_set": bool(tok),
        }

    if force and _simhost_still_running():
        stop_simhost(port=port, force_port_simhosts=True)

    exe = resolve_simhost_exe(workspace_root)
    if exe is None:
        return {
            "ok": False,
            "status": "missing_binary",
            "message": (
                "SimHost.exe not found. Build: "
                "dotnet build integrations/ninjatrader8/Lumina.Execution.Fabric.SimHost -c Release"
            ),
            "exe": None,
        }

    if not tok:
        return {
            "ok": False,
            "status": "missing_token",
            "message": "Cannot start SimHost without LUMINA_FABRIC_TOKEN",
            "exe": str(exe),
        }

    args = [
        str(exe),
        "--port",
        str(int(port)),
        "--account",
        str(account or "Sim101"),
        "--token",
        tok,
    ]

    env = os.environ.copy()
    env["LUMINA_FABRIC_TOKEN"] = tok

    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP

    try:
        _SIMHOST_PROC = subprocess.Popen(
            args,
            cwd=str(exe.parent),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags if sys.platform == "win32" else 0,
            start_new_session=(sys.platform != "win32"),
        )
        _SIMHOST_TOKEN = tok
    except OSError as exc:
        logger.exception("fabric.simhost.spawn_failed")
        return {
            "ok": False,
            "status": "spawn_failed",
            "message": f"Failed to start SimHost: {exc}",
            "exe": str(exe),
        }

    logger.info(
        "fabric.simhost.spawned pid=%s exe=%s port=%s token_len=%s",
        _SIMHOST_PROC.pid,
        exe,
        port,
        len(tok),
    )
    return {
        "ok": True,
        "status": "started",
        "message": f"SimHost started pid={_SIMHOST_PROC.pid}",
        "exe": str(exe),
        "pid": _SIMHOST_PROC.pid,
        "token_set": True,
    }


def ensure_simhost_listening(
    *,
    host: str = "127.0.0.1",
    port: int = 50051,
    token: str = "",
    account: str = "Sim101",
    workspace_root: Path | str | None = None,
    wait_sec: float = 8.0,
    poll_sec: float = 0.25,
    force: bool = False,
) -> dict[str, Any]:
    """If port closed (or force), start SimHost and wait until TCP accepts."""
    if not is_localhost(host):
        return {
            "ok": False,
            "status": "rejected",
            "message": f"Host {host} is not localhost — fail-closed",
            "listening": False,
        }

    if tcp_open(host, int(port)) and not force:
        return {
            "ok": True,
            "status": "already_listening",
            "message": f"{host}:{port} already up",
            "listening": True,
            "started": False,
        }

    spawn = start_simhost(
        host=host,
        port=int(port),
        token=token,
        account=account,
        workspace_root=workspace_root,
        force=force,
    )
    if not spawn.get("ok"):
        return {
            **spawn,
            "listening": False,
            "started": False,
        }

    deadline = time.monotonic() + max(0.5, float(wait_sec))
    while time.monotonic() < deadline:
        if tcp_open(host, int(port)):
            return {
                "ok": True,
                "status": "listening",
                "message": f"SimHost listening on {host}:{port}",
                "listening": True,
                "started": spawn.get("status") in {"started", "starting"},
                "pid": spawn.get("pid"),
                "exe": spawn.get("exe"),
            }
        if spawn.get("status") == "started" and not _simhost_still_running():
            return {
                "ok": False,
                "status": "exited_early",
                "message": "SimHost process exited before the port opened",
                "listening": False,
                "started": True,
                "pid": spawn.get("pid"),
                "exe": spawn.get("exe"),
            }
        time.sleep(max(0.05, float(poll_sec)))

    return {
        "ok": False,
        "status": "timeout",
        "message": (
            f"SimHost did not open {host}:{port} within {wait_sec:.1f}s. "
            "Check that no other process holds the port and token matches."
        ),
        "listening": False,
        "started": spawn.get("status") in {"started", "starting"},
        "pid": spawn.get("pid"),
        "exe": spawn.get("exe"),
    }


def is_ninjatrader_running() -> bool:
    """True if NinjaTrader.exe is running (Windows-friendly)."""
    try:
        import psutil  # type: ignore

        for proc in psutil.process_iter(["name"]):
            name = str(proc.info.get("name") or "").lower()
            if name in {"ninjatrader.exe", "ninjatrader"}:
                return True
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq NinjaTrader.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            out = (r.stdout or "").lower()
            return "ninjatrader.exe" in out
        except (OSError, subprocess.TimeoutExpired):
            return False
    return False


def prefer_nt_addon_host(
    *,
    host: str = "127.0.0.1",
    port: int = 50051,
    wait_sec: float = 6.0,
) -> dict[str, Any]:
    """When NinjaTrader is running: free :port from SimHost so NT AddOn can bind.

    Elon rule: SimHost is a crutch. NT AddOn owns execution + market data.
    Never kill NinjaTrader.exe — only SimHost image markers.
    """
    if not is_localhost(host):
        return {"ok": False, "status": "rejected", "message": "localhost only", "killed": []}

    nt_up = is_ninjatrader_running()
    if not nt_up:
        return {
            "ok": True,
            "status": "nt_not_running",
            "message": "NinjaTrader not running — SimHost may own the port",
            "nt_running": False,
            "killed": [],
        }

    sim_pids = find_simhost_pids_on_port(int(port))
    killed: list[int] = []
    if sim_pids or _simhost_still_running():
        stop = stop_simhost(port=int(port), force_port_simhosts=True)
        killed = list(stop.get("killed") or [])
        logger.info("fabric.prefer_nt killed_simhost pids=%s", killed)

    # Wait briefly for NT AddOn (with retry timer) to claim the port.
    deadline = time.time() + max(1.0, float(wait_sec))
    while time.time() < deadline:
        if tcp_open(host, int(port)):
            # If SimHost somehow respawned, kill again once.
            again = find_simhost_pids_on_port(int(port))
            if again:
                stop_simhost(port=int(port), force_port_simhosts=True)
                time.sleep(0.4)
                continue
            return {
                "ok": True,
                "status": "nt_port_ready",
                "message": f"Port {port} open after yielding SimHost to NT AddOn",
                "nt_running": True,
                "killed": killed,
                "listening": True,
            }
        time.sleep(0.35)

    return {
        "ok": False,
        "status": "nt_port_not_bound",
        "message": (
            f"NinjaTrader is running but nothing listens on {host}:{port} after stopping SimHost. "
            "Run Lumina Repair connection (auto-deploys + builds Custom AddOn), "
            "check %APPDATA%\\LUMINA\\fabric-nt-host.log, then re-run diagnostic."
        ),
        "nt_running": True,
        "killed": killed,
        "listening": False,
    }


def ensure_simhost_token_aligned(
    *,
    host: str = "127.0.0.1",
    port: int = 50051,
    token: str = "",
    account: str = "Sim101",
    workspace_root: Path | str | None = None,
    wait_sec: float = 8.0,
    allow_simhost_autostart: bool = True,
) -> dict[str, Any]:
    """Ensure a Fabric host is up *and* accepts the Brain token.

    Prefer NT AddOn when NinjaTrader is running (data plane). SimHost is only
    auto-started when NT is NOT running and ``allow_simhost_autostart`` is True.

    - If NT running → kill SimHost, wait for NT bind (do not start SimHost).
    - If port closed + NT down → start SimHost with token (execution-only).
    - If port open + auth OK → done.
    - If port open + auth fail + listener is SimHost → kill & restart with token.
    - If port open + auth fail + foreign host (e.g. NT8) → fail with remediation.
    """
    if token:
        tok = str(token).strip()
    else:
        try:
            from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

            tok = str(fabric_secret_read(heal=True).token or "").strip()
        except Exception:
            tok = ""
    if not tok:
        return {
            "ok": False,
            "status": "missing_token",
            "message": "No LUMINA_FABRIC_TOKEN to align",
            "listening": tcp_open(host, int(port)),
            "authenticated": False,
        }

    if not is_localhost(host):
        return {
            "ok": False,
            "status": "rejected",
            "message": f"Host {host} is not localhost — fail-closed",
            "listening": False,
            "authenticated": False,
        }

    # --- Prefer native NT path when NT is alive ---
    if is_ninjatrader_running():
        prefer = prefer_nt_addon_host(host=host, port=int(port), wait_sec=min(8.0, float(wait_sec)))
        if prefer.get("listening"):
            auth_ok, detail = probe_fabric_auth(host, int(port), tok)
            return {
                "ok": bool(auth_ok),
                "status": "nt_addon_aligned" if auth_ok else "nt_addon_auth_failed",
                "message": prefer.get("message"),
                "listening": True,
                "authenticated": auth_ok,
                "auth_detail": detail,
                "nt_running": True,
                "killed": prefer.get("killed") or [],
                "host_kind": "nt_addon_or_unknown",
            }
        # NT up but port still free — do NOT steal with SimHost (data plane required).
        return {
            "ok": False,
            "status": str(prefer.get("status") or "nt_port_not_bound"),
            "message": str(prefer.get("message") or "NT running but Fabric port not bound"),
            "listening": False,
            "authenticated": False,
            "nt_running": True,
            "killed": prefer.get("killed") or [],
            "host_kind": "none",
        }

    if not tcp_open(host, int(port)):
        if not allow_simhost_autostart:
            return {
                "ok": False,
                "status": "no_host",
                "message": "Port closed and SimHost auto-start disabled",
                "listening": False,
                "authenticated": False,
            }
        started = ensure_simhost_listening(
            host=host,
            port=int(port),
            token=tok,
            account=account,
            workspace_root=workspace_root,
            wait_sec=wait_sec,
        )
        if not started.get("listening"):
            return {**started, "authenticated": False, "host_kind": "simhost"}
        auth_ok, detail = probe_fabric_auth(host, int(port), tok)
        return {
            **started,
            "ok": bool(auth_ok),
            "status": "aligned" if auth_ok else "auth_failed_after_start",
            "authenticated": auth_ok,
            "auth_detail": detail,
            "host_kind": "simhost",
            "message": (
                f"SimHost started and authenticated ({detail})"
                if auth_ok
                else f"SimHost started but auth failed ({detail})"
            ),
        }

    # Port already open — verify token.
    auth_ok, detail = probe_fabric_auth(host, int(port), tok)
    if auth_ok:
        return {
            "ok": True,
            "status": "already_aligned",
            "message": f"{host}:{port} accepts configured token",
            "listening": True,
            "authenticated": True,
            "auth_detail": detail,
            "started": False,
            "restarted": False,
        }

    sim_pids = find_simhost_pids_on_port(int(port))
    managed = _simhost_still_running() or bool(sim_pids)
    if not managed:
        return {
            "ok": False,
            "status": "token_mismatch_foreign_host",
            "message": (
                f"Port {port} is open but rejects the Brain token and is not a managed SimHost. "
                "If this is the NT8 AddOn: set User env LUMINA_FABRIC_TOKEN to the same value as "
                "the Brain, then restart NinjaTrader."
            ),
            "listening": True,
            "authenticated": False,
            "auth_detail": detail,
            "restarted": False,
        }

    logger.info(
        "fabric.simhost.token_mismatch restarting sim_pids=%s detail=%s",
        sim_pids,
        detail,
    )
    stop_simhost(port=int(port), force_port_simhosts=True)
    restarted = ensure_simhost_listening(
        host=host,
        port=int(port),
        token=tok,
        account=account,
        workspace_root=workspace_root,
        wait_sec=wait_sec,
        force=True,
    )
    if not restarted.get("listening"):
        return {
            **restarted,
            "authenticated": False,
            "restarted": True,
            "auth_detail": detail,
        }

    auth2, detail2 = probe_fabric_auth(host, int(port), tok)
    return {
        "ok": bool(auth2),
        "status": "realigned" if auth2 else "auth_failed_after_restart",
        "message": (
            f"SimHost restarted with Brain token ({detail2})"
            if auth2
            else f"SimHost restarted but auth still fails ({detail2})"
        ),
        "listening": True,
        "authenticated": auth2,
        "auth_detail": detail2,
        "started": True,
        "restarted": True,
        "pid": restarted.get("pid"),
        "exe": restarted.get("exe"),
    }
