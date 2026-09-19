import { describe, expect, it } from "vitest";

import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";
import {
  freezeRequiresOperatorFork,
  occupancyFencepostRetry,
  resolveStallPhysicsBlocker,
  stallFreezeNextActionLine,
} from "@/lib/birth/birthStallOverlay";

function progress(partial: Partial<BirthProgressPayload>): BirthProgressPayload {
  return partial;
}

function status(partial: Partial<BirthStatusPayload>): BirthStatusPayload {
  return { status: "stage_stalled", ...partial };
}

describe("resolveStallPhysicsBlocker", () => {
  it("prefers live occupancy over hollow None/days=0 pass_reason", () => {
    expect(
      resolveStallPhysicsBlocker(
        progress({
          occupancy: 0.24957,
          pass_reason:
            "foundation_fail:median_loss_r=None missing_or_gt_1.5;replay_cap trades=628 days=0",
          stage_blocker_metric: "median_loss_r",
          attention_summary:
            "Terminal freeze: phoenix_cycle — Twin/operator next_action=accept_champion_or_wipe",
        }),
      ),
    ).toBe("occupancy 24.96% (band 25–75%)");
  });

  it("keeps an honest pass_reason when process-R is present", () => {
    expect(
      resolveStallPhysicsBlocker(
        progress({
          occupancy: 0.24957,
          pass_reason: "occupancy=0.24957 not_in_25%-75%",
        }),
      ),
    ).toBe("occupancy=0.24957 not_in_25%-75%");
  });

  it("never uses attention_summary as the blocker", () => {
    const line = resolveStallPhysicsBlocker(
      progress({
        occupancy: 0.31,
        attention_summary: "Terminal freeze: phoenix_cycle",
        stage_blocker_metric: "occupancy",
      }),
    );
    expect(line).toContain("occupancy");
    expect(line).not.toContain("phoenix_cycle");
  });
});

describe("occupancyFencepostRetry", () => {
  it("is true for live 0.24996 unarmed exam even when freeze still says expand", () => {
    expect(
      occupancyFencepostRetry(
        status({
          progress: {
            occupancy: 0.2499578,
            occupancy_exam_armed: false,
            terminal_freeze: {
              schema: "terminal_freeze_v1",
              reason: "phoenix_cycle",
              resolved: false,
              next_action: "expand_data_or_accept_or_wipe",
            },
          },
        }),
      ),
    ).toBe(true);
  });

  it("is false once the exam window is armed", () => {
    expect(
      occupancyFencepostRetry(
        status({
          progress: {
            occupancy: 0.2499578,
            occupancy_exam_armed: true,
          },
        }),
      ),
    ).toBe(false);
  });
});

describe("freezeRequiresOperatorFork", () => {
  it("is true for unresolved phoenix freeze with accept_champion_or_wipe", () => {
    expect(
      freezeRequiresOperatorFork(
        status({
          progress: {
            swarm_rejected_no_lift: true,
            terminal_freeze: {
              schema: "terminal_freeze_v1",
              reason: "phoenix_cycle",
              resolved: false,
              next_action: "accept_champion_or_wipe",
            },
          },
        }),
      ),
    ).toBe(true);
  });

  it("is false for autonomous retry_stage even when swarm rejected", () => {
    expect(
      freezeRequiresOperatorFork(
        status({
          progress: {
            swarm_rejected_no_lift: true,
            occupancy: 0.24996,
            occupancy_exam_armed: false,
            terminal_freeze: {
              schema: "terminal_freeze_v1",
              reason: "phoenix_cycle",
              resolved: false,
              next_action: "retry_stage",
            },
          },
        }),
      ),
    ).toBe(false);
  });

  it("is false when freeze is resolved", () => {
    expect(
      freezeRequiresOperatorFork(
        status({
          progress: {
            terminal_freeze: {
              schema: "terminal_freeze_v1",
              reason: "phoenix_cycle",
              resolved: true,
              next_action: "accept_champion_or_wipe",
            },
          },
        }),
      ),
    ).toBe(false);
  });
});

describe("stallFreezeNextActionLine", () => {
  it("tells the operator to keep or wipe — not that autonomy will recover", () => {
    const line = stallFreezeNextActionLine(
      status({
        progress: {
          terminal_freeze: {
            schema: "terminal_freeze_v1",
            reason: "phoenix_cycle",
            resolved: false,
            next_action: "accept_champion_or_wipe",
          },
        },
      }),
    );
    expect(line.toLowerCase()).toContain("champion");
    expect(line.toLowerCase()).not.toContain("autonom");
  });

  it("tells the operator to retry the stage on occupancy fencepost", () => {
    const line = stallFreezeNextActionLine(
      status({
        progress: {
          occupancy: 0.24996,
          swarm_rejected_no_lift: true,
          terminal_freeze: {
            schema: "terminal_freeze_v1",
            reason: "phoenix_cycle",
            resolved: false,
            next_action: "retry_stage_or_wipe",
          },
        },
      }),
    );
    expect(line.toLowerCase()).toContain("retry");
    expect(line.toLowerCase()).toContain("wipe");
    expect(line.toLowerCase()).not.toContain("expand will unstick");
  });
});
