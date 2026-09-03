#!/usr/bin/env python3
"""Harvest birth-exit π* into reports/birth_cloud_run/artifacts/.

Runs a certified Birth in an isolated workspace so PR #14 s5_receipt.json and
fitness checksum 707b5ab9d6b9af96 are not overwritten. On S5-pass the complete
hook writes the zip BEFORE polish. This script then seals that zip onto the
grind load path. It never copies lumina_agents/ppo/*.zip.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
HARVEST_ROOT = REPO_ROOT / "reports" / "pi_star_harvest"
HARVEST_WS = HARVEST_ROOT / "workspace"
CANONICAL_REPORTS = REPO_ROOT / "reports" / "birth_cloud_run"
PR14_FITNESS = "707b5ab9d6b9af96"


def _require_ml() -> None:
    missing: list[str] = []
    for name in ("torch", "stable_baselines3", "gymnasium"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise RuntimeError(
            "harvest requires " + ",".join(missing) + " — install CPU torch + sb3, do not fake π*"
        )


def _pr14_receipts_untouched() -> dict[str, Any]:
    s5 = CANONICAL_REPORTS / "s5_receipt.json"
    fitness = CANONICAL_REPORTS / "lumina_birth_fitness_vector.json"
    payload: dict[str, Any] = {
        "s5_exists": s5.is_file(),
        "fitness_exists": fitness.is_file(),
        "s5_trades": None,
        "fitness_checksum": None,
    }
    if s5.is_file():
        raw = json.loads(s5.read_text(encoding="utf-8"))
        payload["s5_trades"] = raw.get("trades")
    if fitness.is_file():
        raw = json.loads(fitness.read_text(encoding="utf-8"))
        payload["fitness_checksum"] = str(raw.get("s5_receipt_checksum") or "")
    payload["pr14_checksum_intact"] = payload["fitness_checksum"] == PR14_FITNESS
    return payload


def main() -> int:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ.setdefault("LUMINA_LOG_LEVEL", "INFO")
    os.environ["VOICE_ENABLED"] = "false"
    sys.path.insert(0, str(REPO_ROOT))
    _require_ml()

    before = _pr14_receipts_untouched()
    if not before["pr14_checksum_intact"]:
        print("REFUSE: PR #14 fitness checksum missing or mutated before harvest", file=sys.stderr)
        return 2

    from lumina_core.birth.birth_exit_policy_export import (
        is_gitignored_ppo_zip,
        resolve_pi_star_path,
        seal_harvested_pi_star,
    )

    shadow_path = REPO_ROOT / "scripts" / "run_birth_cloud_shadow.py"
    spec = importlib.util.spec_from_file_location("run_birth_cloud_shadow", shadow_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load run_birth_cloud_shadow")
    shadow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shadow)

    HARVEST_WS.mkdir(parents=True, exist_ok=True)
    HARVEST_ROOT.mkdir(parents=True, exist_ok=True)
    shadow._prepare_workspace(HARVEST_WS, repo_root=REPO_ROOT)
    code = shadow.run_birth(
        workspace=HARVEST_WS,
        reports_dir=HARVEST_ROOT,
        force=True,
        timeout_sec=6 * 60 * 60,
        target_trades=8_000,
        ppo_update_timesteps=1_000,
    )
    harvested = resolve_pi_star_path(HARVEST_WS)
    canonical = CANONICAL_REPORTS / "artifacts" / "birth_exit_pi_star.zip"
    if harvested.is_file() and not is_gitignored_ppo_zip(harvested):
        seal_harvested_pi_star(
            harvested,
            canonical,
            extra={
                "harvest_workspace": str(HARVEST_WS),
                "harvest_exit_code": code,
                "pr14_s5_receipt_checksum": PR14_FITNESS,
                "pr14_receipts_not_copied": True,
            },
        )
    after = _pr14_receipts_untouched()
    report = {
        "schema": "pi_star_harvest_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "birth_exit_code": code,
        "harvested_path": str(harvested),
        "harvested_exists": harvested.is_file(),
        "canonical_path": str(canonical),
        "canonical_exists": canonical.is_file(),
        "canonical_bytes": int(canonical.stat().st_size) if canonical.is_file() else 0,
        "used_gitignored_ppo": False,
        "pr14_before": before,
        "pr14_after": after,
        "pr14_untouched": after == before and after["pr14_checksum_intact"] is True,
    }
    (HARVEST_ROOT / "harvest_receipt.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    audit = CANONICAL_REPORTS / "PI_STAR_HARVEST_AUDIT.md"
    audit.write_text(
        "\n".join(
            [
                "# π* HARVEST AUDIT",
                "",
                f"**Date:** {report['timestamp']}",
                "**Engine:** isolated certified Birth → export before polish → seal to grind path",
                "**Capital:** SIM / certified-shadow. REAL=no.",
                "",
                json.dumps(report, indent=2),
                "",
                "PR #14 `s5_receipt.json` / fitness checksum `707b5ab9d6b9af96` were not rewritten.",
                "Grind load path is only `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if not report["canonical_exists"] or not report["pr14_untouched"]:
        return 2
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
