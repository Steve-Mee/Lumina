"""Fabric Secret Bus — ONE legal read/write pipe for LUMINA_FABRIC_TOKEN.

Elon law (2026-08 forensics): dual-truth (process env ≠ fabric.json AuthToken)
caused NT host GREEN while Brain diagnostics AUTH_FAILED. Heal-on-read in every
module is duct tape. This module is the single pipe:

  write(token)  → fabric.json + process env + User env (+ optional .env)
  read()        → prefer fabric.json, heal env mirrors, return FabricSecret

All other code MUST call these APIs. Architecture tests ban raw getenv outside
this module (and C# FabricConfig.ResolveToken).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ENV_PRIMARY = "LUMINA_FABRIC_TOKEN"
ENV_LEGACY = "LUMINA_NT8_API_KEY"

# Metrics (process-local; observability can scrape later).
_divergence_total = 0
_heal_total = 0
_heal_failed_total = 0
_lock = threading.RLock()


def fabric_json_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric.json"
    return Path.home() / ".config" / "LUMINA" / "fabric.json"


def fingerprint(token: str) -> str:
    """Non-secret identity of a token (sha256 hex, first 16 chars). Empty → \"\"."""
    tok = str(token or "").strip()
    if not tok:
        return ""
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class FabricSecret:
    token: str
    fingerprint: str
    source: str
    surfaces_aligned: bool
    env_len: int
    json_len: int
    mismatch: bool
    healed: bool

    @property
    def ok(self) -> bool:
        return bool(self.token)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "fingerprint": self.fingerprint,
            "source": self.source,
            "surfaces_aligned": self.surfaces_aligned,
            "env_len": self.env_len,
            "json_len": self.json_len,
            "mismatch": self.mismatch,
            "healed": self.healed,
            # Never include raw token in logs/telemetry dumps.
            "token_len": len(self.token),
        }


def metrics_snapshot() -> dict[str, int]:
    return {
        "fabric_secret_divergence_total": int(_divergence_total),
        "fabric_secret_heal_total": int(_heal_total),
        "fabric_secret_heal_failed_total": int(_heal_failed_total),
    }


def _read_json_auth_token(path: Path | None = None) -> str:
    target = path or fabric_json_path()
    if not target.is_file():
        return ""
    try:
        data = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("AuthToken") or data.get("auth_token") or "").strip()


def _set_user_env(name: str, value: str) -> bool:
    """Best-effort User-scope env (Windows) so NT inherits after restart."""
    try:
        from lumina_launcher.services.setup_persist_fabric import (
            set_user_environment_variable,
        )

        return bool(set_user_environment_variable(name, value))
    except Exception:
        # Fallback: process only (already set by caller).
        try:
            os.environ[name] = value
            return True
        except Exception:
            return False


def write(
    token: str,
    *,
    source: str = "fabric_secret.write",
    config_manager: Any | None = None,
) -> dict[str, Any]:
    """Atomic multi-surface commit of the Fabric auth token.

    Surfaces: fabric.json AuthToken, process env, User env, optional .env.
    Fail-closed on empty/weak tokens (ADR-0041).
    """
    global _heal_failed_total
    tok = str(token or "").strip()
    result: dict[str, Any] = {
        "ok": False,
        "fingerprint": "",
        "fabric_json": None,
        "process_env": False,
        "user_env": False,
        "dotenv": False,
        "source": source,
        "error": None,
    }
    if not tok:
        result["error"] = "empty_token"
        return result
    try:
        from lumina_core.cyber_sentinel import assert_fabric_token_safe

        assert_fabric_token_safe(tok, mode_context="sim")
    except Exception as exc:
        result["error"] = f"token_unsafe:{exc}"
        with _lock:
            _heal_failed_total += 1
        return result

    fp = fingerprint(tok)
    result["fingerprint"] = fp

    # 1) process env first so concurrent readers see the new secret quickly
    os.environ[ENV_PRIMARY] = tok
    result["process_env"] = True

    # 2) fabric.json (host SSOT)
    try:
        from lumina_launcher.services.setup_persist_fabric import write_fabric_json_defaults

        path = write_fabric_json_defaults(auth_token=tok)
        # Persist non-secret fingerprint for operators / future host status.
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                data["TokenFingerprint"] = fp
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
        result["fabric_json"] = str(path)
    except Exception as exc:
        logger.exception("fabric_secret.write fabric.json failed")
        result["error"] = f"fabric_json:{exc}"
        with _lock:
            _heal_failed_total += 1
        return result

    # 3) User env
    result["user_env"] = _set_user_env(ENV_PRIMARY, tok)

    # 4) optional workspace .env
    if config_manager is not None:
        try:
            config_manager.write_env_file({ENV_PRIMARY: tok})
            result["dotenv"] = True
        except Exception as exc:
            logger.warning("fabric_secret.write dotenv failed: %s", exc)

    result["ok"] = bool(result["process_env"] and result["fabric_json"])
    logger.info(
        "fabric_secret.write ok=%s fp=%s source=%s process=%s user=%s json=%s",
        result["ok"],
        fp,
        source,
        result["process_env"],
        result["user_env"],
        bool(result["fabric_json"]),
    )
    return result


def read(
    *,
    heal: bool = True,
    prefer_host_json: bool = True,
) -> FabricSecret:
    """Single legal reader. Prefers fabric.json; heals process/User env when divergent."""
    global _divergence_total, _heal_total, _heal_failed_total

    env_tok = str(os.getenv(ENV_PRIMARY) or "").strip()
    legacy = str(os.getenv(ENV_LEGACY) or "").strip()
    json_tok = _read_json_auth_token()

    mismatch = bool(env_tok and json_tok and env_tok != json_tok)
    if mismatch:
        with _lock:
            _divergence_total += 1

    source = "empty"
    token = ""
    if prefer_host_json and json_tok and (not env_tok or env_tok != json_tok):
        token = json_tok
        source = "fabric_json" if not env_tok else "fabric_json_healed_env"
    elif env_tok:
        token = env_tok
        source = "process_env"
    elif json_tok:
        token = json_tok
        source = "fabric_json"
    elif legacy:
        token = legacy
        source = "legacy_env"

    healed = False
    if heal and token and os.getenv(ENV_PRIMARY, "").strip() != token:
        try:
            os.environ[ENV_PRIMARY] = token
            _set_user_env(ENV_PRIMARY, token)
            healed = True
            with _lock:
                _heal_total += 1
            logger.warning(
                "fabric_secret.read heal env→%s env_len=%s json_len=%s mismatch=%s",
                source,
                len(env_tok),
                len(json_tok),
                mismatch,
            )
        except Exception:
            with _lock:
                _heal_failed_total += 1
            logger.exception("fabric_secret.read heal failed")

    surfaces_aligned = bool(token) and (
        not json_tok or os.getenv(ENV_PRIMARY, "").strip() == token
    )
    return FabricSecret(
        token=token,
        fingerprint=fingerprint(token),
        source=source,
        surfaces_aligned=surfaces_aligned,
        env_len=len(env_tok),
        json_len=len(json_tok),
        mismatch=mismatch,
        healed=healed,
    )


def assert_surfaces_aligned() -> FabricSecret:
    """Fail-closed check for gates: token present and env matches json when both set."""
    sec = read(heal=True)
    if not sec.ok:
        raise RuntimeError("Fabric token empty (fabric_secret.read fail-closed)")
    if sec.mismatch and not sec.surfaces_aligned:
        raise RuntimeError(
            "Fabric token plane misaligned after heal "
            f"(env_len={sec.env_len} json_len={sec.json_len})"
        )
    return sec


def generate_token() -> str:
    """Cryptographically strong url-safe token."""
    return secrets.token_urlsafe(32)


# Back-compat aliases used during migration.
def resolve_fabric_token_ssot(
    *,
    heal_process_env: bool = True,
    prefer_host_json: bool = True,
) -> dict[str, Any]:
    """Legacy dict shape for call sites not yet on FabricSecret."""
    sec = read(heal=heal_process_env, prefer_host_json=prefer_host_json)
    return {
        "token": sec.token,
        "source": sec.source,
        "env_len": sec.env_len,
        "json_len": sec.json_len,
        "mismatch": sec.mismatch,
        "healed_process_env": sec.healed,
        "healed_user_env": sec.healed,
        "ok": sec.ok,
        "fingerprint": sec.fingerprint,
        "surfaces_aligned": sec.surfaces_aligned,
    }


__all__ = [
    "ENV_LEGACY",
    "ENV_PRIMARY",
    "FabricSecret",
    "assert_surfaces_aligned",
    "fabric_json_path",
    "fingerprint",
    "generate_token",
    "metrics_snapshot",
    "read",
    "resolve_fabric_token_ssot",
    "write",
]
