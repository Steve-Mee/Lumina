"""One-shot: clear poisoned early EdgeScore champion from live birth state."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lumina_core.birth.config import load_birth_v2_config
from lumina_core.birth.starship_birth import sanitize_edgescore_champion


def main() -> None:
    cfg = load_birth_v2_config(ROOT).curriculum
    for rel in ("state/lumina_birth_checkpoint.json", "state/lumina_birth_progress.json"):
        path = ROOT / rel
        if not path.is_file():
            print(f"skip missing {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        metrics = data.get("stage_metrics") if isinstance(data.get("stage_metrics"), dict) else data
        best = float(metrics.get("best_edgescore") or data.get("best_edgescore") or 0.0)
        at = int(metrics.get("best_edgescore_at_trade") or data.get("best_edgescore_at_trade") or 0)
        wr = float(
            metrics.get("plateau_best_winrate")
            or metrics.get("best_winrate")
            or data.get("best_winrate")
            or 0.0
        )
        req = int(
            metrics.get("stage_pass_gate_trades") or data.get("stage_pass_gate_trades") or 200
        )
        _new_best, _new_at, cleared = sanitize_edgescore_champion(
            best_edgescore=best,
            best_edgescore_at_trade=at,
            best_winrate=wr,
            required=req,
            cfg=cfg,
        )
        print(f"{path.name}: before edge={best} at={at} wr={wr:.4f} cleared={cleared}")
        if not cleared:
            continue
        if isinstance(data.get("stage_metrics"), dict):
            data["stage_metrics"]["best_edgescore"] = 0.0
            data["stage_metrics"]["best_edgescore_at_trade"] = 0
            data["stage_metrics"]["best_edgescore_policy_path"] = ""
        data["best_edgescore"] = 0.0
        data["best_edgescore_at_trade"] = 0
        data["best_edgescore_policy_path"] = ""
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        print(f"sanitized {path}")

    champ = ROOT / "lumina_agents" / "ppo" / "birth_champion_edgescore_stage1_trend.zip"
    if champ.is_file():
        poisoned = champ.with_name(champ.stem + "_poisoned_early.bak")
        if poisoned.exists():
            poisoned.unlink()
        champ.replace(poisoned)
        print(f"renamed champion -> {poisoned.name}")
    else:
        print("no champion zip present")


if __name__ == "__main__":
    main()
