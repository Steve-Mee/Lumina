import { describe, expect, it } from "vitest";

import {
  formatBirthExpectancyPercent,
  formatBirthMetricTarget,
} from "@/lib/birth/birthMetricFormat";
import {
  extractStageScorecard,
  humanizeEdgescoreBlockerDetail,
  isRawEdgescorePassReason,
  isStageGoalMet,
} from "@/lib/birth/birthStageScorecard";

describe("birth HUD copy", () => {
  it("detects raw EdgeScore pass_reason dumps", () => {
    expect(
      isRawEdgescorePassReason(
        "edgescore=0.450 wr=32.6% hold=72.5% exp=-0.174 entropy=n/a trades=215/200 blockers=expectancy -0.174 < -0.150",
      ),
    ).toBe(true);
    expect(isRawEdgescorePassReason("Expectancy -17% (need >= -15%) | EdgeScore 25%")).toBe(
      false,
    );
  });

  it("humanizes raw blocker into percent checklist", () => {
    const detail = humanizeEdgescoreBlockerDetail(
      {
        edgescore: 0.25,
        stage_winrate: 0.326,
        stage_hold_ratio: 0.725,
        expectancy_proxy: -0.174,
        entropy_alive: false,
        policy_entropy: null,
        pass_reason:
          "edgescore=0.450 wr=32.6% hold=72.5% exp=-0.174 entropy=n/a blockers=expectancy",
      },
      "edgescore=0.450 wr=32.6% hold=72.5% exp=-0.174 entropy=n/a blockers=expectancy",
    );
    expect(detail).toContain("Expectancy -17%");
    expect(detail).toContain("WR 33%");
    expect(detail).toContain("EdgeScore 25%");
    expect(detail).not.toContain("edgescore=");
    expect(detail).not.toMatch(/â|Â/);
  });

  it("formats EdgeScore target with full goals", () => {
    const target = formatBirthMetricTarget({
      passCriteriaId: "trend_edgescore",
      metricLabel: "EdgeScore",
      metricValue: 0.25,
      metricTarget: null,
    });
    expect(target).toContain("hygiene WR>=35% (lifetime or rolling)");
    expect(target).toContain("entropy alive");
    expect(target).toContain("expectancy >= -15%");
    expect(target).not.toMatch(/â|Â/);
  });

  it("formats expectancy as WR-50 percent", () => {
    const formatted = formatBirthExpectancyPercent(-0.174);
    expect(formatted.value).toBe("-17%");
    expect(formatted.hint).toContain("WR-50%");
    expect(formatted.hint).toContain("-15%");
  });

  it("ignores legacy pass_metric_target 0.35 for EdgeScore bars", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage1_trend",
      pass_criteria_id: "trend_edgescore",
      pass_metric_label: "EdgeScore",
      pass_metric_target: 0.35,
      edgescore: 0.25,
      stage_trades: 100,
      stage_target_trades: 200,
    });
    expect(scorecard?.metricTarget).toBeNull();
    expect(scorecard?.metricPct).toBeCloseTo(25);
  });

  it("does not treat EdgeScore hygiene target as goal met", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage1_trend",
      pass_criteria_id: "trend_edgescore",
      pass_metric_label: "EdgeScore",
      edgescore: 0.4,
      pass_metric_target: 0.35,
      stage_trades: 250,
      stage_target_trades: 200,
      stage_pass_gate_trades: 200,
    });
    expect(scorecard).not.toBeNull();
    // No blocker + volume met => goal met even though score is a composite.
    expect(isStageGoalMet(scorecard!)).toBe(true);

    const blocked = {
      ...scorecard!,
      blockerDetail: "Expectancy -17% (need >= -15%) | EdgeScore 25%",
      blockerLabel: "Blocking metric",
    };
    expect(isStageGoalMet(blocked)).toBe(false);
  });

  it("sanitizes goal label separators", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage1_trend",
      pass_criteria_id: "trend_edgescore",
      pass_criteria_label:
        ">=200 pass gate (2000 budget) \u00b7 EdgeScore \u00b7 hygiene WR>=35%",
      stage_trades: 100,
      stage_target_trades: 200,
    });
    expect(scorecard?.goalLabel).toContain("|");
    expect(scorecard?.goalLabel).not.toContain("\u00b7");
    expect(scorecard?.goalLabel).not.toMatch(/â|Â/);
  });

  it("maps hygiene WR telemetry and honest blocker copy", () => {
    const scorecard = extractStageScorecard({
      curriculum_stage: "stage1_trend",
      pass_criteria_id: "trend_edgescore",
      pass_metric_label: "EdgeScore",
      edgescore: 0.45,
      stage_trades: 269,
      stage_target_trades: 200,
      stage_winrate: 0.29,
      rolling_winrate_500: 0.334764,
      rolling_winrate_source: "true_window",
      rolling_window_trades_covered: 233,
      hygiene_wr_floor: 0.35,
      hygiene_wr_lifetime: 0.29,
      hygiene_wr_rolling: 0.334764,
      hygiene_wr_effective: 0.29,
      hygiene_wr_source: "neither",
      rolling_wr_eligible: false,
      stage_blocker_metric: "winrate",
      pass_reason:
        "Hygiene WR lifetime 29% / rolling 33% (need >=35%; rolling counts after 400) | EdgeScore 45%",
    });
    expect(scorecard?.hygieneWrEffective).toBeCloseTo(0.29);
    expect(scorecard?.hygieneWrLifetime).toBeCloseTo(0.29);
    expect(scorecard?.hygieneWrRolling).toBeCloseTo(0.334764);
    expect(scorecard?.rollingWrEligible).toBe(false);
    expect(scorecard?.blockerDetail).toContain("lifetime 29%");
    expect(scorecard?.blockerDetail).toContain("rolling 33%");
    expect(scorecard?.blockerDetail).toContain("400");
  });
});
