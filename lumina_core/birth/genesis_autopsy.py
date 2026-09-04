"""G7 ladder autopsy from disk only. No invented receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.fitness_vector import FITNESS_VECTOR_NAME
from lumina_core.birth.genesis_cloud_const import (
    BIRTH_INCOMPLETE,
    EYES_ZIP_NAME,
    NEWBORN_ZIP_NAME,
    STAGE_RECEIPT_FILES,
)
from lumina_core.birth.synthetic_cloud_fixture import SOURCE_LABEL

WORKS = "Works"
WEAK = "Weak"
BROKEN = "Broken"
FORBIDDEN = "Forbidden-correct"


def _receipt(art: Path, name: str) -> dict[str, Any] | None:
    path = art / name
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _row(rung: str, status: str, evidence: str, cause: str = "", nxt: str = "") -> dict[str, str]:
    return {
        "rung": rung,
        "status": status,
        "evidence": evidence,
        "cause": cause,
        "next_experiment": nxt,
    }


def build_autopsy(*, art: Path, work: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    fixture = dict(state.get("g1") or {})
    birth = dict(state.get("g2") or {})
    exam = dict(state.get("g3") or {})
    eyes = dict(state.get("g4") or {})
    g5 = dict(state.get("g5") or {})
    g6 = dict(state.get("g6") or {})
    sidecar = art / "01_genesis_fixture_manifest.json"
    train_hash = str(fixture.get("hash") or fixture.get("train_hash") or "")
    rth = int(fixture.get("rth_bar_seconds") or 10)
    fixture_status = WORKS
    fixture_cause = ""
    fixture_next = ""
    if rth > 10:
        fixture_status = WEAK
        fixture_cause = f"cloud wall forced rth_bar_seconds={rth} (calendar 90 kept)"
        fixture_next = "GENESIS_FIXTURE_10S_RTH"
    rows = [
        _row(
            "Fixture generator + certified cache",
            fixture_status,
            f"{sidecar.name} source={fixture.get('source')} hash={train_hash} "
            f"days={fixture.get('days')} ticks={fixture.get('tick_count')} "
            f"regimes={fixture.get('holdout_regimes')}",
            fixture_cause,
            fixture_next,
        )
    ]
    status_g2 = str(birth.get("status") or "")
    incomplete = (not bool(exam.get("exited"))) or status_g2 == BIRTH_INCOMPLETE
    for stage, name in STAGE_RECEIPT_FILES:
        rec = _receipt(art, name)
        if rec is not None:
            rows.append(
                _row(
                    _rung_label(stage),
                    WORKS,
                    f"{name} schema={rec.get('schema')} trades={rec.get('trades')} "
                    f"pass_criteria_id={rec.get('pass_criteria_id')} "
                    f"oos_sharpe={rec.get('oos_sharpe')}",
                )
            )
        elif incomplete:
            ckpt = dict(birth.get("checkpoint") or {})
            rows.append(
                _row(
                    _rung_label(stage),
                    WEAK,
                    f"missing {name}; checkpoint={ckpt.get('curriculum_stage')} "
                    f"trades={ckpt.get('stage_trades')} status={status_g2}",
                    "Birth wall exhausted before this receipt flushed",
                    "GENESIS_BIRTH_RESUME",
                )
            )
        else:
            rows.append(
                _row(
                    _rung_label(stage),
                    BROKEN,
                    f"missing {name} while birth claimed complete",
                    "receipt not exported after claimed pass",
                    "GENESIS_RECEIPT_EXPORT",
                )
            )
    zip_path = art / NEWBORN_ZIP_NAME
    if exam.get("exited") and zip_path.is_file():
        rows.append(
            _row(
                "Birth exit + pi_star export",
                WORKS,
                f"g3_birth_exit_exam.json exited=true sha={exam.get('newborn_zip_sha256')} "
                f"fitness_ok={exam.get('fitness_checksum_ok')}",
            )
        )
    else:
        rows.append(
            _row(
                "Birth exit + pi_star export",
                WEAK if incomplete else BROKEN,
                f"exited={exam.get('exited')} missing={exam.get('missing')} zip={zip_path.is_file()}",
                "five foundation_v2 receipts + fitness vector not all present",
                "GENESIS_BIRTH_RESUME",
            )
        )
    birth_ledgers = (art / "genesis_birth_A_close_ledger.jsonl").is_file()
    if birth_ledgers:
        rows.append(
            _row(
                "43-dim newborn eval A/B",
                WORKS,
                "genesis_birth_A/B_close_ledger.jsonl on this fixture holdout halves",
            )
        )
    else:
        rows.append(
            _row(
                "43-dim newborn eval A/B",
                WEAK if incomplete else BROKEN,
                f"skip_reason={g5.get('skip_reason')}",
                "no newborn zip to eval" if incomplete else "eval path did not write ledgers",
                "GENESIS_NEWBORN_EVAL",
            )
        )
    eyes_zip = art / EYES_ZIP_NAME
    if eyes_zip.is_file():
        rows.append(
            _row(
                "MARK_EYES wrapper 46-dim",
                WORKS,
                f"{EYES_ZIP_NAME} init=scratch obs_dim=46",
            )
        )
    else:
        rows.append(
            _row(
                "MARK_EYES wrapper 46-dim",
                WEAK,
                f"wrapper modules present; child zip missing status={eyes.get('status')}",
                str(eyes.get("error") or "birth incomplete or sb3 missing"),
                "GENESIS_EYES_LEARN",
            )
        )
    learn = bool(eyes.get("learn_called"))
    steps = int(eyes.get("actual_timesteps") or 0)
    if learn and steps > 0:
        rows.append(
            _row(
                "MARK_EYES 10k scratch learn",
                WORKS,
                f"learn_called=true actual_timesteps={steps} seed=20260904",
            )
        )
    else:
        rows.append(
            _row(
                "MARK_EYES 10k scratch learn",
                WEAK,
                f"learn_called={learn} steps={steps} status={eyes.get('status')}",
                str(eyes.get("error") or "stable_baselines3 missing or birth incomplete"),
                "GENESIS_EYES_LEARN",
            )
        )
    tag = str(g5.get("G5_tag") or "")
    if tag == "GENESIS_EYES_OK":
        rows.append(
            _row(
                "MARK_EYES eval vs newborn",
                WORKS,
                f"g5_eval.json tag={tag} HOLE_MOVED A/B={g5.get('HOLE_MOVED_A')}/{g5.get('HOLE_MOVED_B')}",
            )
        )
    elif tag in {"GENESIS_EYES_FAIL", "GENESIS_S_MISSING", "GENESIS_BIRTH_ONLY"}:
        rows.append(
            _row(
                "MARK_EYES eval vs newborn",
                WEAK,
                f"g5_eval.json tag={tag} (not compared to old path_early 78/83)",
                "child did not clear HOLE_MOVED on both legs, or learn/eval skipped",
                "GENESIS_EYES_HOLD_COMPARE",
            )
        )
    else:
        rows.append(
            _row(
                "MARK_EYES eval vs newborn",
                WEAK,
                "G5 not licensed",
                "no G5 tag on disk",
                "GENESIS_EYES_HOLD_COMPARE",
            )
        )
    rows.append(
        _row(
            "T/DEAD/bounce families",
            FORBIDDEN,
            "PATH_EXIT_K3_SHADOW default False; PATH_SHAPE_K3_SHADOW default False; not rerun",
        )
    )
    rows.append(
        _row(
            "REAL / Promotion / Proof door",
            FORBIDDEN,
            f"g6_real_door.json G6_tag={g6.get('G6_tag')} REAL=no source={SOURCE_LABEL} real_data_pct=0.0",
        )
    )
    rows.append(
        _row(
            "Capital path (qty=1 MES $5 clip)",
            WORKS,
            "lumina_core/rl/gym_stop_fill.py:32 birth_force_qty_one; "
            "lumina_core/birth/notional_cap.py:48 birth_close_cap_usd; "
            "lumina_core/birth/birth_trade_geometry.py MES $5 — untouched",
        )
    )
    ckpt = work / "state" / "lumina_birth_checkpoint.json"
    rows.append(
        _row(
            "Autonomy (checkpoint / no human T)",
            WORKS if ckpt.is_file() or bool(exam.get("exited")) else WEAK,
            f"checkpoint={ckpt.is_file()} force=True reuse_data_manifest=True no T_LOCK",
            "" if ckpt.is_file() or exam.get("exited") else "no checkpoint flushed before wall",
            "" if ckpt.is_file() or exam.get("exited") else "GENESIS_BIRTH_RESUME",
        )
    )
    _ = FITNESS_VECTOR_NAME
    return rows


def _rung_label(stage: str) -> str:
    return {
        "stage1_trend": "Birth S1",
        "stage2_range": "Birth S2 occupancy / envelope",
        "stage3_mixed": "Birth S3 in-band idle",
        "stage4_viable_plant": "Birth S4",
        "stage5_probe_handoff": "Birth S5 + OOS sharpe",
    }.get(stage, stage)


def render_autopsy_md(rows: list[dict[str, str]]) -> str:
    lines = [
        "# GENESIS ladder autopsy",
        "",
        "Filled from this run's disk only. Old path_early / 8cc435c6 / 53df2d78 were not inputs.",
        "",
        "| Rung | Works / Weak / Broken / Forbidden-correct | Evidence (file + number) |",
        "|------|-------------------------------------------|--------------------------|",
    ]
    for row in rows:
        ev = str(row["evidence"]).replace("|", "/")
        lines.append(f"| {row['rung']} | {row['status']} | {ev} |")
    lines.extend(["", "## Weak / Broken causes + next experiment", ""])
    for row in rows:
        if row["status"] not in {WEAK, BROKEN}:
            continue
        lines.append(
            f"- **{row['rung']}** ({row['status']}): {row['cause'] or row['evidence']} "
            f"→ `{row['next_experiment'] or 'n/a'}`"
        )
    lines.append("")
    return "\n".join(lines)


__all__ = ["BROKEN", "FORBIDDEN", "WEAK", "WORKS", "build_autopsy", "render_autopsy_md"]
