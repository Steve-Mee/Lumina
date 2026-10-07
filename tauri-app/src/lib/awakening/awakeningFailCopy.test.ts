import { describe, expect, it } from "vitest";

import {
  awakeningHeaderStatus,
  awakeningMissionMessage,
  isAwakeningFailed,
} from "@/lib/awakening/awakeningFailCopy";

describe("awakeningFailCopy", () => {
  it("does not keep a loading line after the runner has died", () => {
    const input = {
      running: false,
      focusStatus: "failed",
      error:
        "[WinError 5] Toegang geweigerd: 'lumina_phase_continuum.json.tmp' -> 'lumina_phase_continuum.json'",
      progressMessage: "Loading frozen π* + Birth split",
    };
    expect(isAwakeningFailed(input)).toBe(true);
    expect(awakeningHeaderStatus(input)).toBe("Clock halted — fail-closed, Birth intact");
    expect(awakeningMissionMessage(input)).toContain("WinError 5");
    expect(awakeningMissionMessage(input)).not.toContain("Loading frozen");
  });

  it("does not treat a not-started Awakening as a failed exam", () => {
    const input = {
      running: false,
      passNow: false,
      focusStatus: "pending",
      error: null,
      progressMessage: null,
    };
    expect(isAwakeningFailed(input)).toBe(false);
    expect(awakeningHeaderStatus(input)).toBe("Not started — start Awakening from Phase Hub");
    expect(awakeningMissionMessage(input)).not.toMatch(/failed/i);
    expect(awakeningMissionMessage(input)).toMatch(/First Watch/i);
    expect(awakeningMissionMessage(input)).not.toMatch(/8 train/i);
    expect(awakeningMissionMessage(input)).not.toMatch(/keep-best/i);
  });

  it("keeps the live progress line while the clock is running", () => {
    const input = {
      running: true,
      progressMessage: "First Watch — eval frozen plant on holdout B (no learn)",
      error: null,
      focusStatus: "running",
    };
    expect(awakeningHeaderStatus(input)).toContain("First Watch");
    expect(awakeningMissionMessage(input)).toContain("no learn");
    expect(awakeningMissionMessage(input)).not.toMatch(/cycle 1\/8/i);
  });
});
