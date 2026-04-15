from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lumina_core.engine.stress_suite_runner import StressSuiteRunner
from scripts.validation.build_regime_oos_results import build_regime_oos_results


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def main() -> int:
    summary = _load_json(Path("state/last_run_summary.json"))
    regime_payload = _load_json(Path("state/regime_oos_results.json"))
    if not regime_payload:
        generated, source = build_regime_oos_results()
        regime_payload = {
            "schema": "regime_oos_results_v1",
            "source": source,
            "regimes": generated,
        }

    regime_results = regime_payload.get("regimes") if isinstance(regime_payload.get("regimes"), dict) else regime_payload
    if not isinstance(regime_results, dict):
        regime_results = {}

    metrics = {
        "pnl_realized": float(summary.get("pnl_realized", 0.0) or 0.0),
        "max_drawdown": float(summary.get("max_drawdown", 0.0) or 0.0),
        "var_breach_count": int(summary.get("var_breach_count", 0) or 0),
    }

    runner = StressSuiteRunner()
    validation = runner.build_validation_pack(metrics, regime_results)

    output = {
        "status": "pass" if validation.get("ready_for_real") else "fail",
        "inputs": {
            "summary_file": "state/last_run_summary.json",
            "regime_file": "state/regime_oos_results.json",
            "regime_source": regime_payload.get("source", "legacy_or_unknown"),
            "metrics": metrics,
        },
        "validation": validation,
    }

    out_dir = Path("state/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "regime_scorecard.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(json.dumps({"status": output["status"], "output": str(out_path)}))
    return 0 if output["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
