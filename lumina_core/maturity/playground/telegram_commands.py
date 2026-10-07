"""Playground operator verbs. The configured Telegram chat is the hands.

The runner never seals the envelope and never marks the deck live.
Numbers in a reply are copied from the exit law or from config.yaml.
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

import yaml

from lumina_core.maturity.continuum import load_continuum
from lumina_core.maturity.playground.envelope import write_operator_seal
from lumina_core.maturity.playground.journal import append_experiment_entry
from lumina_core.maturity.playground.law import evaluate_playground_exit
from lumina_core.maturity.playground.progress import load_playground_progress, merge_playground_progress
from lumina_core.maturity.playground.sense_brief import bar_book_operator_alert
from lumina_core.notifications.phase_status_report import format_phase_status

_VERBS = frozenset(
    {"STATUS", "STAND", "PAUSE", "RESUME", "STOP", "DECK", "CAP", "SEAL", "CONTINUE", "HOLD"}
)


def try_handle_playground_command(workspace_root: Path | str, text: str) -> dict[str, Any] | None:
    """Apply a verb and send the reply. None when the text is not ours."""
    result = apply_playground_command(workspace_root, text)
    if result is None:
        return None
    _send(workspace_root, str(result.get("reply") or ""))
    return result


def apply_playground_command(workspace_root: Path | str, text: str) -> dict[str, Any] | None:
    parsed = _parse(text)
    if parsed is None:
        return None
    root = Path(workspace_root)
    if str(load_continuum(root).get("active_phase") or "") != "playground":
        return None
    verb, arg = parsed
    if verb in {"STATUS", "STAND"}:
        reply = _status_reply(root)
    elif verb == "PAUSE":
        merge_playground_progress(root, {"paused": True})
        reply = "Playground gepauzeerd. Tape en cursor blijven. Stall telt niet.\n" + _board(root)
    elif verb == "RESUME":
        merge_playground_progress(root, {"paused": False})
        reply = "Playground hervat op dezelfde tape.\n" + _board(root)
    elif verb == "STOP":
        _request_stop(root)
        reply = (
            "Stop gevraagd. De klok eindigt incomplete. "
            "Birth en Awakening blijven. De tape blijft.\n" + _board(root)
        )
        _book(root, "telegram STOP", [reply.split("\n", 1)[0]])
    elif verb == "DECK":
        merge_playground_progress(root, {"deck_live": True, "deck_live_source": "telegram"})
        reply = "Deck live vastgelegd vanuit Telegram. De runner heeft dit niet gezet.\n" + _board(root)
    elif verb == "CAP":
        reply = _apply_cap(root, arg)
    elif verb == "SEAL":
        reply = _apply_seal(root, arg)
    elif verb == "CONTINUE":
        reply = _apply_continue(root)
    else:
        reply = _apply_hold(root)
    return {"ok": True, "command": verb, "reply": reply}


def ensure_seal_token(workspace_root: Path | str) -> str:
    root = Path(workspace_root)
    current = str(load_playground_progress(root).get("seal_token") or "")
    if len(current) >= 6:
        return current
    token = secrets.token_hex(3)
    merge_playground_progress(root, {"seal_token": token})
    return token


def read_sim_limits(workspace_root: Path | str) -> tuple[float | None, float | None]:
    raw = _load_config(Path(workspace_root))
    sim = raw.get("sim") if isinstance(raw.get("sim"), dict) else {}
    return _num(sim.get("daily_loss_cap")), _num(sim.get("max_total_open_risk"))


def set_sim_daily_loss_cap(workspace_root: Path | str, cap: float) -> str | None:
    """Replace only the sim.daily_loss_cap line. Returns an error string or None."""
    if float(cap) >= 0.0:
        return "daily_loss_cap moet een negatieve vloer zijn, bijvoorbeeld CAP -150."
    path = Path(workspace_root) / "config.yaml"
    if not path.is_file():
        return "config.yaml ontbreekt."
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    in_sim = False
    replaced = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if stripped and not stripped.startswith("#") and indent == 0 and stripped.endswith(":"):
            in_sim = stripped == "sim:"
        if in_sim and stripped.startswith("daily_loss_cap:"):
            pad = line[: len(line) - len(line.lstrip(" "))]
            newline = "\n" if line.endswith("\n") else ""
            rendered = format(float(cap), "g")
            out.append(f"{pad}daily_loss_cap: {rendered}{newline}")
            replaced = True
            continue
        out.append(line)
    if not replaced:
        return "sim.daily_loss_cap ontbreekt in config.yaml."
    path.write_text("".join(out), encoding="utf-8")
    return None


def _apply_cap(root: Path, arg: str) -> str:
    number = _num(arg)
    if number is None:
        return "CAP verwacht een getal. Voorbeeld: CAP -150."
    error = set_sim_daily_loss_cap(root, number)
    if error:
        return error
    _book(root, "telegram CAP", [f"sim.daily_loss_cap: {number}"])
    return f"sim.daily_loss_cap gezet op {number}. Nog niet verzegeld.\n" + _status_reply(root)


def _apply_seal(root: Path, arg: str) -> str:
    expected = str(load_playground_progress(root).get("seal_token") or "")
    given = str(arg or "").strip()
    if not expected or given.lower() != expected.lower():
        return "SEAL geweigerd. Geen geldige token. Vraag STATUS voor de uitdaging."
    cap, risk = read_sim_limits(root)
    if cap is None or cap >= 0.0:
        return "SEAL geweigerd. sim.daily_loss_cap is leeg of geen verliesvloer. Eerst CAP."
    if risk is None or risk <= 0.0:
        return "SEAL geweigerd. sim.max_total_open_risk ontbreekt."
    write_operator_seal(root, daily_loss_cap=cap, max_total_open_risk=risk, source="telegram")
    _book(
        root,
        "telegram SEAL",
        [f"daily_loss_cap: {cap}", f"max_total_open_risk: {risk}", "source: telegram"],
    )
    return (
        f"SIM-envelope verzegeld. daily_loss_cap {cap}, max_total_open_risk {risk}.\n" + _board(root)
    )


def _apply_continue(root: Path) -> str:
    prog = load_playground_progress(root)
    bracket = int(prog.get("conclusive_bracket") or 0)
    asked = prog.get("conclusive_asked_at")
    if bracket <= 0 or asked in (None, ""):
        return "CONTINUE genegeerd. Er staat geen conclusieve vraag open."
    merge_playground_progress(root, {"conclusive_continued_through": bracket})
    _book(root, "telegram CONTINUE", [f"continued_through: {bracket}", "pass_now blijft false"])
    return (
        f"Crawl loopt door voorbij n_P {bracket}. Dit is geen pass. De lat blijft.\n" + _board(root)
    )


def _apply_hold(root: Path) -> str:
    prog = load_playground_progress(root)
    fault = str(prog.get("stall_fault") or "")
    if not fault:
        return "HOLD genegeerd. Er is geen stall-venster actief."
    merge_playground_progress(root, {"stall_hold_fault": fault})
    return f"Dit venster ({fault}) telt niet mee. Het volgende wel.\n" + _board(root)


def _request_stop(root: Path) -> None:
    merge_playground_progress(root, {"operator_stop": True, "paused": False})
    try:
        from lumina_core.maturity.maturity_service import MaturityService

        service = MaturityService.instance()
        service.configure_workspace(root)
        service._stop_requested.set()
    except Exception:
        return


def _status_reply(root: Path) -> str:
    lines = [_board(root), _needed(root), bar_book_operator_alert(root)]
    return "\n".join(line for line in lines if line).strip()


def _needed(root: Path) -> str:
    _ok, missing, learned = evaluate_playground_exit(root)
    if not bool(learned.get("envelope_sealed")):
        cap, risk = read_sim_limits(root)
        token = ensure_seal_token(root)
        if cap is None or cap >= 0.0:
            return (
                "Dagvloer is -2% van de Sim-portefeuille en wordt gezet zodra de equity "
                f"binnen is. Geen handmatig getal. Token {token} blijft voor STATUS."
            )
        if risk is None or risk <= 0.0:
            return f"Nodig: sim.max_total_open_risk, daarna SEAL {token}."
        return f"Nodig: SEAL {token}. Limieten daily_loss_cap {cap}, max_total_open_risk {risk}."
    if not bool(learned.get("deck_live")):
        return "Nodig: DECK. Daarmee bevestig je dat jij de operator bent."
    if missing:
        return "Nog geen pass. STATUS toont wat ontbreekt."
    return ""


def _board(root: Path) -> str:
    ok, missing, learned = evaluate_playground_exit(root)
    _title, body, _kind = format_phase_status(
        "playground",
        kind="passed" if ok else "progress",
        learned=learned,
        missing=list(missing),
    )
    return body


def _book(root: Path, title: str, lines: list[str]) -> None:
    try:
        append_experiment_entry(root, title=title, lines=lines)
    except OSError:
        return


def _send(workspace_root: Path | str, reply: str) -> None:
    if not reply.strip():
        return
    try:
        from lumina_core.notifications.telegram_notifier import get_telegram_notifier

        notifier = get_telegram_notifier()
        notifier.configure_workspace(workspace_root)
        notifier.send_message(
            f"LUMINA STATUS — Playground\n\n{reply}",
            kind="phase_status",
            correlation_id="playground:command",
            expects_reply=True,
            source="playground_telegram_commands",
        )
    except Exception:
        return


def _parse(text: str) -> tuple[str, str] | None:
    parts = str(text or "").strip().split()
    if not parts:
        return None
    verb = parts[0].upper()
    if verb not in _VERBS:
        return None
    arg = parts[1] if len(parts) > 1 else ""
    return verb, arg


def _load_config(root: Path) -> dict[str, Any]:
    path = root / "config.yaml"
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
