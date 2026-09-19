import { describe, expect, it } from "vitest";

import {
  curriculumStagesPassedFill,
  extractBirthProgressTruth,
  formatBirthProgressHeadline,
  occupancyEnvelopeDominated,
  resolveManifestCalendarDays,
} from "@/lib/birth/birthProgressTruth";

describe("birthProgressTruth", () => {
  it("never calls 79.5% complete while a stage gate is open", () => {
    const headline = formatBirthProgressHeadline({
      progress_pct: 79.5,
      curriculum_index: 5,
      curriculum_total: 5,
      stage_pass_now: false,
      stage_blocker_metric: "oos_sharpe",
      progress_truth: {
        kind: "stage_index",
        stage_index: 5,
        stage_count: 5,
        stage_pass_now: false,
        blocker: "oos_sharpe",
        pct_is_not_complete: true,
      },
    });
    expect(headline.toLowerCase()).not.toContain("complete");
    expect(headline).toContain("Stage 5/5");
    expect(headline).toContain("not passed");
    expect(headline).toContain("oos sharpe");
  });

  it("prefers manifest actual_calendar_days over stale HUD days", () => {
    expect(
      resolveManifestCalendarDays({
        data_days_loaded: 91,
        data_manifest: { days_loaded: 91, actual_calendar_days: 366 },
        data_manifest_calendar_days: 366,
      }),
    ).toBe(366);
  });

  it("flags occupancy bought by the envelope as a lie", () => {
    expect(
      occupancyEnvelopeDominated({
        pass_reason: "foundation_fail:occupancy_envelope_dominated=0.93",
      }),
    ).toBe(true);
    expect(
      occupancyEnvelopeDominated({
        occupancy_exam_armed: true,
        envelope_override_fraction: 0.90,
        occupancy: 0.28,
      }),
    ).toBe(true);
    expect(
      occupancyEnvelopeDominated({
        occupancy_exam_armed: false,
        envelope_override_fraction: 0.9231,
        occupancy: 0.2477,
      }),
    ).toBe(false);
    expect(occupancyEnvelopeDominated({ pass_reason: "foundation_pass" })).toBe(false);
    expect(
      occupancyEnvelopeDominated({ envelope_override_fraction: 0.2, occupancy: 0.4 }),
    ).toBe(false);
  });

  it("fills the bar from stages passed, not theater 79.5%", () => {
    expect(
      curriculumStagesPassedFill({
        progress_pct: 79.5,
        curriculum_total: 5,
        stages_passed: ["stage1_trend", "stage2_range", "stage3_mixed", "stage4_viable_plant"],
        stage_pass_now: false,
      }),
    ).toBe(80);
  });

  it("does not paint passed when pass_reason is foundation_fail", () => {
    const truth = extractBirthProgressTruth({
      curriculum_index: 3,
      curriculum_total: 5,
      stage_pass_now: true,
      pass_reason: "foundation_fail:median_loss_r=None;replay_cap trades=2331 days=0",
      progress_truth: {
        stage_index: 3,
        stage_count: 5,
        stage_pass_now: true,
        blocker: null,
        pct_is_not_complete: true,
      },
    });
    expect(truth.stagePassNow).toBe(false);
    expect(truth.curriculumLabel.toLowerCase()).toContain("not passed");
  });

  it("does not paint freeze as passed even if foundation gate fields say so", () => {
    const truth = extractBirthProgressTruth({
      curriculum_index: 3,
      curriculum_total: 5,
      stage_pass_now: true,
      progress_truth: {
        stage_index: 3,
        stage_count: 5,
        stage_pass_now: true,
        blocker: null,
        pct_is_not_complete: true,
      },
      terminal_freeze: {
        schema: "terminal_freeze_v1",
        reason: "phoenix_cycle",
        resolved: false,
        next_action: "accept_champion_or_wipe",
      },
    });
    expect(truth.stagePassNow).toBe(false);
    expect(truth.curriculumLabel.toLowerCase()).toContain("not passed");
    expect(truth.curriculumLabel).toContain("phoenix");
  });

  it("treats engine progress_truth as SSOT for pass/fail", () => {
    const truth = extractBirthProgressTruth({
      progress_pct: 79.5,
      curriculum_index: 5,
      stage_pass_now: false,
      progress_truth: {
        stage_index: 5,
        stage_count: 5,
        stage_pass_now: false,
        pct_is_not_complete: true,
        blocker: "oos_sharpe",
      },
    });
    expect(truth.pctIsNotComplete).toBe(true);
    expect(truth.stagePassNow).toBe(false);
    expect(truth.curriculumLabel).toMatch(/not passed/);
  });
});
