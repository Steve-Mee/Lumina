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
        title: "Credentials",
        status: "Secure operator access",
        tone: "cyan",
      };
    case "configuration":
      return {
        eyebrow: SETUP_EYEBROW,
        title: "Configuration",
        status: "Trading profile & risk envelope",
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
  interrupted: boolean;
  certificateFailed: boolean;
  stageStalledActive: boolean;
  milestones: BirthMilestone[];
  phaseSubtitle: string;
}

export function resolveBirthScreenPhaseHeader(
  input: BirthScreenPhaseInput,
): LuminaPhasePresentation {
  if (input.genesisMode) {
    return {
      eyebrow: "Birth Protocol",
      title: "Neural Genesis",
      status: input.activating
        ? "Activation sequence engaged"
        : input.interrupted
          ? "Birth gestopt — kies volgende actie"
          : "Awaiting activation",
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
      title: "Birth Certificate",
      status: input.phaseSubtitle,
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

  return {
    eyebrow: "Birth Phase",
    title: "Birth Protocol",
    status: input.phaseSubtitle,
    tone: "violet",
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
