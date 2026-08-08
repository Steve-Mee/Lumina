import { describe, expect, it } from "vitest";

import {
  formatBirthChampionEdgeScore,
  formatBirthEdgeScorePercent,
  formatBirthExpectancyPercent,
  formatBirthMetricDetail,
  formatBirthMetricTarget,
  formatBirthMetricValue,
  formatBirthMetricValuePrecise,
  isBirthExpectancyProxyValid,
} from "@/lib/birth/birthMetricFormat";

describe("birthMetricFormat", () => {
  it("formats EdgeScore as percent", () => {
    const model = {
      passCriteriaId: "trend_edgescore",
      metricLabel: "EdgeScore",
      metricValue: 0.22,
      metricTarget: 0.35,
      tradesDone: 200,
    };
    expect(formatBirthMetricValue(model)).toBe("22%");
    expect(formatBirthMetricValuePrecise(model)).toBe("22.0%");
    expect(formatBirthMetricTarget(model)).toContain("lifetime or rolling");
    expect(formatBirthMetricValue(model)).toContain("%");
  });

  it("formats hygiene winrate as percent", () => {
    const model = {
      passCriteriaId: "trend_winrate",
      metricLabel: "Win rate",
      metricValue: 0.42,
      metricTarget: 0.45,
      tradesDone: 200,
    };
    expect(formatBirthMetricValue(model)).toBe("42%");
  });

  it("formats stage2/3 EdgeScore as percent", () => {
    for (const id of ["range_edgescore", "mixed_edgescore"] as const) {
      const model = {
        passCriteriaId: id,
        metricLabel: "EdgeScore",
        metricValue: 0.31,
        metricTarget: 0.35,
        tradesDone: 200,
      };
      expect(formatBirthMetricValue(model)).toBe("31%");
      expect(formatBirthMetricValue(model)).toContain("%");
    }
  });

  it("formatBirthMetricDetail keeps EdgeScore percent for S2/S3", () => {
    const detail = formatBirthMetricDetail({
      passCriteriaId: "range_edgescore",
      metricLabel: "EdgeScore",
      metricValue: 0.27,
      metricTarget: 0.35,
      tradesDone: 200,
    });
    expect(detail).toContain("27%");
    expect(detail).toContain("flat 30-70%");
    expect(detail).not.toContain("0.27");
  });

  it("formats champion EdgeScore as percent", () => {
    expect(formatBirthEdgeScorePercent(0.273)).toBe("27%");
    expect(formatBirthEdgeScorePercent(0.273, { precise: true })).toBe("27.3%");
    expect(formatBirthEdgeScorePercent(null)).toBe("—");
  });

  it("does not show fake 0% for unlocked champion EdgeScore", () => {
    const pending = formatBirthChampionEdgeScore({
      best_edgescore: 0,
      best_edgescore_at_trade: 0,
      stage_trades: 137,
      stage_pass_gate_trades: 300,
      edgescore_champion_min_trades: 300,
    });
    expect(pending.value).toBe("—");
    expect(pending.hint).toContain("300");
    expect(pending.hint).toContain("137");

    const locked = formatBirthChampionEdgeScore({
      best_edgescore: 0.334,
      best_edgescore_at_trade: 320,
      edgescore_champion_locked: true,
      stage_trades: 400,
      edgescore_champion_min_trades: 300,
    });
    expect(locked.value).toBe("33%");
    expect(locked.hint).toContain("320");
  });

  it("formats WR-50 expectancy and rejects legacy USD-scale values", () => {
    expect(formatBirthExpectancyPercent(-0.174).value).toBe("-17%");
    expect(isBirthExpectancyProxyValid(-1493.581188)).toBe(false);
    const stale = formatBirthExpectancyPercent(-1493.581188);
    expect(stale.value).toBe("—");
    expect(stale.hint).toContain("stale scale");
  });
});
