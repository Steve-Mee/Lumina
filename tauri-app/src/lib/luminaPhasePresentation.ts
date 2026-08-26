import type { BirthMilestone } from "@/lib/birthPhaseModel";
import type { OnboardingStepId } from "@/lib/onboardingSteps";
import type { TradingMode } from "@/store/coreStore";

export type LuminaPhaseTone = "cyan" | "violet" | "emerald" | "amber" | "rose";

export interface LuminaPhasePresentation {
  eyebrow: string;
  title: string;
  status?: string;
  tone?: LuminaPhaseTone;
}

const SETUP_EYEBROW = "Lumina Setup";

export function resolveWizardPhaseHeader(
  step: OnboardingStepId,
  activating = false,
): LuminaPhasePresentation {
  switch (step) {
    case "welcome":
      return {
        eyebrow: SETUP_EYEBROW,
        title: "Welcome",
        status: "Begin Lumina installation",
        tone: "cyan",
      };
    case "backend":
      return {
        eyebrow: SETUP_EYEBROW,
        title: "Backend Connection",
        status: "Connect to LUMINA Core",
        tone: "cyan",
      };
    case "ollama":
    case "model":
      return {
        eyebrow: SETUP_EYEBROW,
        title: "Smart Setup",
        status: "Ollama & model intelligence",
        tone: "violet",
      };
    case "credentials":
      return {
        eyebrow: SETUP_EYEBROW,
        title: "Operator Vault",
        status: "Seal channels · await link",
        tone: "cyan",
      };
    case "configuration":
      return {
        eyebrow: SETUP_EYEBROW,
        title: "Risk Envelope",
        status: "Trading profile · capital first",
        tone: "cyan",
      };
    case "birth":
      return {
        eyebrow: "Birth Protocol",
        title: "Neural Genesis",
        status: activating ? "Activation sequence engaged" : "Maturity Charter",
        tone: "cyan",
      };
    default:
      return {
        eyebrow: SETUP_EYEBROW,
        title: "Setup",
        tone: "cyan",
      };
  }
}

export interface BirthScreenPhaseInput {
  genesisMode: boolean;
  missionMode: boolean;
  awakening: boolean;
  activating: boolean;
  /** Full launch shell (intent sticky). */
  launching?: boolean;
  /** Interrupted / paused — choose Continue or Start clean. */
  decisionMode?: boolean;
  /** Engine/activation attention without full stop (aligned with deck). */
  genesisAttention?: boolean;
  /** Override status from Genesis presentation SSOT when on deck. */
  genesisPhaseStatus?: string;
  genesisPhaseTone?: LuminaPhaseTone;
  interrupted: boolean;
  certificateFailed: boolean;
  certificateOverlayActive?: boolean;
  stageStalledActive: boolean;
  milestones: BirthMilestone[];
  phaseSubtitle: string;
}

export function resolveBirthScreenPhaseHeader(
  input: BirthScreenPhaseInput,
): LuminaPhasePresentation {
  // Launch wins over genesis/decision — never flash "paused" mid-activate.
  if (input.launching || input.activating) {
    return {
      eyebrow: "Birth Protocol",
      title: "Starting Birth",
      status: "Verifying systems — stay on this screen",
      tone: "cyan",
    };
  }

  if (input.awakening) {
    return {
      eyebrow: "Birth Phase",
      title: "Awakening",
      status: "Birth complete — organism ready for command deck",
      tone: "emerald",
    };
  }

  if (input.missionMode) {
    const active = input.milestones.find((m) => m.state === "active");
    return {
      eyebrow: "Birth Phase",
      title: active?.label ?? "Curriculum Training",
      status: input.phaseSubtitle,
      tone: "cyan",
    };
  }

  if (input.certificateFailed) {
    return {
      eyebrow: "Birth Protocol",
      title: "Certificate",
      status: input.certificateOverlayActive ? "Diagnostics below" : input.phaseSubtitle,
      tone: "rose",
    };
  }

  if (input.stageStalledActive) {
    return {
      eyebrow: "Birth Phase",
      title: "Curriculum Stalled",
      status: input.phaseSubtitle,
      tone: "amber",
    };
  }

  // Genesis deck SSOT — one header tone with the glass panel (no dual narrative).
  if (input.genesisMode && input.genesisPhaseStatus) {
    return {
      eyebrow: "Birth Protocol",
      title: "Neural Genesis",
      status: input.genesisPhaseStatus,
      tone: input.genesisPhaseTone ?? "cyan",
    };
  }

  if (input.decisionMode || (input.genesisMode && input.interrupted)) {
    return {
      eyebrow: "Birth Protocol",
      title: "Neural Genesis",
      status: "Birth stopped — choose next step",
      tone: "amber",
    };
  }

  if (input.genesisMode && input.genesisAttention) {
    return {
      eyebrow: "Birth Protocol",
      title: "Neural Genesis",
      status: "Birth needs attention — choose next step",
      tone: "amber",
    };
  }

  if (input.genesisMode) {
    return {
      eyebrow: "Birth Protocol",
      title: "Neural Genesis",
      status: "Awaiting activation",
      tone: "cyan",
    };
  }

  // Never orphan: fall back to genesis-style header, not empty protocol.
  return {
    eyebrow: "Birth Protocol",
    title: "Neural Genesis",
    status: input.phaseSubtitle || "Awaiting activation",
    tone: "cyan",
  };
}

export function resolveDeckPhaseHeader(mode: TradingMode): LuminaPhasePresentation {
  if (mode === "REAL") {
    return {
      eyebrow: "Command Deck",
      title: "REAL Operations",
      status: "Live capital — constitution enforced",
      tone: "rose",
    };
  }

  return {
    eyebrow: "Command Deck",
    title: "SIM Operations",
    status: "Simulation mode — no capital at risk",
    tone: "cyan",
  };
}
