import { describe, expect, it } from "vitest";

import {
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

  it("formats WR-50 expectancy and rejects legacy USD-scale values", () => {
    expect(formatBirthExpectancyPercent(-0.174).value).toBe("-17%");
    expect(isBirthExpectancyProxyValid(-1493.581188)).toBe(false);
    const stale = formatBirthExpectancyPercent(-1493.581188);
    expect(stale.value).toBe("—");
    expect(stale.hint).toContain("stale scale");
  });
});
