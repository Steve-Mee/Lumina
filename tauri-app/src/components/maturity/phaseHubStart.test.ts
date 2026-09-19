import { describe, expect, it } from "vitest";

import { followPhaseStart } from "@/components/maturity/phaseHubStart";
import type { MaturityHubPayload } from "@/lib/maturationClient";

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
        last_result: { ok: false, missing: ["evolution_proof_passed"] },
        exit_eval: { ok: false, missing: ["evolution_proof_passed"] },
      } as MaturityHubPayload,
    ];
    let index = 0;
    const result = await followPhaseStart(
      async () => hubs[Math.min(index++, hubs.length - 1)] as MaturityHubPayload,
      "awakening",
      { attempts: 5, delayMs: 1 },
    );
    expect(result.ok).toBe(false);
    expect(result.message).toContain("Evolution proof");
    expect(result.hub.focus_status).toBe("failed");
  });
});
