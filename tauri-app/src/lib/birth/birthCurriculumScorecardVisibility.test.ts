import { describe, expect, it } from "vitest";

import {
  isBirthCurriculumScorecardActive,
} from "@/lib/birth/birthActiveProgress";
import { extractStageScorecard } from "@/lib/birth/birthStageScorecard";

describe("isBirthCurriculumScorecardActive", () => {
  it("hides scorecard during historical data load even if curriculum_stage stamped", () => {
    expect(
      isBirthCurriculumScorecardActive({
        phase: "loading_history",
        sub_phase: "loading_history",
        curriculum_stage: "stage1_trend",
        curriculum_index: 1,
        stage_trades: 0,
      }),
    ).toBe(false);
    expect(
      extractStageScorecard({
        phase: "loading_history",
        curriculum_stage: "stage1_trend",
        pass_criteria_id: "trend_edgescore",
        stage_trades: 0,
      }),
    ).toBeNull();
  });

  it("hides scorecard during enrich / ticks_ready / policy_init", () => {
    for (const phase of [
      "enriching_regimes",
      "enriching_news",
      "train_holdout_split",
      "holdout_preflight",
      "policy_init",
      "ticks_ready",
    ]) {
      expect(
        isBirthCurriculumScorecardActive({
          phase,
          curriculum_stage: "stage1_trend",
        }),
      ).toBe(false);
    }
  });

  it("shows scorecard when curriculum training starts", () => {
    for (const phase of [
      "curriculum_learning",
      "curriculum_stage",
      "ppo_training",
      "curriculum_research",
      "parallel_simulation",
    ]) {
      expect(
        isBirthCurriculumScorecardActive({
          phase,
          curriculum_stage: "stage1_trend",
          stage_trades: 10,
        }),
      ).toBe(true);
    }
    const card = extractStageScorecard({
      phase: "ppo_training",
      curriculum_stage: "stage1_trend",
      curriculum_index: 1,
      curriculum_total: 3,
      pass_criteria_id: "trend_edgescore",
      stage_trades: 50,
      stage_target_trades: 200,
    });
    expect(card).not.toBeNull();
    expect(card?.stageLabel).toMatch(/Stage 1\/3/);
  });

  it("shows stage 2 card only on stage2 curriculum phases", () => {
    const card = extractStageScorecard({
      phase: "curriculum_learning",
      curriculum_stage: "stage2_range",
      curriculum_index: 2,
      curriculum_total: 3,
      stage_display_name: "Range patience",
      pass_criteria_id: "range_edgescore",
      stage_trades: 100,
    });
    expect(card?.stageLabel).toMatch(/Stage 2\/3/);
  });
});
