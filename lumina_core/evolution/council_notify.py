"""Council notify — Phase Hub file always; Telegram best-effort (K14)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.evolution.council import CouncilDossier


def pending_path(workspace: Path | str, kind: str) -> Path:
    name = "council_pending_sim.json" if kind == "sim" else "council_pending_real.json"
    return Path(workspace) / "state" / name


def write_hub(workspace: Path | str, kind: str, dossier: CouncilDossier) -> Path:
    """One pending SIM and one pending REAL (rate-limit)."""
    path = pending_path(workspace, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dossier.to_dict(), indent=2), encoding="utf-8")
    return path


def hub_visible(workspace: Path | str, kind: str) -> bool:
    return pending_path(workspace, kind).is_file()


def notify_council(
    workspace: Path | str,
    kind: str,
    dossier: CouncilDossier,
    *,
    telegram_ok: bool = True,
) -> dict[str, Any]:
    path = write_hub(workspace, kind, dossier)
    telegram_sent = False
    if telegram_ok:
        try:
            from lumina_core.notifications.telegram_notifier import TelegramNotifier

            question = str(dossier.question or "council")
            telegram_sent = bool(
                TelegramNotifier().send_message(
                    f"Lumina council ({kind}): {question}",
                    kind="operator",
                    source="council_notify",
                )
            )
        except Exception:
            telegram_sent = False
    return {
        "hub_path": str(path),
        "hub_visible": True,
        "telegram_sent": telegram_sent,
        "kind": kind,
    }
