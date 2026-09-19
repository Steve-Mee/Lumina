import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  apprenticeshipLifeLine,
  resolveApprenticeshipLifeState,
} from "@/lib/apprenticeship/apprenticeshipLife";

describe("apprenticeshipLife", () => {
  it("treats a fresh heartbeat while running as live", () => {
    const now = Date.parse("2026-09-19T12:00:10Z");
    expect(
      resolveApprenticeshipLifeState({
        running: true,
        updatedAt: "2026-09-19T12:00:08Z",
        nowMs: now,
      }),
    ).toBe("live");
  });

  it("does not fake life when the runner is idle", () => {
    expect(
      resolveApprenticeshipLifeState({
        running: false,
        updatedAt: "2026-09-19T12:00:08Z",
        nowMs: Date.parse("2026-09-19T12:00:10Z"),
      }),
    ).toBe("idle");
  });

  it("life line reports n_A and green days", () => {
    const line = apprenticeshipLifeLine({
      running: true,
      nA: 40,
      nD: 2,
      updatedAt: "2026-09-19T12:00:08Z",
      nowMs: Date.parse("2026-09-19T12:00:10Z"),
    });
    expect(line).toContain("n_A 40/150");
    expect(line).toContain("green 2/5");
  });

  it("pulse source does not embed BirthOrganismVisual", () => {
    const src = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "../../components/maturity/ApprenticeshipLifePulse.tsx"),
      "utf8",
    );
    expect(src).not.toContain("BirthOrganismVisual");
    expect(src).not.toContain("birth-organism");
  });
});
