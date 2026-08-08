#!/usr/bin/env python3
"""OR5: Champion freeze operator CLI — status / accept / wipe (sacred fork).

Usage:
  python scripts/validation/champion_freeze_ops.py --workspace . status
  python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm
  python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm --no-start
  python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm --keep-tick-cache
  python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm

Never arms REAL, never declares Perfect Birth, never trains through freeze
without an explicit accept/wipe choice. Status is always safe (read-only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_progress(workspace: Path) -> dict[str, Any]:
    for name in ("lumina_birth_progress.json", "first_boot_progress.json"):
        path = workspace / "state" / name
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                return raw if isinstance(raw, dict) else {}
            except Exception:
                return {}
    return {}


def _load_checkpoint_metrics(workspace: Path) -> dict[str, Any]:
    path = workspace / "state" / "lumina_birth_checkpoint.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        metrics = raw.get("stage_metrics")
        out = dict(metrics) if isinstance(metrics, dict) else {}
        if raw.get("phase"):
            out.setdefault("phase", raw.get("phase"))
        return out
    except Exception:
        return {}


def _print_card(card: dict[str, Any]) -> None:
    print(f"champion_freeze_ops decision={card.get('decision')}")
    print(
        f"  freeze_active={card.get('freeze_active')} "
        f"accepted={card.get('champion_accepted')} "
        f"rejected={card.get('rejected_no_lift')}"
    )
    print(
        f"  phase={card.get('phase') or '-'} "
        f"sub_phase={card.get('sub_phase') or '-'} "
        f"stage={card.get('stage') or '-'}"
    )
    print(
        f"  trades={card.get('cumulative_trades')} "
        f"budget_remaining={card.get('trade_budget_remaining')} "
        f"stage1_receipt={card.get('stage1_certified_receipt')}"
    )
    if card.get("stage_blocker_metric"):
        print(
            f"  blocker={card.get('stage_blocker_metric')}="
            f"{card.get('stage_blocker_value')} "
            f"wr={card.get('stage_winrate')} edgescore={card.get('edgescore')}"
        )
        if card.get("pass_reason"):
            print(f"  pass_reason: {card.get('pass_reason')}")
    rec = card.get("recovery") or {}
    print(
        f"  recovery.active={rec.get('active')} theater={rec.get('theater')} "
        f"productive={rec.get('productive')} next={rec.get('next_action')}"
    )
    reasons = rec.get("theater_reasons") or []
    if reasons:
        print(f"  theater_reasons: {', '.join(str(r) for r in reasons)}")
    print(f"  guidance: {card.get('guidance')}")
    cmds = card.get("commands") or {}
    print("  commands:")
    for key in (
        "status",
        "accept",
        "accept_no_start",
        "wipe_keep_cache",
        "wipe_full",
        "gate",
        "checklist",
    ):
        if cmds.get(key):
            print(f"    {key}: {cmds[key]}")
    forbidden = card.get("forbidden") or []
    if forbidden:
        print(f"  forbidden: {', '.join(forbidden)}")


def _birth_service(workspace: Path) -> Any:
    from lumina_launcher.services.birth_service import BirthService

    svc = BirthService()
    if hasattr(svc, "configure_workspace"):
        svc.configure_workspace(workspace)
    return svc


def cmd_status(workspace: Path, *, as_json: bool) -> int:
    from lumina_core.birth.champion_freeze_ops import build_champion_freeze_decision_card

    card = build_champion_freeze_decision_card(
        progress=_load_progress(workspace),
        checkpoint_metrics=_load_checkpoint_metrics(workspace),
        workspace=str(workspace),
    )
    # Mirror questions to Telegram when freeze open (idempotent pending).
    if card.get("freeze_active") and not card.get("champion_accepted"):
        try:
            from lumina_core.birth.champion_freeze_telegram import (
                maybe_poll_freeze_telegram,
                notify_champion_freeze_decision,
            )

            notify_champion_freeze_decision(
                workspace,
                progress=_load_progress(workspace),
                force=False,
            )
            maybe_poll_freeze_telegram(workspace)
        except Exception:
            pass
    if as_json:
        print(json.dumps(card, indent=2, ensure_ascii=True, default=str))
    else:
        _print_card(card)
        if card.get("freeze_active"):
            print(
                "  telegram: reply ACCEPT | ACCEPT_NO_START | WIPE | WIPE_FULL "
                "(same questions as app popup)"
            )
    # Exit 2 when human fork required (freeze open)
    if card.get("freeze_active") and not card.get("champion_accepted"):
        return 2
    return 0


def cmd_accept(
    workspace: Path,
    *,
    confirm: bool,
    no_start: bool,
    target_trades: int | None,
    as_json: bool,
    force: bool,
) -> int:
    from lumina_core.birth.champion_freeze_ops import build_champion_freeze_decision_card

    progress = _load_progress(workspace)
    metrics = _load_checkpoint_metrics(workspace)
    card = build_champion_freeze_decision_card(
        progress=progress,
        checkpoint_metrics=metrics,
        workspace=str(workspace),
    )
    if not confirm:
        print("REFUSED: accept requires --confirm (sacred fork).")
        if not as_json:
            _print_card(card)
        return 1
    if not card.get("freeze_active") and not force:
        print(
            "REFUSED: no champion freeze active. "
            "Use --force only if you intentionally re-stamp accept flags."
        )
        return 1

    svc = _birth_service(workspace)
    result = svc.accept_champion_birth(
        target_trades=target_trades,
        start=not no_start,
        source="cli",
    )
    # Recompute card after mutation
    after = build_champion_freeze_decision_card(
        progress=_load_progress(workspace),
        checkpoint_metrics=_load_checkpoint_metrics(workspace),
        workspace=str(workspace),
    )
    payload = {
        "schema": "champion_freeze_ops_result_v1",
        "action": "accept",
        "started": not no_start,
        "result": result,
        "card_after": after,
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"champion_freeze_ops accept ok "
            f"started={not no_start} status={result.get('status')}"
        )
        print(f"  message: {result.get('message') or result.get('status')}")
        _print_card(after)
        print(
            "  next: follow docs/birth-stage2-certified-reentry-checklist.md "
            "before claiming Stage 2 / Perfect Birth"
        )
    return 0


def cmd_wipe(
    workspace: Path,
    *,
    confirm: bool,
    keep_tick_cache: bool,
    as_json: bool,
    force: bool,
    join_timeout: float,
) -> int:
    from lumina_core.birth.champion_freeze_ops import build_champion_freeze_decision_card

    progress = _load_progress(workspace)
    metrics = _load_checkpoint_metrics(workspace)
    card = build_champion_freeze_decision_card(
        progress=progress,
        checkpoint_metrics=metrics,
        workspace=str(workspace),
    )
    if not confirm:
        print("REFUSED: wipe requires --confirm (destructive sacred fork).")
        if not as_json:
            _print_card(card)
        return 1
    if not card.get("freeze_active") and not force:
        print(
            "REFUSED: no champion freeze active. "
            "Wipe without freeze requires --force (explicit full Birth reset)."
        )
        return 1

    svc = _birth_service(workspace)
    result = svc.wipe_all_birth_data(
        join_timeout=join_timeout,
        preserve_tick_cache=keep_tick_cache,
        source="cli",
    )
    after = build_champion_freeze_decision_card(
        progress=_load_progress(workspace),
        checkpoint_metrics=_load_checkpoint_metrics(workspace),
        workspace=str(workspace),
    )
    payload = {
        "schema": "champion_freeze_ops_result_v1",
        "action": "wipe",
        "keep_tick_cache": keep_tick_cache,
        "result": result,
        "card_after": after,
    }
    status = str(result.get("status") or "")
    ok = status in {"wiped", "ok"} or status == "wiped"
    if status == "rejected":
        ok = False
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"champion_freeze_ops wipe status={status} "
            f"keep_tick_cache={keep_tick_cache}"
        )
        print(f"  message: {result.get('message')}")
        if result.get("removed_artifacts") is not None:
            print(f"  removed: {len(result.get('removed_artifacts') or [])}")
            print(f"  preserved: {len(result.get('preserved_artifacts') or [])}")
        _print_card(after)
        print(
            "  next: genesis/setup if required, then "
            "docs/birth-stage2-certified-reentry-checklist.md "
            "(full Birth re-entry after wipe)"
        )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Champion freeze operator CLI (OR5 accept/wipe sacred fork)"
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="",
        help="Workspace root (default: repo root)",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow accept/wipe when freeze is not active (explicit)",
    )
    parser.add_argument(
        "--target-trades",
        type=int,
        default=None,
        help="Optional trade budget for accept+start",
    )
    parser.add_argument(
        "--join-timeout",
        type=float,
        default=30.0,
        help="Stop timeout seconds before wipe (default 30)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Read-only decision card (exit 2 if freeze open)")

    p_accept = sub.add_parser(
        "accept",
        help="Accept frozen champion (requires --confirm)",
    )
    p_accept.add_argument(
        "--confirm",
        action="store_true",
        help="Required confirmation for accept mutation",
    )
    p_accept.add_argument(
        "--no-start",
        action="store_true",
        help="Clear freeze only; do not start Birth (checklist first)",
    )

    p_wipe = sub.add_parser(
        "wipe",
        help="Wipe birth training artifacts (requires --confirm)",
    )
    p_wipe.add_argument(
        "--confirm",
        action="store_true",
        help="Required confirmation for wipe mutation",
    )
    p_wipe.add_argument(
        "--keep-tick-cache",
        action="store_true",
        help="Preserve tick cache / data artifacts when wiping",
    )

    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve() if args.workspace else ROOT

    if args.command == "status":
        return cmd_status(workspace, as_json=args.json)
    if args.command == "accept":
        return cmd_accept(
            workspace,
            confirm=bool(args.confirm),
            no_start=bool(args.no_start),
            target_trades=args.target_trades,
            as_json=args.json,
            force=bool(args.force),
        )
    if args.command == "wipe":
        return cmd_wipe(
            workspace,
            confirm=bool(args.confirm),
            keep_tick_cache=bool(args.keep_tick_cache),
            as_json=args.json,
            force=bool(args.force),
            join_timeout=float(args.join_timeout),
        )
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
