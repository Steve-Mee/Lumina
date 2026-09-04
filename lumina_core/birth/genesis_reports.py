"""G7/G8 + AUDIT/VERDICT/flags writers for the genesis cloud ladder."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.genesis_autopsy import build_autopsy, render_autopsy_md
from lumina_core.birth.genesis_cloud_const import (
    FLAGS_NAME,
    G6_TAG,
    GENESIS_FIXTURE_SEED,
    HONESTY,
    OVERALL,
    SOURCE_GENESIS,
)
from lumina_core.birth.genesis_cloud_protocol import compose_genesis_flags

POINTER = (
    "\n---\n\n"
    "## Pointer — genesis first-life ladder\n\n"
    "Genesis run lives under `reports/genesis_cloud_run`. "
    "Old `reports/birth_cloud_run` artifacts were **not** used as inputs "
    "(no path_early JSONL, no 8cc435c6 / 53df2d78 / 7e86c2bb tape, no parent zip load).\n"
)


def write_flags(art: Path, payload: dict[str, Any]) -> dict[str, Any]:
    flags = compose_genesis_flags(payload)
    (art / FLAGS_NAME).write_text(json.dumps(flags, indent=2) + "\n", encoding="utf-8")
    return flags


def write_autopsy(art: Path, work: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    rows = build_autopsy(art=art, work=work, state=state)
    (art / "GENESIS_LADDER_AUTOPSY.md").write_text(render_autopsy_md(rows), encoding="utf-8")
    (art / "genesis_autopsy_rows.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows


def write_next_experiments(art: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        name = str(row.get("next_experiment") or "").strip()
        if not name or name in seen or row.get("status") not in {"Weak", "Broken"}:
            continue
        seen.add(name)
        items.append(
            {
                "title": name,
                "science_variable": str(row.get("cause") or row.get("rung")),
                "fail_closed_success_tag": _success_tag(name),
                "forbidden": (
                    "go REAL; T_LOCK; T_FP; DEAD; bounce; invented receipts; "
                    "reuse 7e86c2bb / 8cc435c6 / 53df2d78; lower FOUNDATION_HISTORY_START_DAYS; "
                    "REAL=yes on synthetic"
                ),
            }
        )
    lines = ["# GENESIS next experiments", "", "Ranked from this run's G7 gaps only. No item is go REAL.", ""]
    for i, item in enumerate(items, start=1):
        lines.extend(
            [
                f"## {i}. {item['title']}",
                f"- Science variable: {item['science_variable']}",
                f"- Fail-closed success tag: `{item['fail_closed_success_tag']}`",
                f"- Forbidden: {item['forbidden']}",
                "",
            ]
        )
    if not items:
        lines.append("No Weak/Broken rungs produced a next experiment. REAL door stays locked.")
        lines.append("")
    (art / "GENESIS_NEXT_EXPERIMENTS.md").write_text("\n".join(lines), encoding="utf-8")
    return items


def _success_tag(name: str) -> str:
    mapping = {
        "GENESIS_BIRTH_RESUME": "BIRTH_EXIT_OK",
        "GENESIS_FIXTURE_10S_RTH": "FIXTURE_10S_OK",
        "GENESIS_EYES_LEARN": "GENESIS_LEARN_OK",
        "GENESIS_EYES_HOLD_COMPARE": "GENESIS_EYES_OK",
        "GENESIS_NEWBORN_EVAL": "GENESIS_BIRTH_EVAL_OK",
        "GENESIS_RECEIPT_EXPORT": "RECEIPTS_ON_DISK",
    }
    return mapping.get(name, "SHADOW_MEASURE")


def write_experiment_log(
    reports: Path,
    art: Path,
    *,
    flags: dict[str, Any],
    rows: list[dict[str, str]],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    body = [
        "# LUMINA Genesis experiment log",
        "",
        "Append-only after first write. Isolated first-life ladder. SIM / synthetic only.",
        "",
        f"## {now} — genesis cloud ladder",
        "",
        f"- source=`{SOURCE_GENESIS}` fixture_seed=`{GENESIS_FIXTURE_SEED}` "
        f"train_hash=`{flags.get('fixture_train_hash')}` real_data_pct=`{flags.get('real_data_pct')}`",
        f"- birth_exited=`{flags.get('birth_exited')}` birth_status=`{flags.get('birth_status')}`",
        f"- G5_tag=`{flags.get('G5_tag')}` G6_tag=`{flags.get('G6_tag')}` REAL=`{flags.get('REAL')}`",
        f"- overall=`{OVERALL}` used_old_path_early=`false` used_old_parent_zip=`false`",
        "",
        "### Autopsy statuses",
        "",
    ]
    for row in rows:
        body.append(f"- {row['rung']}: {row['status']}")
    body.extend(["", "## Honesty", "", HONESTY, ""])
    text = "\n".join(body)
    (reports / "LUMINA_GENESIS_EXPERIMENT_LOG.md").write_text(text, encoding="utf-8")
    (art / "LUMINA_GENESIS_EXPERIMENT_LOG.md").write_text(text, encoding="utf-8")


def append_birth_log_pointer(repo: Path) -> None:
    path = repo / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if not path.is_file():
        return
    existing = path.read_text(encoding="utf-8")
    if "genesis first-life ladder" in existing:
        return
    path.write_text(existing.rstrip() + POINTER, encoding="utf-8")


def write_audit_verdict(
    reports: Path,
    *,
    g0: dict[str, Any],
    g1: dict[str, Any],
    g2: dict[str, Any],
    g3: dict[str, Any],
    g4: dict[str, Any],
    g5: dict[str, Any],
    g6: dict[str, Any],
    rows: list[dict[str, str]],
    flags: dict[str, Any],
) -> None:
    audit = _sectioned(
        title="GENESIS_CLOUD_AUDIT",
        g0=g0,
        g1=g1,
        g2=g2,
        g3=g3,
        g4=g4,
        g5=g5,
        g6=g6,
        rows=rows,
        flags=flags,
    )
    verdict = _sectioned(
        title="GENESIS_CLOUD_VERDICT",
        g0=g0,
        g1=g1,
        g2=g2,
        g3=g3,
        g4=g4,
        g5=g5,
        g6=g6,
        rows=rows,
        flags=flags,
        verdict=True,
    )
    (reports / "GENESIS_CLOUD_AUDIT.md").write_text(audit, encoding="utf-8")
    (reports / "GENESIS_CLOUD_VERDICT.md").write_text(verdict, encoding="utf-8")


def _sectioned(
    *,
    title: str,
    g0: dict[str, Any],
    g1: dict[str, Any],
    g2: dict[str, Any],
    g3: dict[str, Any],
    g4: dict[str, Any],
    g5: dict[str, Any],
    g6: dict[str, Any],
    rows: list[dict[str, str]],
    flags: dict[str, Any],
    verdict: bool = False,
) -> str:
    works = sum(1 for r in rows if r["status"] == "Works")
    weak = sum(1 for r in rows if r["status"] == "Weak")
    broken = sum(1 for r in rows if r["status"] == "Broken")
    forbidden = sum(1 for r in rows if r["status"] == "Forbidden-correct")
    lines = [
        f"# {title}",
        "",
        "## G0 Recon",
        "",
        f"```json\n{json.dumps(g0, indent=2, default=str)}\n```",
        "",
        "## G1 Fixture",
        "",
        f"```json\n{json.dumps(g1, indent=2, default=str)}\n```",
        "",
        "## G2 Birth",
        "",
        f"```json\n{json.dumps({k: v for k, v in g2.items() if k != 'engine_result'}, indent=2, default=str)}\n```",
        "",
        "## G3 Birth exit",
        "",
        f"```json\n{json.dumps(g3, indent=2, default=str)}\n```",
        "",
        "## G4 MARK_EYES train",
        "",
        f"```json\n{json.dumps(g4, indent=2, default=str)}\n```",
        "",
        "## G5 Eval",
        "",
        f"```json\n{json.dumps(g5, indent=2, default=str)}\n```",
        "",
        "## G6 REAL door",
        "",
        f"G6_tag=`{g6.get('G6_tag', G6_TAG)}` REAL=`no`",
        "",
        f"```json\n{json.dumps(g6, indent=2, default=str)}\n```",
        "",
        "## G7 Autopsy summary",
        "",
        f"Works={works} Weak={weak} Broken={broken} Forbidden-correct={forbidden}",
        "",
    ]
    for row in rows:
        lines.append(f"- {row['rung']}: **{row['status']}**")
    lines.extend(["", "## Honesty", "", HONESTY, ""])
    if verdict:
        lines.extend(
            [
                "## Verdict",
                "",
                f"overall=`{flags.get('overall')}` birth_exited=`{flags.get('birth_exited')}` "
                f"G5_tag=`{flags.get('G5_tag')}` G6_tag=`{G6_TAG}` REAL=`no` playground=`false` "
                f"evolution_proof_stamped=`false`. First life. Door locked.",
                "",
            ]
        )
    return "\n".join(lines)


__all__ = [
    "append_birth_log_pointer",
    "write_audit_verdict",
    "write_autopsy",
    "write_experiment_log",
    "write_flags",
    "write_next_experiments",
]
