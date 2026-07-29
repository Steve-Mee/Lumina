import { describe, expect, it } from "vitest";

import { extractStageScorecard } from "@/lib/birth/birthStageScorecard";
import {
  formatBirthMetricValue,
} from "@/lib/birth/birthMetricFormat";

describe("birthStageScorecard EdgeScore S2/S3", () => {
  it("maps range_edgescore from progress.edgescore as percent metric", () => {
    const scorecard = extractStageScorecard(
      {
        curriculum_stage: "stage2_range",
        pass_criteria_id: "range_edgescore",
        pass_metric_label: "EdgeScore",
        edgescore: 0.27,
        stage_trades: 200,
        target_trades: 300,
      },
      Date.now(),
    );
    expect(scorecard?.passCriteriaId).toBe("range_edgescore");
    expect(scorecard?.metricValue).toBe(0.27);
    expect(scorecard?.metricLabel).toBe("EdgeScore");
    expect(
      formatBirthMetricValue({
        passCriteriaId: scorecard!.passCriteriaId,
        metricLabel: scorecard!.metricLabel,
        metricValue: scorecard!.metricValue,
        metricTarget: scorecard!.metricTarget,
        tradesDone: scorecard!.tradesDone,
      }),
    ).toBe("27%");
  });

  it("infers mixed_edgescore for stage3 and binds edgescore", () => {
    const scorecard = extractStageScorecard(
      {
        curriculum_stage: "stage3_mixed",
        edgescore: 0.41,
        stage_trades: 400,
        target_trades: 500,
      },
      Date.now(),
    );
    expect(scorecard?.passCriteriaId).toBe("mixed_edgescore");
    expect(scorecard?.metricValue).toBe(0.41);
    expect(
      formatBirthMetricValue({
        passCriteriaId: scorecard!.passCriteriaId,
        metricLabel: scorecard!.metricLabel,
        metricValue: scorecard!.metricValue,
        metricTarget: scorecard!.metricTarget,
        tradesDone: scorecard!.tradesDone,
      }),
    ).toBe("41%");
  });

  it("falls back hygiene lifetime from stage_winrate when hygiene fields absent", () => {
    const scorecard = extractStageScorecard(
      {
        curriculum_stage: "stage1_trend",
        pass_criteria_id: "trend_edgescore",
        edgescore: 0.45,
        stage_trades: 269,
        stage_winrate: 0.29,
        rolling_winrate_500: 0.33,
      },
      Date.now(),
    );
    expect(scorecard?.hygieneWrLifetime).toBeCloseTo(0.29);
    expect(scorecard?.hygieneWrRolling).toBeCloseTo(0.33);
  });
});
