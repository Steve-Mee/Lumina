import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  awakeningLifeLine,
  formatHeartbeatAge,
  heartbeatAgeMs,
  resolveAwakeningLifeState,
} from "@/lib/awakening/awakeningLife";

describe("awakeningLife", () => {
  it("treats a fresh heartbeat while running as live", () => {
    const now = Date.parse("2026-09-19T12:00:10Z");
    const updatedAt = "2026-09-19T12:00:08Z";
    expect(heartbeatAgeMs(updatedAt, now)).toBe(2000);
    expect(
      resolveAwakeningLifeState({
        running: true,
        updatedAt,
        nowMs: now,
      }),
    ).toBe("live");
  });

  it("does not fake life when the runner is idle", () => {
    expect(
      resolveAwakeningLifeState({
        running: false,
        updatedAt: "2026-09-19T12:00:08Z",
        nowMs: Date.parse("2026-09-19T12:00:10Z"),
      }),
    ).toBe("idle");
  });

  it("says computing when running but heartbeat is stale — not stuck", () => {
    expect(
      resolveAwakeningLifeState({
        running: true,
        updatedAt: "2026-09-19T12:00:00Z",
        nowMs: Date.parse("2026-09-19T12:01:00Z"),
      }),
    ).toBe("computing");
  });

  it("formats an honest First Watch activity line from real fields", () => {
    const line = awakeningLifeLine({
      running: true,
      activity: "eval_B",
      nB: 133,
      updatedAt: "2026-09-19T12:00:08Z",
      nowMs: Date.parse("2026-09-19T12:00:20Z"),
    });
    expect(line).toContain("First Watch");
    expect(line).toContain("eval B");
    expect(line).not.toMatch(/Cycle/);
    expect(line).toContain("133/500");
    expect(line).toContain("12s ago");
    expect(formatHeartbeatAge(4000)).toBe("just now");
  });

  it("names a leftover day-book walk by bars, not as PPO steps", () => {
    const line = awakeningLifeLine({
      running: true,
      activity: "probe_A",
      probeBars: 8192,
      nB: 500,
      updatedAt: "2026-10-06T04:00:00Z",
      nowMs: Date.parse("2026-10-06T04:01:00Z"),
    });
    expect(line).toContain("First Watch");
    expect(line).toContain("day book");
    expect(line).toContain("bar 8,192");
    expect(line).not.toContain("steps");
    expect(line).not.toMatch(/Cycle/);
  });

  it("life pulse does not embed the Birth helix (rings leaked over the cinematic)", () => {
    const src = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "../../components/maturity/AwakeningLifePulse.tsx"),
      "utf8",
    );
    expect(src).not.toContain("BirthOrganismVisual");
    expect(src).not.toContain("birth-organism");
  });
});
