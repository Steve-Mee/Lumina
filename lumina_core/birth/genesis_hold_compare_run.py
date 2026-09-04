"""CLI: measure frozen genesis A/B books. No learn. Does not overwrite G5 ledgers."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import GENESIS_ART, GENESIS_ROOT, REPO_ROOT
from lumina_core.birth.genesis_hold_compare import (
    G5_BIRTH_A,
    G5_BIRTH_B,
    G5_EYES_A,
    G5_EYES_B,
    G5_FLAGS,
    HOLDOUT_TICKS_A,
    HOLDOUT_TICKS_B,
    TAG_S_MISSING,
    combine_leg_tags,
    compare_leg,
    g5_inputs_present,
    licensed_next_family,
    refuse_genesis_eyes_ok,
)
from lumina_core.birth.genesis_hold_compare_report import render_audit, render_verdict
from lumina_core.birth.genesis_hold_compare_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.rl.observation_builder import OBSERVATION_DIM

POINTER = (
    "\n---\n\n"
    "## Pointer — genesis HOLD_COMPARE follow-on\n\n"
    "Gate 1 cache-source honesty + Gate 2 HOLD_COMPARE live under "
    "`reports/genesis_cloud_run`. G5 ledgers were read-only. Floor 150 stays. "
    "GENESIS_EYES_OK is false. No second 10k. REAL=no.\n"
)


def _git(sha_ref: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", sha_ref],
            cwd=str(REPO_ROOT),
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _sha16(raw: str) -> str:
    text = str(raw or "").strip()
    if len(text) >= 16:
        return text[:16]
    return text


def _gate1_tag() -> str:
    syn = real_data_percentage([{"source": "synthetic_cloud_fixture"}])
    real = real_data_percentage([{"source": "real"}])
    lie = real_data_percentage([{"source": "realistic_sim"}])
    if syn == 0.0 and real == 100.0 and lie == 0.0:
        return "HONEST_OK"
    return "HONEST_FAIL"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def run_hold_compare() -> dict[str, Any]:
    origin_main = _git("origin/main")
    gate0 = {
        "origin_main": origin_main,
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "pct_synthetic": real_data_percentage([{"source": "synthetic_cloud_fixture"}]),
        "pct_real": real_data_percentage([{"source": "real"}]),
        "pct_REAL_NT": real_data_percentage([{"source": "REAL_NT"}]),
        "G5_flags_present": G5_FLAGS.is_file(),
    }
    g5: dict[str, Any] = {}
    if G5_FLAGS.is_file():
        g5 = json.loads(G5_FLAGS.read_text(encoding="utf-8"))
        gate0["G5_tag"] = g5.get("G5_tag")
        gate0["fixture_train_hash"] = g5.get("fixture_train_hash")
        gate0["REAL"] = g5.get("REAL")
    gate1 = _gate1_tag()
    t1 = table_t1_honesty()
    if float(t1["pct_synthetic_cloud_fixture"]) != 0.0:
        gate1 = "HONEST_FAIL"
    if g5_inputs_present():
        cmp_a = compare_leg(
            birth_path=G5_BIRTH_A,
            child_path=G5_EYES_A,
            holdout_ticks=HOLDOUT_TICKS_A,
            expected_n_policy_child=113,
        )
        cmp_b = compare_leg(
            birth_path=G5_BIRTH_B,
            child_path=G5_EYES_B,
            holdout_ticks=HOLDOUT_TICKS_B,
            expected_n_policy_child=103,
        )
        gate2 = combine_leg_tags(str(cmp_a["cause"]), str(cmp_b["cause"]))
    else:
        cmp_a = {"birth": {}, "child": {"n_policy": 0}, "cause": TAG_S_MISSING}
        cmp_b = {"birth": {}, "child": {"n_policy": 0}, "cause": TAG_S_MISSING}
        gate2 = TAG_S_MISSING
    if gate1 == "HONEST_FAIL":
        tag = "GENESIS_FOLLOWON_FAIL"
        family = "H_NONE"
    elif gate2 == TAG_S_MISSING:
        tag = "S_MISSING"
        family = "H_NONE"
    else:
        tag = "GENESIS_FOLLOWON_OK"
        family = licensed_next_family(gate2, gate1_ok=True)
    n_a = int((cmp_a.get("child") or {}).get("n_policy") or 0)
    n_b = int((cmp_b.get("child") or {}).get("n_policy") or 0)
    flags = refuse_genesis_eyes_ok(
        {
            "source": "genesis_followon",
            "gate1_tag": gate1,
            "gate2_tag": gate2,
            "tag": tag,
            "law": "SHADOW",
            "licensed_next_family": family,
            "POLICY_EDGE_MIN_TRADES": 150,
            "n_policy_A_child": n_a,
            "n_policy_B_child": n_b,
            "HOLE_MOVED_A": False,
            "HOLE_MOVED_B": False,
            "GENESIS_EYES_OK": False,
            "learn_called": False,
            "optimizer_steps": 0,
            "evolution_proof_stamped": False,
            "REAL": "no",
            "playground": False,
            "hook_default": False,
            "used_old_path_early": False,
            "real_data_pct_synthetic_fixture": 0.0,
            "overall": "GENESIS_FOLLOWON SHADOW_MEASURE",
        }
    )
    t0 = table_t0_identity(
        origin_main=origin_main,
        train_hash=str(g5.get("fixture_train_hash") or ""),
        newborn_sha16=_sha16(str(g5.get("newborn_zip_sha256") or "")),
        child_sha16=_sha16(str(g5.get("mark_eyes_child_sha256") or "")),
    )
    t2_a = table_t2_leg("A", cmp_a)
    t2_b = table_t2_leg("B", cmp_b)
    t3 = table_t3_license(
        combined_tag=tag,
        gate1_tag=gate1,
        gate2_tag=gate2,
        licensed_next=family,
    )
    _write_json(GENESIS_ART / "genesis_hold_compare_A.json", {**cmp_a, "t2": t2_a})
    _write_json(GENESIS_ART / "genesis_hold_compare_B.json", {**cmp_b, "t2": t2_b})
    _write_json(GENESIS_ART / "genesis_hold_compare_flags.json", flags)
    (GENESIS_ROOT / "GENESIS_HOLD_COMPARE_AUDIT.md").write_text(
        render_audit(gate0=gate0, t0=t0, t1=t1, t2_a=t2_a, t2_b=t2_b, t3=t3, flags=flags),
        encoding="utf-8",
    )
    (GENESIS_ROOT / "GENESIS_HOLD_COMPARE_VERDICT.md").write_text(
        render_verdict(flags=flags, t2_a=t2_a, t2_b=t2_b),
        encoding="utf-8",
    )
    _append_logs(flags)
    return flags


def _append_logs(flags: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    block = [
        f"## {now} — genesis HOLD_COMPARE follow-on",
        "",
        f"- tag=`{flags.get('tag')}` gate1=`{flags.get('gate1_tag')}` "
        f"gate2=`{flags.get('gate2_tag')}` law=`SHADOW`",
        f"- licensed_next_family=`{flags.get('licensed_next_family')}`",
        f"- n_policy_child A/B=`{flags.get('n_policy_A_child')}`/`{flags.get('n_policy_B_child')}` "
        f"floor=150 GENESIS_EYES_OK=false learn_called=false REAL=no",
        "",
        HONESTY_PARAGRAPH,
        "",
    ]
    log_path = GENESIS_ROOT / "LUMINA_GENESIS_EXPERIMENT_LOG.md"
    existing = log_path.read_text(encoding="utf-8") if log_path.is_file() else "# LUMINA Genesis experiment log\n\n"
    if "genesis HOLD_COMPARE follow-on" not in existing:
        log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    birth_log = REPO_ROOT / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if birth_log.is_file():
        text = birth_log.read_text(encoding="utf-8")
        if "genesis HOLD_COMPARE follow-on" not in text:
            birth_log.write_text(text.rstrip() + POINTER, encoding="utf-8")


def main() -> int:
    flags = run_hold_compare()
    print(json.dumps(flags, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
