import { describe, expect, it } from "vitest";
import type { BirthProgressPayload } from "@/lib/birth/birthClientTypes";
import {
  CANONICAL_SWARM_NO_LIFT_REASON,
  LEGACY_SWARM_NO_LIFT_REASON,
  formatSwarmTournamentLiftLabel,
  isSwarmNoLiftReason,
  isSwarmRejectedNoLift,
  normalizeSwarmAttentionReason,
  preferTournamentProgressKeys,
  readSwarmTournamentAtStart,
  readSwarmTournamentLiftOk,
  rewriteVanityEdgeScoreLiftCopy,
  normalizeBirthStatusProgress,
} from "@/lib/birth/birthTournamentNaming";

describe("birthTournamentNaming (T12)", () => {
  it("normalizes legacy attention reason to tournament code", () => {
    expect(normalizeSwarmAttentionReason(LEGACY_SWARM_NO_LIFT_REASON)).toBe(
      CANONICAL_SWARM_NO_LIFT_REASON,
    );
    expect(normalizeSwarmAttentionReason(CANONICAL_SWARM_NO_LIFT_REASON)).toBe(
      CANONICAL_SWARM_NO_LIFT_REASON,
    );
    expect(normalizeSwarmAttentionReason("birth_interrupted")).toBe("birth_interrupted");
    expect(isSwarmNoLiftReason(LEGACY_SWARM_NO_LIFT_REASON)).toBe(true);
    expect(isSwarmNoLiftReason(CANONICAL_SWARM_NO_LIFT_REASON)).toBe(true);
    expect(isSwarmNoLiftReason("other")).toBe(false);
  });

  it("prefers tournament keys over legacy edgescore aliases", () => {
    const legacyOnly: BirthProgressPayload = {
      swarm_edgescore_lift_ok: true,
      swarm_edgescore_at_start: 0.42,
      attention_reason_code: LEGACY_SWARM_NO_LIFT_REASON,
      attention_summary: "Swarm tournament produced no EdgeScore lift",
    };
    const norm = preferTournamentProgressKeys(legacyOnly)!;
    expect(norm.swarm_tournament_lift_ok).toBe(true);
    expect(norm.swarm_tournament_at_start).toBe(0.42);
    expect(norm.attention_reason_code).toBe(CANONICAL_SWARM_NO_LIFT_REASON);
    expect(norm.attention_summary).toContain("no tournament lift");
    expect(norm.attention_summary?.toLowerCase()).not.toContain("edgescore lift");
  });

  it("does not overwrite primary tournament keys with legacy", () => {
    const dual: BirthProgressPayload = {
      swarm_tournament_lift_ok: false,
      swarm_tournament_at_start: 0.5,
      swarm_edgescore_lift_ok: true,
      swarm_edgescore_at_start: 0.1,
    };
    const norm = preferTournamentProgressKeys(dual)!;
    expect(norm.swarm_tournament_lift_ok).toBe(false);
    expect(norm.swarm_tournament_at_start).toBe(0.5);
  });

  it("reads lift ok / at start with alias fallback", () => {
    expect(readSwarmTournamentLiftOk({ swarm_edgescore_lift_ok: true })).toBe(true);
    expect(readSwarmTournamentLiftOk({ swarm_tournament_lift_ok: false })).toBe(false);
    expect(readSwarmTournamentAtStart({ swarm_edgescore_at_start: 0.33 })).toBe(0.33);
    expect(readSwarmTournamentAtStart({ swarm_tournament_at_start: 0.9 })).toBe(0.9);
    expect(readSwarmTournamentLiftOk(undefined)).toBeUndefined();
  });

  it("detects swarm reject from flags or reason code", () => {
    expect(isSwarmRejectedNoLift({ swarm_rejected_no_lift: true })).toBe(true);
    expect(
      isSwarmRejectedNoLift({ attention_reason_code: LEGACY_SWARM_NO_LIFT_REASON }),
    ).toBe(true);
    expect(isSwarmRejectedNoLift({ attention_reason_code: "other" })).toBe(false);
  });

  it("formats tournament lift labels without EdgeScore vanity", () => {
    const frozen = formatSwarmTournamentLiftLabel({
      swarm_rejected_no_lift: true,
      swarm_tournament_at_start: 0.41,
    });
    expect(frozen.value).toBe("no tournament lift");
    expect(frozen.hint.toLowerCase()).not.toContain("edgescore");
    expect(frozen.tone).toBe("warn");

    const ok = formatSwarmTournamentLiftLabel({ swarm_tournament_lift_ok: true });
    expect(ok.value).toBe("lift ok");
    expect(ok.tone).toBe("ok");

    const accepted = formatSwarmTournamentLiftLabel({ swarm_champion_accepted: true });
    expect(accepted.value).toBe("champion accepted");
  });

  it("rewrites vanity EdgeScore lift copy", () => {
    expect(rewriteVanityEdgeScoreLiftCopy("no EdgeScore lift")).toBe("no tournament lift");
    expect(rewriteVanityEdgeScoreLiftCopy("edgescore lift failed")).toBe(
      "tournament lift failed",
    );
  });

  it("normalizes birth status progress envelope", () => {
    const status = normalizeBirthStatusProgress({
      status: "running",
      progress: {
        swarm_edgescore_lift_ok: false,
        attention_reason_code: LEGACY_SWARM_NO_LIFT_REASON,
      },
    });
    expect(status.progress?.swarm_tournament_lift_ok).toBe(false);
    expect(status.progress?.attention_reason_code).toBe(CANONICAL_SWARM_NO_LIFT_REASON);
  });
});
