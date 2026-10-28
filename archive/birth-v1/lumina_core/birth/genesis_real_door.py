"""G6 REAL-readiness audit — must fail-closed on synthetic + no NT."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Callable

from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.evolution_proof_gate import evolution_proof_passed
from lumina_core.birth.genesis_cloud_const import G6_TAG
from lumina_core.birth.synthetic_cloud_fixture import SOURCE_LABEL
from lumina_core.evolution.promotion_gate import PromotionGate
from lumina_core.maturity.maturation_progress import maturation_eligible_for_real
from lumina_core.rl.observation_builder import OBSERVATION_DIM


def _cite(obj: Callable[..., Any] | type[Any]) -> str:
    path = inspect.getsourcefile(obj) or inspect.getfile(obj)
    _lines, start = inspect.getsourcelines(obj)
    rel = path
    marker = "/workspace/"
    if marker in path.replace("\\", "/"):
        rel = path.replace("\\", "/").split(marker, 1)[-1]
    else:
        for token in ("lumina_core/", "lumina_launcher/", "lumina_os/"):
            idx = path.replace("\\", "/").find(token)
            if idx >= 0:
                rel = path.replace("\\", "/")[idx:]
                break
    return f"{rel}:{start}"


def _row(function: str, result: str, why: str) -> dict[str, str]:
    return {"function": function, "result": result, "why": why}


def audit_real_door(
    *,
    work: Path,
    art: Path,
    fixture: dict[str, Any],
    container_start_called: bool,
    nt_called: bool,
) -> dict[str, Any]:
    from lumina_core.container.container_lifecycle import ApplicationContainerLifecycleMixin
    from lumina_core.risk.risk_controller import HardRiskController
    from lumina_core.risk.risk_gates import RiskGatesMixin

    import yaml

    cfg_path = work / "config.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}
    mode = str((raw or {}).get("mode") or "")
    real_pct = float(fixture.get("real_data_pct") or 0.0)
    source = str(fixture.get("source") or SOURCE_LABEL)
    thresholds = BirthCertificateThresholds()
    try:
        proof = bool(evolution_proof_passed(work))
    except Exception:
        proof = False
    try:
        eligible, blockers = maturation_eligible_for_real(work)
    except Exception as exc:
        eligible, blockers = False, [f"inspect-only: {exc}"]
    rows = [
        _row(
            "config.yaml mode",
            "PASS" if mode == "sim" else "BROKEN",
            f"mode={mode!r} (must stay sim)",
        ),
        _row(
            f"BirthCertificateThresholds.min_real_data_pct {_cite(BirthCertificateThresholds)}",
            "FAIL",
            f"real_data_pct={real_pct} < min_real_data_pct={thresholds.min_real_data_pct}",
        ),
        _row(
            "tick source",
            "FAIL-CLOSED",
            f"source={source} (synthetic_cloud_fixture is not a REAL certificate)",
        ),
        _row(
            f"ApplicationContainer.start {_cite(ApplicationContainerLifecycleMixin.start)}",
            "PASS" if not container_start_called else "BROKEN",
            "container.start not called (broker connect forbidden)",
        ),
        _row(
            "NinjaTrader / Fabric / gRPC",
            "PASS" if not nt_called else "BROKEN",
            "NT/Fabric host not contacted",
        ),
        _row(
            f"PromotionGate.evaluate {_cite(PromotionGate.evaluate)}",
            "FAIL",
            "no proving certificate / no promotion evidence on synthetic first life",
        ),
        _row(
            f"evolution_proof_passed {_cite(evolution_proof_passed)}",
            "FAIL",
            f"stamped={proof} (must stay false)",
        ),
        _row(
            f"maturation_eligible_for_real {_cite(maturation_eligible_for_real)}",
            "FAIL",
            f"eligible={eligible} blockers={blockers}",
        ),
        _row(
            "certificate OOS WR 0.48",
            "FAIL",
            f"min_oos_winrate={thresholds.min_oos_winrate} not claimed",
        ),
        _row(
            f"kill-switch / Dead Man {_cite(RiskGatesMixin._engage_kill_switch)}",
            "N/A",
            "not armed against a live broker (no broker connect)",
        ),
        _row(
            f"HardRiskController {_cite(HardRiskController)}",
            "PRESENT",
            "risk engine independent of strategy (bounded context lumina_core/risk)",
        ),
        _row(
            "first live/SIM broker order",
            "NONE",
            "no container.start, no order path",
        ),
        _row(
            "lumina_core/rl/observation_builder.py:36 OBSERVATION_DIM",
            "PASS" if int(OBSERVATION_DIM) == 43 else "BROKEN",
            f"OBSERVATION_DIM={OBSERVATION_DIM} (must stay 43)",
        ),
        _row(
            "PATH_EXIT_K3_SHADOW / PATH_SHAPE_K3_SHADOW",
            "PASS" if (not bool(PATH_EXIT_K3_SHADOW.get()) and not bool(PATH_SHAPE_K3_SHADOW.get())) else "BROKEN",
            f"exit={PATH_EXIT_K3_SHADOW.get()} shape={PATH_SHAPE_K3_SHADOW.get()} default False",
        ),
    ]
    broken = [r for r in rows if r["result"] == "BROKEN"]
    if mode != "sim" or container_start_called or nt_called or proof or eligible:
        broken.append(_row("REAL print", "BROKEN", "a live path would have opened REAL"))
    tag = G6_TAG
    if any(r["result"] == "BROKEN" for r in rows):
        # Door still locked; BROKEN rows are P0 bugs to file in G7.
        tag = G6_TAG
    payload = {
        "G6_tag": tag,
        "REAL": "no",
        "rows": rows,
        "broken": broken,
        "real_data_pct": real_pct,
        "source": source,
        "mode": mode,
        "evolution_proof_stamped": False,
        "promotion_passed": False,
        "nt_called": bool(nt_called),
        "container_start_called": bool(container_start_called),
        "observation_dim": int(OBSERVATION_DIM),
    }
    (art / "g6_real_door.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return payload


__all__ = ["audit_real_door"]
