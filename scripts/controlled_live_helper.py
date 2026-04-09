from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return data


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle, default_flow_style=False, allow_unicode=True)


def inject_config(config_path: Path, mode: str, broker_mode: str) -> int:
    cfg = _load_yaml(config_path)

    cfg["mode"] = str(mode).strip().lower()

    risk = cfg.get("risk_controller")
    if not isinstance(risk, dict):
        risk = {}
        cfg["risk_controller"] = risk

    # Conservative safety rails remain present even in SIM validation scripts.
    risk["daily_loss_cap"] = -150.0
    risk["max_consecutive_losses"] = 1
    risk["max_open_risk_per_instrument"] = 75.0
    risk["max_total_open_risk"] = 150.0
    risk["max_exposure_per_regime"] = 100.0
    risk["cooldown_after_streak"] = 60
    risk["session_cooldown_minutes"] = 60
    risk["enabled"] = True
    risk["enforce_session_guard"] = True
    risk["eod_force_close_minutes_before_session_end"] = 30
    risk["eod_no_new_trades_minutes_before_session_end"] = 60
    risk["margin_tracker_enabled"] = True
    risk["kelly_fraction"] = 0.25

    broker = cfg.get("broker")
    if not isinstance(broker, dict):
        broker = {}
        cfg["broker"] = broker
    broker["backend"] = "live" if broker_mode == "live" else "paper"

    trading = cfg.get("trading")
    if not isinstance(trading, dict):
        trading = {}
        cfg["trading"] = trading

    trading["news_avoidance_pre_minutes"] = 10
    trading["news_avoidance_post_minutes"] = 5
    trading["news_avoidance_high_impact_pre_minutes"] = 15
    trading["news_avoidance_high_impact_post_minutes"] = 10
    trading["eod_force_close_minutes_before_session_end"] = 30
    trading["eod_no_new_trades_minutes_before_session_end"] = 60
    trading["overnight_gap_protection_enabled"] = True
    trading["kelly_fraction_max"] = 0.25
    trading["kelly_min_confidence"] = 0.65

    _save_yaml(config_path, cfg)
    print(f"[OK] Injected controlled-live profile into {config_path} (mode={mode}, broker={broker_mode})")
    return 0


def _summary_candidates() -> list[Path]:
    return [
        Path("state/last_run_summary.json"),
        Path("state/last_run_summary_controlled_live_30m.json"),
        Path("state/last_run_summary_live_30m_paper.json"),
    ]


def contract_check(expected_broker_status: str) -> int:
    found = next((p for p in _summary_candidates() if p.exists()), None)
    if found is None:
        print("[ERROR] No validation summary JSON found")
        return 1

    try:
        payload = json.loads(found.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] Failed to parse {found}: {exc}")
        return 2

    required = ["runtime", "broker_status", "total_trades", "risk_events", "var_breach_count"]
    for key in required:
        if key not in payload:
            print(f"[ERROR] Missing required field: {key}")
            return 3

    got_broker_status = str(payload.get("broker_status", "")).strip().lower()
    if got_broker_status != expected_broker_status.strip().lower():
        print(
            f"[ERROR] Expected broker_status='{expected_broker_status}', got '{payload.get('broker_status')}'"
        )
        return 4

    if int(payload.get("risk_events", 0) or 0) != 0:
        print(f"[WARNING] Expected risk_events=0, got {payload.get('risk_events')}")

    if int(payload.get("var_breach_count", 0) or 0) != 0:
        print(f"[WARNING] Expected var_breach_count=0, got {payload.get('var_breach_count')}")

    print(f"[OK] Contract verified from {found}")
    print(
        f"     runtime={payload.get('runtime')}, broker_status={payload.get('broker_status')}"
    )
    print(
        f"     trades={payload.get('total_trades')}, pnl={payload.get('pnl_realized')}, risk_events={payload.get('risk_events')}"
    )
    return 0


def stability_check() -> int:
    summary_path = Path("state/last_run_summary.json")
    if not summary_path.exists():
        print("[ERROR] state/last_run_summary.json not found; run stability-check first")
        return 1

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] Failed to parse {summary_path}: {exc}")
        return 2

    stability = payload.get("stability_report") if isinstance(payload.get("stability_report"), dict) else {}
    ready_for_real = bool(payload.get("READY_FOR_REAL", stability.get("READY_FOR_REAL", False)))
    status = str(payload.get("stability_status", stability.get("status", "RED"))).upper()

    print(f"[INFO] Stability status: {status}")
    print(f"[INFO] READY_FOR_REAL: {ready_for_real}")
    failures = stability.get("failures", []) if isinstance(stability.get("failures"), list) else []
    if failures:
        print("[INFO] Stability failures: " + ", ".join(str(x) for x in failures))

    if not ready_for_real:
        print("[ERROR] SIM stability gate is RED; REAL cutover blocked")
        return 3

    print("[OK] SIM stability gate is GREEN")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled live helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_inject = sub.add_parser("inject", help="Inject controlled-live config settings")
    p_inject.add_argument("--config", default="config.yaml")
    p_inject.add_argument("--mode", choices=["sim", "real"], required=True)
    p_inject.add_argument("--broker", choices=["paper", "live"], required=True)

    p_check = sub.add_parser("contract-check", help="Validate summary contract")
    p_check.add_argument("--expected-broker-status", required=True)

    sub.add_parser("stability-check", help="Validate READY_FOR_REAL from latest summary")

    args = parser.parse_args()

    if args.cmd == "inject":
        return inject_config(Path(args.config), mode=args.mode, broker_mode=args.broker)
    if args.cmd == "contract-check":
        return contract_check(expected_broker_status=args.expected_broker_status)
    if args.cmd == "stability-check":
        return stability_check()

    return 99


if __name__ == "__main__":
    raise SystemExit(main())
