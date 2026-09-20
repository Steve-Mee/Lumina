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

  it("idle copy keeps same-exam prefer-better without a loading lie", () => {
    expect(
      awakeningMissionMessage({
        running: false,
        error: null,
        focusStatus: "incomplete",
        progressMessage: null,
        note: null,
      }),
    ).toMatch(/same exam/i);
    expect(
      awakeningMissionMessage({
        running: false,
        error: null,
        focusStatus: "incomplete",
        progressMessage: null,
        note: null,
      }),
    ).toMatch(/never train A/i);
  });

  it("keeps the live progress line while the clock is running", () => {
    const input = {
      running: true,
      progressMessage: "Awakening cycle 1/8 — train A, eval B",
      error: null,
      focusStatus: "running",
    };
    expect(awakeningHeaderStatus(input)).toContain("cycle 1/8");
    expect(awakeningMissionMessage(input)).toContain("train A");
  });
});
