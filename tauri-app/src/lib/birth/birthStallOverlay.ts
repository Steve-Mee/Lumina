import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";

import { isUnresolvedTerminalFreeze } from "@/lib/birth/birthFreeze";

/**
 * Operator stall card: one physics blocker, never the freeze sentence as blocker.
 * Hollow pass_reason (None / days=0) is a write bug — do not show it.
 */
export function resolveStallPhysicsBlocker(
  progress: BirthProgressPayload | null | undefined,
): string {
  if (!progress) {
    return "";
  }
  const occupancy = Number(progress.occupancy);
  const occupancyLine = Number.isFinite(occupancy)
    ? `occupancy ${(occupancy * 100).toFixed(2)}% (band 25–75%)`
    : "";
  const pass = String(progress.pass_reason ?? "").trim();
  const hollow = /None|days\s*=\s*0/i.test(pass);
  if (pass && !hollow) {
    return pass;
  }
  if (occupancyLine) {
    return occupancyLine;
  }
  return String(progress.stage_blocker_metric ?? "").trim().replace(/_/g, " ");
}

/** Live 0.24996 chatter: unarmed exam pinned just under 25%. Expand cannot fix it. */
export function occupancyFencepostRetry(
  status: BirthStatusPayload | null | undefined,
): boolean {
  if (!isUnresolvedTerminalFreeze(status)) {
    return false;
  }
  const progress = status?.progress;
  if (!progress) {
    return false;
  }
  const next = String(progress.terminal_freeze?.next_action ?? "").toLowerCase();
  if (next.includes("retry_stage")) {
    return true;
  }
  if (progress.occupancy_exam_armed === true) {
    return false;
  }
  const occupancy = Number(progress.occupancy);
  if (!Number.isFinite(occupancy)) {
    return false;
  }
  return occupancy >= 0.24 && occupancy < 0.25;
}

/** Unresolved freeze whose next_action is accept/wipe — operator fork, not autonomy theater. */
export function freezeRequiresOperatorFork(
  status: BirthStatusPayload | null | undefined,
): boolean {
  if (!isUnresolvedTerminalFreeze(status)) {
    return false;
  }
  const next = String(status?.progress?.terminal_freeze?.next_action ?? "").toLowerCase();
  // Autonomous sample reset — not an operator fork, even if swarm rejected.
  if (next === "retry_stage") {
    return false;
  }
  if (next.includes("accept") || next.includes("wipe")) {
    return true;
  }
  return Boolean(status?.progress?.swarm_rejected_no_lift);
}

export function stallFreezeNextActionLine(
  status: BirthStatusPayload | null | undefined,
): string {
  if (!freezeRequiresOperatorFork(status)) {
    return "";
  }
  const next = String(status?.progress?.terminal_freeze?.next_action ?? "").trim();
  if (occupancyFencepostRetry(status) || next.includes("retry_stage")) {
    return "Occupancy fencepost — retry this stage (reset poisoned sample) or wipe. Expand will not unstick 25% chatter.";
  }
  if (next.includes("accept")) {
    return "Twin/operator: keep the frozen champion or wipe. Training will not resume until you choose.";
  }
  return "Operator fork required — expand is closed. Wipe or review genesis.";
}
