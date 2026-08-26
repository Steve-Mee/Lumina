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
import { metricPctForCriteria } from "@/lib/birth/birthStageScorecardHealth";

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
    expect(formatBirthMetricTarget(model)).toContain("median loss R");
    expect(formatBirthMetricTarget(model)).not.toContain("lifetime or rolling");
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
    expect(detail).toContain("occupancy 30-70%");
    expect(detail).toContain("median loss R");
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

  it("formats closed-loop process-R as R, never percent or syncing", () => {
    const model = {
      passCriteriaId: "closed_loop",
      metricLabel: "Median loss R",
      metricValue: 9.3719,
      metricMax: 1.5,
      tradesDone: 1300,
    };
    expect(formatBirthMetricValue(model)).toBe("9.37R");
    expect(formatBirthMetricValuePrecise(model)).toBe("9.37R");
    expect(formatBirthMetricDetail(model)).toContain("9.37R");
    expect(formatBirthMetricDetail(model)).not.toContain("%");
    expect(formatBirthMetricValue(model)).not.toContain("%");
  });

  it("missing process-R after trades is dash, not syncing", () => {
    const model = {
      passCriteriaId: "closed_loop",
      metricLabel: "Median loss R",
      metricValue: null,
      metricMax: 1.5,
      tradesDone: 700,
    };
    expect(formatBirthMetricValue(model)).toBe("—");
    expect(formatBirthMetricValuePrecise(model)).toBe("—");
    expect(formatBirthMetricDetail(model)).toContain("fail-closed");
    expect(formatBirthMetricValuePrecise(model)).not.toBe("syncing…");
  });

  it("closed-loop bar is lower-is-better vs 1.5R, never 937%", () => {
    expect(metricPctForCriteria("closed_loop", 1.1, null, null, 1.5)).toBe(100);
    expect(metricPctForCriteria("closed_loop", 9.37, null, null, 1.5)).toBeCloseTo(
      (1.5 / 9.37) * 100,
    );
    expect(metricPctForCriteria("closed_loop", 9.37, null, null, 1.5)).toBeLessThan(20);
  });

  it("formats WR-50 expectancy and rejects legacy USD-scale values", () => {
    expect(formatBirthExpectancyPercent(-0.174).value).toBe("-17%");
    expect(isBirthExpectancyProxyValid(-1493.581188)).toBe(false);
    const stale = formatBirthExpectancyPercent(-1493.581188);
    expect(stale.value).toBe("—");
    expect(stale.hint).toContain("stale scale");
  });
});
