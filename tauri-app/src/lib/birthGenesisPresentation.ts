/**
 * Genesis deck presentation SSOT — one surface, one tone, one primary CTA.
 * Operator language only; raw Python/trace stays technical detail (optional).
 *
 * Clean idle / post-wipe (status.message = "Birth Phase nog niet gestart") is NOT
 * attention — never flash Retry / Recovery / dual banners after a full wipe.
 */

import {
  shouldHideActivateForDecision,
  shouldShowDecisionBanner,
} from "@/lib/birthOperatorMode";

export type GenesisBannerTone = "info" | "warn";
export type GenesisCtaMode = "activate" | "decision" | "retry" | "locked";

export interface GenesisDeckPresentationInput {
  activating: boolean;
  sessionInterrupted: boolean;
  checkpointAvailable: boolean;
  resumePlateauRisk?: boolean;
  decisionMode?: boolean;
  sessionProbePending?: boolean;
  sessionProbeError?: boolean;
  engineLive?: boolean;
  /** Onboarding / activation error */
  error?: string | null;
  /** Birth store poll error */
  pollError?: string | null;
  /** Backend status.message / status.error */
  statusMessage?: string | null;
  statusError?: string | null;
}

export interface GenesisDeckPresentation {
  /** Mono toolbar under Neural Genesis title */
  toolbarSubtitle: string;
  banner: {
    tone: GenesisBannerTone;
    title: string;
    body: string;
  };
  /** Optional mono detail under banner (sanitized operator line + optional technical) */
  detail: {
    operatorLine: string;
    technicalLine: string | null;
  } | null;
  ctaMode: GenesisCtaMode;
  ctaHint: string;
  /** Phase header status when on genesis (aligned with deck) */
  phaseStatus: string;
  phaseTone: "cyan" | "amber";
  /** BIRTH chip state */
  birthChipState: "ok" | "warn";
  showStartCleanSecondary: boolean;
  /** True only for real residual / activation failures — never clean idle. */
  hasAttention: boolean;
  /**
   * Recovery tab: prior session to clear/stop, or real attention that may need full wipe.
   * Never after a clean post-wipe idle.
   */
  showRecoveryTab: boolean;
  /**
   * Land operator on Recovery (not Charter) for decision / real attention.
   * Charter stays reviewable; actions live under Recovery.
   */
  preferRecoveryTab: boolean;
}

const INTERNAL_ERROR_OPERATOR =
  "Birth engine hit an internal error. Retry activation, or start clean if the run is corrupt.";

const TRACE_OR_EXCEPTION =
  /\b(UnboundLocalError|Traceback|Exception|Error:|TypeError|ValueError|RuntimeError|KeyError|AttributeError|NameError|ImportError|cannot access local variable|File \"|line \d+)\b/i;

/**
 * Backend idle / post-wipe status.message is informational, not a failure.
 * Treating it as attention causes Retry + Recovery + dual banners after wipe.
 */
export function isBenignBirthStatusMessage(raw: string | null | undefined): boolean {
  const text = String(raw ?? "").trim();
  if (!text) {
    return true;
  }
  const t = text.toLowerCase();
  return (
    /nog niet gestart/.test(t) ||
    /^not[_\s-]?started\.?$/.test(t) ||
    t === "idle" ||
    t === "wiped" ||
    /ready for (a )?clean start/.test(t) ||
    /geen birth-data gevonden/.test(t) ||
    /all birth data wiped/.test(t) ||
    /awaiting activation/.test(t) ||
    /maturity charter/.test(t)
  );
}

/** Map raw backend/engine text to operator-facing copy. */
export function sanitizeBirthOperatorMessage(raw: string | null | undefined): {
  operator: string;
  technical: string | null;
} {
  const text = String(raw ?? "").trim();
  if (!text || isBenignBirthStatusMessage(text)) {
    return { operator: "", technical: null };
  }

  if (TRACE_OR_EXCEPTION.test(text)) {
    // Keep a short technical fingerprint for support, not the full stack.
    const firstLine = text.split(/\r?\n/)[0]?.trim() ?? text;
    const technical =
      firstLine.length > 160 ? `${firstLine.slice(0, 157)}…` : firstLine;
    return { operator: INTERNAL_ERROR_OPERATOR, technical };
  }

  // Fabric / history operator messages already human — pass through, cap length.
  const operator = text.length > 280 ? `${text.slice(0, 277)}…` : text;
  return { operator, technical: null };
}

function pickRawAttention(input: GenesisDeckPresentationInput): string {
  const hard =
    String(input.error ?? "").trim() ||
    String(input.pollError ?? "").trim() ||
    String(input.statusError ?? "").trim();
  if (hard) {
    return hard;
  }
  // status.message is often idle copy ("Birth Phase nog niet gestart") — only real issues.
  const soft = String(input.statusMessage ?? "").trim();
  if (!soft || isBenignBirthStatusMessage(soft)) {
    return "";
  }
  return soft;
}

export function resolveGenesisDeckPresentation(
  input: GenesisDeckPresentationInput,
): GenesisDeckPresentation {
  const probePending = Boolean(input.sessionProbePending);
  const probeError = Boolean(input.sessionProbeError);
  const interrupted = Boolean(input.sessionInterrupted);
  const checkpoint = Boolean(input.checkpointAvailable);
  const plateau = Boolean(input.resumePlateauRisk);
  const activating = Boolean(input.activating);
  const engineLive = Boolean(input.engineLive);

  const raw = pickRawAttention(input);
  const sanitized = sanitizeBirthOperatorMessage(raw);
  const hasAttention = Boolean(sanitized.operator) && !activating;

  const hideActivate = shouldHideActivateForDecision({
    sessionInterrupted: interrupted,
    checkpointAvailable: checkpoint,
    activating,
    sessionProbePending: probePending,
    engineLive,
  });

  const decisionBanner = shouldShowDecisionBanner({
    sessionInterrupted: interrupted,
    checkpointAvailable: checkpoint,
    resumePlateauRisk: plateau,
  });

  // --- CTA mode ---
  let ctaMode: GenesisCtaMode = "activate";
  if (probePending || probeError) {
    ctaMode = "locked";
  } else if (hideActivate) {
    ctaMode = "decision";
  } else if (hasAttention) {
    // Real residual / activation failure — Retry (same path as Activate).
    ctaMode = "retry";
  }
  // decisionMode alone without interrupt/checkpoint is NOT retry (clean idle after wipe).

  // --- Toolbar + phase ---
  let toolbarSubtitle = "Maturity charter · awaiting activation";
  let phaseStatus = "Awaiting activation";
  let phaseTone: "cyan" | "amber" = "cyan";
  let birthChipState: "ok" | "warn" = engineLive ? "warn" : "ok";

  if (activating) {
    toolbarSubtitle = "Maturity charter · activation in progress";
    phaseStatus = "Verifying systems — stay on this screen";
    phaseTone = "cyan";
    birthChipState = "warn";
  } else if (probePending) {
    toolbarSubtitle = "Maturity charter · loading session";
    phaseStatus = "Loading previous birth session";
    phaseTone = "cyan";
  } else if (probeError) {
    toolbarSubtitle = "Maturity charter · session status unavailable";
    phaseStatus = "Session status unavailable — retry";
    phaseTone = "amber";
    birthChipState = "warn";
  } else if (ctaMode === "decision" || decisionBanner) {
    toolbarSubtitle = "Maturity charter · choose next step";
    phaseStatus = "Birth stopped — choose next step";
    phaseTone = "amber";
    birthChipState = "warn";
  } else if (ctaMode === "retry" || hasAttention) {
    toolbarSubtitle = "Maturity charter · needs attention";
    phaseStatus = "Birth needs attention — choose next step";
    phaseTone = "amber";
    birthChipState = "warn";
  }

  // --- Banner ---
  let banner: GenesisDeckPresentation["banner"];
  if (probePending) {
    banner = {
      tone: "info",
      title: "Loading session state:",
      body: "Checking for a previous birth (checkpoint / interrupted run). Activate stays locked until this finishes.",
    };
  } else if (probeError) {
    banner = {
      tone: "warn",
      title: "Session status unavailable:",
      body: "Could not confirm whether a previous birth is waiting. Retry status so you do not overwrite a checkpoint by accident.",
    };
  } else if (decisionBanner && !activating) {
    banner = {
      tone: "warn",
      title: "Birth stopped — open Recovery:",
      body: checkpoint
        ? "A checkpoint is waiting. Use the Recovery tab for Continue or Start clean — one primary path."
        : "No resumable checkpoint. Use the Recovery tab to Start clean (charter stays reviewable).",
    };
  } else if (hasAttention) {
    banner = {
      tone: "warn",
      title: "Birth needs attention — open Recovery:",
      body: "Retry or clear the prior run from the Recovery tab. Full wipe (tick cache) stays there too.",
    };
  } else {
    banner = {
      tone: "info",
      title: "What we need from you:",
      body: "Review the auto charter, set data policy, then activate birth. Training size is computed for this install — Birth pass is process-R, not a WR slider.",
    };
  }

  // --- Detail ---
  // Recovery tab owns the operator story for decision mode (never dual banner + callout).
  // Charter only shows detail for real engine errors when Recovery is not the decision surface.
  let detail: GenesisDeckPresentation["detail"] = null;
  const decisionSurface =
    ctaMode === "decision" || decisionBanner || Boolean(input.decisionMode);
  if (hasAttention && sanitized.operator && !decisionSurface) {
    detail = {
      operatorLine: sanitized.operator,
      technicalLine: sanitized.technical,
    };
  }

  // Recovery only when there is something to clear/stop/complete — not clean post-wipe idle.
  const showRecoveryTab =
    !activating &&
    !probePending &&
    (checkpoint ||
      plateau ||
      engineLive ||
      interrupted ||
      Boolean(input.decisionMode) ||
      ctaMode === "decision" ||
      decisionBanner ||
      hasAttention ||
      ctaMode === "retry");

  const preferRecoveryTab =
    showRecoveryTab &&
    !activating &&
    (decisionSurface || ctaMode === "retry" || hasAttention || plateau || engineLive);

  // CTA hints — decision/retry actions live under Recovery (no footer button thrash).
  let ctaHint = "Hold to arm the ring · birth engine idle is normal before activate";
  if (ctaMode === "locked") {
    ctaHint = "Activate locked until session status loads · prevents accidental overwrite";
  } else if (preferRecoveryTab && (ctaMode === "decision" || decisionBanner)) {
    ctaHint = "Decision actions live under the Recovery tab";
  } else if (ctaMode === "retry" && showRecoveryTab) {
    ctaHint = "Retry below · or clear prior run under Recovery";
  } else if (ctaMode === "retry") {
    ctaHint = "Retry uses the same activation path";
  }

  // Secondary Start clean under Activate only when Recovery tab is hidden.
  const showStartCleanSecondary =
    !activating &&
    !probePending &&
    !showRecoveryTab &&
    (ctaMode === "retry" || hasAttention);

  return {
    toolbarSubtitle,
    banner,
    detail,
    ctaMode,
    ctaHint,
    phaseStatus,
    phaseTone,
    birthChipState,
    showStartCleanSecondary,
    hasAttention,
    showRecoveryTab,
    preferRecoveryTab,
  };
}
