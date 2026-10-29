"""Write the operator's demo and real account names.

Demo becomes the addon bind (fabric.json AccountName and config.yaml account_name).
Real is stored only as fabric.json RealAccountName. The addon ignores that key.
The token and the trade mode stay as they are.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lumina_core.broker.ninjatrader.account_names import (
    DEMO_HELP,
    REAL_HELP,
    NtAccountRejected,
    validate_account_pair,
)
from lumina_launcher.services.setup_persist_fabric import fabric_json_path

_ACCOUNT_LINE = re.compile(r"^(\s*)account_name:\s*\S.*$")
_WHITELIST_KEY = re.compile(r"^(\s*)sim_account_whitelist:\s*(.*)$")
_FABRIC_SECRET_KEYS = frozenset(
    {
        "LUMINA_LIVE_RELEASE_SECRET",
        "LiveReleaseSecret",
        "live_release_secret",
        "live_release_mac_secret",
    }
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_fabric(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return raw if isinstance(raw, dict) else {}


def _demo_from_text(text: str) -> str:
    try:
        import yaml

        raw = yaml.safe_load(text)
    except Exception:
        return ""
    if not isinstance(raw, dict):
        return ""
    broker = raw.get("broker")
    if not isinstance(broker, dict):
        return ""
    nt = broker.get("ninjatrader")
    if not isinstance(nt, dict):
        return ""
    return str(nt.get("account_name") or "").strip()


def _demo_from_config(workspace_root: Path) -> str:
    path = workspace_root / "config.yaml"
    if not path.is_file():
        return ""
    try:
        return _demo_from_text(_read_text(path))
    except OSError:
        return ""


def _mode_from_config(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("mode:"):
            return line.split(":", 1)[1].strip()
    return ""


def _upsert_sim_whitelist(text: str, demo: str) -> str:
    """Keep yaml whitelist equal to the demo bind name. Never adds the live name."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    key_idx = None
    key_indent = ""
    for index, line in enumerate(lines):
        matched = _WHITELIST_KEY.match(line)
        if matched:
            key_idx = index
            key_indent = matched.group(1)
            break
    item_line = f"{key_indent}  - {demo}"
    if key_idx is not None:
        drop_to = key_idx + 1
        while drop_to < len(lines):
            candidate = lines[drop_to]
            stripped = candidate.strip()
            if stripped.startswith("-") and candidate.startswith(key_indent):
                drop_to += 1
                continue
            break
        rebuilt = [*lines[:key_idx], f"{key_indent}sim_account_whitelist:", item_line, *lines[drop_to:]]
    else:
        account_idx = next((index for index, line in enumerate(lines) if _ACCOUNT_LINE.match(line)), None)
        if account_idx is None:
            raise NtAccountRejected(
                ["config.yaml heeft geen account_name onder broker.ninjatrader. De whitelist is niet geschreven."]
            )
        indent_match = re.match(r"^(\s*)", lines[account_idx])
        pad = indent_match.group(1) if indent_match else "    "
        rebuilt = [
            *lines[: account_idx + 1],
            f"{pad}sim_account_whitelist:",
            f"{pad}  - {demo}",
            *lines[account_idx + 1 :],
        ]
    body = newline.join(rebuilt)
    if text.endswith(("\n", "\r\n")):
        body += newline
    return body


def _replace_demo_line(text: str, demo: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    replaced = False
    lines: list[str] = []
    for line in text.splitlines():
        if not replaced and _ACCOUNT_LINE.match(line):
            indent = re.match(r"^(\s*)", line)
            pad = indent.group(1) if indent else ""
            lines.append(f"{pad}account_name: {demo}")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        raise NtAccountRejected(
            ["config.yaml heeft geen account_name onder broker.ninjatrader. De demo-naam is niet geschreven."]
        )
    body = newline.join(lines)
    if text.endswith(("\n", "\r\n")):
        body += newline
    return body


def read_nt_accounts(
    workspace_root: Path | str,
    *,
    fabric_path: Path | None = None,
) -> dict[str, Any]:
    """Names only. The fabric token is never included."""
    root = Path(workspace_root)
    path = fabric_path or fabric_json_path()
    fabric = _load_fabric(path)
    demo_config = _demo_from_config(root)
    demo_fabric = str(fabric.get("AccountName") or "").strip()
    real_name = str(fabric.get("RealAccountName") or "").strip()
    aligned = bool(demo_config) and demo_config.casefold() == demo_fabric.casefold()
    pair_complete = False
    pair_error = ""
    if aligned and real_name:
        try:
            validate_account_pair(demo_fabric or demo_config, real_name)
            pair_complete = True
        except NtAccountRejected as exc:
            pair_error = " ".join(exc.errors)
    elif demo_config and demo_fabric and not aligned:
        pair_error = (
            f"config.yaml noemt {demo_config}. fabric.json AccountName noemt {demo_fabric}. "
            "Sla de rekeningen opnieuw op zodat beide bestanden dezelfde demo-naam dragen."
        )
    return {
        "demo_account": demo_fabric or demo_config,
        "demo_config": demo_config,
        "demo_fabric": demo_fabric,
        "real_account": real_name,
        "names_aligned": aligned,
        "pair_complete": pair_complete,
        "pair_error": pair_error,
        "bind_account": "AccountName",
        "real_field": "RealAccountName",
        "real_bound": False,
        "restart_to_bind": True,
        "demo_help": DEMO_HELP,
        "real_help": REAL_HELP,
        "fabric_path": str(path),
    }


def first_seal_account_block(
    workspace_root: Path | str,
    *,
    setup_complete: bool,
    fabric_path: Path | None = None,
) -> str:
    """Block the first vault seal until both account names are stored.

    An already completed setup stays open. The later change screen is the writer.
    """
    if setup_complete:
        return ""
    snap = read_nt_accounts(workspace_root, fabric_path=fabric_path)
    if snap.get("pair_complete"):
        return ""
    err = str(snap.get("pair_error") or "").strip()
    if err:
        return err
    return (
        "Demo- en real-rekening zijn nog leeg. "
        "Open NT-rekeningen, kopieer beide namen uit Control Center → Accounts, en sla ze op. "
        + DEMO_HELP
        + " "
        + REAL_HELP
    )


def write_nt_accounts(
    workspace_root: Path | str,
    demo: str,
    real: str,
    *,
    fabric_path: Path | None = None,
) -> dict[str, Any]:
    """Persist a valid pair. Refuses to bind the real name or to change mode."""
    demo_name, real_name = validate_account_pair(demo, real)
    if real_name.casefold() == demo_name.casefold():
        raise NtAccountRejected(["Demo en real zijn dezelfde naam."])
    root = Path(workspace_root)
    config_path = root / "config.yaml"
    if not config_path.is_file():
        raise NtAccountRejected(["config.yaml ontbreekt. De rekeningen zijn niet geschreven."])
    fabric = fabric_path or fabric_json_path()
    if not fabric.is_file():
        raise NtAccountRejected(
            ["fabric.json ontbreekt. Rond eerst de Fabric-token af. De rekeningen zijn niet geschreven."]
        )
    original_config_bytes = config_path.read_bytes()
    original_fabric_bytes = fabric.read_bytes()
    original_config = original_config_bytes.decode("utf-8-sig")
    original_fabric = original_fabric_bytes.decode("utf-8-sig")
    mode_before = _mode_from_config(original_config)
    try:
        fabric_data = json.loads(original_fabric)
    except json.JSONDecodeError as exc:
        raise NtAccountRejected(["fabric.json is geen geldige JSON. De rekeningen zijn niet geschreven."]) from exc
    if not isinstance(fabric_data, dict):
        raise NtAccountRejected(["fabric.json is geen object. De rekeningen zijn niet geschreven."])
    token = fabric_data.get("AuthToken")
    updated_config = _replace_demo_line(original_config, demo_name)
    if _mode_from_config(updated_config) != mode_before:
        raise NtAccountRejected(["De modus in config.yaml zou wijzigen. De rekeningen zijn niet geschreven."])
    if "RealAccountName" in updated_config:
        raise NtAccountRejected(["De real-naam zou in config.yaml komen. Dat bestand wordt gecommit. Geweigerd."])
    if _demo_from_text(updated_config) != demo_name:
        raise NtAccountRejected(["config.yaml zou een andere account_name krijgen dan de demo. Geweigerd."])
    secret_hits = [key for key in _FABRIC_SECRET_KEYS if key in fabric_data]
    if secret_hits:
        raise NtAccountRejected(
            ["LIVE_RELEASE secret mag niet in fabric.json. Alleen de environment mag de HMAC-sleutel dragen."]
        )
    updated_config = _upsert_sim_whitelist(updated_config, demo_name)
    if _mode_from_config(updated_config) != mode_before:
        raise NtAccountRejected(["De modus in config.yaml zou wijzigen. De rekeningen zijn niet geschreven."])
    if _demo_from_text(updated_config) != demo_name:
        raise NtAccountRejected(["config.yaml zou een andere account_name krijgen dan de demo. Geweigerd."])
    fabric_data["AccountName"] = demo_name
    fabric_data["RealAccountName"] = real_name
    fabric_data["SimAccountWhitelist"] = [demo_name]
    fabric_data["LiveReleaseEnabled"] = False
    if str(fabric_data.get("AccountName") or "") != demo_name:
        raise NtAccountRejected(["AccountName wijkt af van de demo-naam."])
    if str(fabric_data.get("AccountName") or "").casefold() == real_name.casefold():
        raise NtAccountRejected(["De real-naam zou de bind-naam worden. Dat is geweigerd."])
    encoded = json.dumps(fabric_data, indent=2) + "\n"

    def _restore() -> None:
        config_path.write_bytes(original_config_bytes)
        fabric.write_bytes(original_fabric_bytes)

    try:
        config_path.write_bytes(updated_config.encode("utf-8"))
        fabric.write_bytes(encoded.encode("utf-8"))
        written = json.loads(fabric.read_text(encoding="utf-8-sig"))
        if written.get("AuthToken") != token:
            raise NtAccountRejected(["Het Fabric-token veranderde. De schrijf is teruggedraaid."])
        if written.get("AccountName") != demo_name or written.get("RealAccountName") != real_name:
            raise NtAccountRejected(["De rekeningnamen zijn niet blijven staan. De schrijf is teruggedraaid."])
        written_list = written.get("SimAccountWhitelist")
        if not isinstance(written_list, list) or [str(item) for item in written_list] != [demo_name]:
            raise NtAccountRejected(["De SIM-whitelist is niet blijven staan. De schrijf is teruggedraaid."])
        if written.get("LiveReleaseEnabled") is True:
            raise NtAccountRejected(["LIVE_RELEASE mag niet vanuit de launcher aan. Geweigerd."])
        if any(key in written for key in _FABRIC_SECRET_KEYS):
            raise NtAccountRejected(["LIVE_RELEASE secret mag niet in fabric.json."])
        if "AuthToken" in written and written.get("AccountName") == real_name:
            raise NtAccountRejected(["De real-naam zou de bind-naam worden. Dat is geweigerd."])
    except NtAccountRejected:
        _restore()
        raise
    except Exception as exc:
        _restore()
        raise NtAccountRejected([f"Schrijven mislukte: {exc}. De vorige namen zijn teruggezet."]) from exc
    result = read_nt_accounts(root, fabric_path=fabric)
    result["saved"] = True
    result["bind_note"] = (
        f"Demo {demo_name} staat in AccountName. "
        f"Real {real_name} staat in RealAccountName en wordt niet gebonden. "
        "Sluit NinjaTrader en start hem opnieuw om de demo-naam te laden. "
        "Er hoeft niets gecompileerd te worden."
    )
    return result
