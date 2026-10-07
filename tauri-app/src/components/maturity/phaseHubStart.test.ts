import { describe, expect, it } from "vitest";

import { followPhaseStart, livingClockPhase } from "@/components/maturity/phaseHubStart";
import type { MaturityHubPayload } from "@/lib/maturationClient";

describe("livingClockPhase", () => {
  it("returns the running living phase", () => {
    expect(livingClockPhase({ runner_active: true, active_phase: "awakening" })).toBe("awakening");
  });

  it("ignores an idle hub focus", () => {
    expect(livingClockPhase({ runner_active: false, active_phase: "awakening" })).toBeNull();
    expect(livingClockPhase({ runner_active: true, active_phase: "birth" })).toBeNull();
  });
});

describe("followPhaseStart", () => {
  it("waits until the runner idles then reports missing proofs", async () => {
    const hubs: MaturityHubPayload[] = [
      {
        runner_active: true,
        last_result: null,
        focus_status: "running",
      } as MaturityHubPayload,
      {
        runner_active: false,
        focus_status: "failed",
        last_result: { ok: false, missing: ["baseline_not_the_plant"] },
        exit_eval: { ok: false, missing: ["baseline_not_the_plant"] },
      } as MaturityHubPayload,
    ];
    let index = 0;
    const result = await followPhaseStart(
      async () => hubs[Math.min(index++, hubs.length - 1)] as MaturityHubPayload,
      "awakening",
      { attempts: 5, delayMs: 1 },
    );
    expect(result.ok).toBe(false);
    expect(result.message).toMatch(/Plant baseline/i);
    expect(result.hub.focus_status).toBe("failed");
  });
});
