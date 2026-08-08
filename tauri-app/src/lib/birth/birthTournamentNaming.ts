/**
 * T12 / Seal II — tournament physics naming parity for Tauri.
 *
 * Backend dual-writes swarm_tournament_* (primary) + swarm_edgescore_* (legacy).
 * Stage "EdgeScore" pass criteria stay named EdgeScore; only swarm *lift* vanity
 * uses tournament language.
 */

import type { BirthProgressPayload } from "@/lib/birth/birthClientTypes";

export const CANONICAL_SWARM_NO_LIFT_REASON = "swarm_no_tournament_lift";
export const LEGACY_SWARM_NO_LIFT_REASON = "swarm_no_edgescore_lift";

/** Map legacy edgescore vanity reason codes to tournament physics names. */
export function normalizeSwarmAttentionReason(code: string | null | undefined): string {
  const c = String(code ?? "").trim();
  if (c === LEGACY_SWARM_NO_LIFT_REASON) {
    return CANONICAL_SWARM_NO_LIFT_REASON;
  }
  return c;
}

export function isSwarmNoLiftReason(code: string | null | undefined): boolean {
  const c = String(code ?? "").trim();
  return c === CANONICAL_SWARM_NO_LIFT_REASON || c === LEGACY_SWARM_NO_LIFT_REASON;
}

/** Prefer tournament_* over legacy edgescore_*; normalize attention reason codes. */
export function preferTournamentProgressKeys(
  progress: BirthProgressPayload | null | undefined,
): BirthProgressPayload | undefined {
  if (!progress) {
    return undefined;
  }
  const out: BirthProgressPayload = { ...progress };

  if (out.swarm_tournament_lift_ok === undefined && out.swarm_edgescore_lift_ok !== undefined) {
    out.swarm_tournament_lift_ok = Boolean(out.swarm_edgescore_lift_ok);
  }
  if (out.swarm_tournament_at_start === undefined && out.swarm_edgescore_at_start !== undefined) {
    out.swarm_tournament_at_start = Number(out.swarm_edgescore_at_start);
  }
  if (out.attention_reason_code) {
    out.attention_reason_code = normalizeSwarmAttentionReason(out.attention_reason_code);
  }

  // Operator-facing copy: never show "EdgeScore lift" for swarm physics.
  if (out.attention_summary) {
    out.attention_summary = rewriteVanityEdgeScoreLiftCopy(out.attention_summary);
  }

  return out;
}

/** Rewrite residual vanity "EdgeScore lift" phrases in operator copy. */
export function rewriteVanityEdgeScoreLiftCopy(text: string): string {
  return String(text ?? "")
    .replace(/no EdgeScore lift/gi, "no tournament lift")
    .replace(/EdgeScore lift/gi, "tournament lift")
    .replace(/edgescore lift/gi, "tournament lift");
}

export function readSwarmTournamentLiftOk(
  progress: BirthProgressPayload | null | undefined,
): boolean | undefined {
  if (!progress) return undefined;
  if (progress.swarm_tournament_lift_ok !== undefined) {
    return Boolean(progress.swarm_tournament_lift_ok);
  }
  if (progress.swarm_edgescore_lift_ok !== undefined) {
    return Boolean(progress.swarm_edgescore_lift_ok);
  }
  return undefined;
}

export function readSwarmTournamentAtStart(
  progress: BirthProgressPayload | null | undefined,
): number | undefined {
  if (!progress) return undefined;
  if (progress.swarm_tournament_at_start != null && Number.isFinite(Number(progress.swarm_tournament_at_start))) {
    return Number(progress.swarm_tournament_at_start);
  }
  if (progress.swarm_edgescore_at_start != null && Number.isFinite(Number(progress.swarm_edgescore_at_start))) {
    return Number(progress.swarm_edgescore_at_start);
  }
  return undefined;
}

export function isSwarmRejectedNoLift(
  progress: BirthProgressPayload | null | undefined,
): boolean {
  if (!progress) return false;
  return Boolean(
    progress.swarm_rejected_no_lift ||
      progress.policy_swarm_rejected_no_lift ||
      isSwarmNoLiftReason(progress.attention_reason_code),
  );
}

export function isSwarmChampionAccepted(
  progress: BirthProgressPayload | null | undefined,
): boolean {
  if (!progress) return false;
  return Boolean(
    progress.swarm_champion_accepted || progress.policy_swarm_champion_accepted,
  );
}

/** Compact HUD label for tournament lift state (not stage EdgeScore). */
export function formatSwarmTournamentLiftLabel(
  progress: BirthProgressPayload | null | undefined,
): { value: string; hint: string; tone: "ok" | "warn" | "danger" | "default" } {
  const rejected = isSwarmRejectedNoLift(progress);
  const accepted = isSwarmChampionAccepted(progress);
  const liftOk = readSwarmTournamentLiftOk(progress);
  const atStart = readSwarmTournamentAtStart(progress);
  const atStartLabel =
    atStart != null && Number.isFinite(atStart) ? atStart.toFixed(3) : null;

  if (accepted) {
    return {
      value: "champion accepted",
      hint: atStartLabel ? `baseline ${atStartLabel}` : "operator accepted frozen champion",
      tone: "ok",
    };
  }
  if (rejected) {
    return {
      value: "no tournament lift",
      hint: "champion frozen — accept or wipe",
      tone: "warn",
    };
  }
  if (liftOk === true) {
    return {
      value: "lift ok",
      hint: atStartLabel ? `baseline ${atStartLabel}` : "swarm tournament improved score",
      tone: "ok",
    };
  }
  if (liftOk === false) {
    return {
      value: "no lift",
      hint: atStartLabel ? `baseline ${atStartLabel}` : "awaiting swarm resolution",
      tone: "default",
    };
  }
  if (progress?.policy_swarm_active) {
    return {
      value: "running",
      hint: "policy swarm tournament in progress",
      tone: "default",
    };
  }
  return {
    value: "—",
    hint: "swarm tournament not active",
    tone: "default",
  };
}

/** Normalize full birth status progress for UI consumers. */
export function normalizeBirthStatusProgress<T extends { progress?: BirthProgressPayload }>(
  status: T,
): T {
  if (!status?.progress) {
    return status;
  }
  return {
    ...status,
    progress: preferTournamentProgressKeys(status.progress),
  };
}
