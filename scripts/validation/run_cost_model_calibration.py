from __future__ import annotations

import argparse
import json
from pathlib import Path

from lumina_core.monitoring.reality_gap_tracker import RealityGapThresholds, run_daily_reality_gap
from lumina_core.risk.cost_model import TradeExecutionCostModel
from lumina_core.risk.cost_model_calibrator import apply_calibration_from_state, run_daily_calibration


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run daily cost-model calibration and reality-gap tracking.")
    parser.add_argument("--audit-path", default="logs/trade_fill_audit.jsonl")
    parser.add_argument("--calibration-state", default="state/cost_model_calibration.json")
    parser.add_argument("--instrument", default="MES")
    parser.add_argument("--atr-fallback", type=float, default=8.0)
    parser.add_argument("--time-period", default="midday")
    parser.add_argument("--paper-metrics-path", default="state/validation/paper_fill_metrics.json")
    parser.add_argument("--reality-gap-log", default="logs/reality_gap.jsonl")
    parser.add_argument("--spread-threshold", type=float, default=0.5)
    parser.add_argument("--slippage-threshold", type=float, default=0.5)
    parser.add_argument("--fill-rate-threshold", type=float, default=0.1)
    parser.add_argument("--sigma-multiplier", type=float, default=1.0)
    parser.add_argument("--sigma-floor", type=float, default=0.0)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    calibration = run_daily_calibration(
        audit_path=Path(args.audit_path),
        state_path=Path(args.calibration_state),
        instrument=str(args.instrument),
        atr_fallback=float(args.atr_fallback),
        time_period=str(args.time_period),
        sigma_multiplier=float(args.sigma_multiplier),
        sigma_floor=float(args.sigma_floor),
    )
    model = TradeExecutionCostModel.from_config({}, instrument=str(args.instrument))
    applied_bias_ticks, applied_sigma = apply_calibration_from_state(
        model,
        state_path=Path(args.calibration_state),
        sigma_fallback=float(args.sigma_floor),
    )

    reality_gap = run_daily_reality_gap(
        live_audit_path=Path(args.audit_path),
        paper_metrics_path=Path(args.paper_metrics_path),
        output_log_path=Path(args.reality_gap_log),
        thresholds=RealityGapThresholds(
            spread_tick_gap_max=float(args.spread_threshold),
            slippage_tick_gap_max=float(args.slippage_threshold),
            fill_rate_gap_max=float(args.fill_rate_threshold),
        ),
    )

    print(
        json.dumps(
            {
                "status": "breach" if reality_gap.threshold_breached else "ok",
                "calibration": {
                    "sample_count": calibration.sample_count,
                    "mean_bias_usd": calibration.mean_bias_usd,
                    "stdev_bias_usd": calibration.stdev_bias_usd,
                    "mean_bias_ticks": calibration.mean_bias_ticks,
                    "stdev_bias_ticks": calibration.stdev_bias_ticks,
                    "recommended_slippage_sigma": calibration.recommended_slippage_sigma,
                    "state_path": args.calibration_state,
                    "applied": {
                        "bias_slippage_ticks": applied_bias_ticks,
                        "slippage_sigma": applied_sigma,
                    },
                },
                "reality_gap": reality_gap.to_record(),
            }
        )
    )
    return 2 if reality_gap.threshold_breached else 0


if __name__ == "__main__":
    raise SystemExit(main())
