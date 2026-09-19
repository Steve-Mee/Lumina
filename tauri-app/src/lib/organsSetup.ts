import type { OnboardingPayload } from "@/lib/onboardingSteps";

export type VoiceChoiceId = "ollama" | "grok_remote" | "vllm" | "off";

export interface OrgansBlockedProvider {
  id: string;
  reason_human: string;
}

export interface OrgansChoice {
  id: VoiceChoiceId | string;
  visible: boolean;
  enabled: boolean;
  default: boolean;
  label: string;
  help: string;
  consequence_if_yes: string;
  consequence_if_no: string;
}

export interface OrgansTruthV1 {
  dto?: string;
  schema?: string;
  lungs: {
    status: string;
    cuda_available: boolean;
    device_name: string | null;
    human_status: string;
    next_action: string | null;
  };
  voice: {
    status: string;
    selected_provider: VoiceChoiceId;
    allowed_providers: string[];
    blocked_providers: OrgansBlockedProvider[];
    human_status: string;
    next_action: string | null;
  };
  news: {
    workload: "voice";
    provider_preference: string[];
    can_run: boolean;
    order_path_coupled: false;
    human_status: string;
  };
  operator_choices: OrgansChoice[];
  conflation_warnings: string[];
  next_honest_steps: string[];
}

export const CUDA_GLOSS =
  "CUDA is the way an NVIDIA graphics card does heavy math. LUMINA uses it to practise trades.";
export const VLLM_GLOSS =
  "vLLM is an optional extra-fast talking server. It is not the thing that learns to trade.";
export const OLLAMA_GLOSS = "Ollama is a small local talking program. Safe to run next to learning.";
export const XAI_GLOSS =
  "Cloud brain. Best for reading live news. Needs a key. Does not learn trades by itself.";

const WINDOWS_VLLM_REASON =
  "This extra-fast local assistant only runs on Linux or WSL2. On this Windows PC we use Ollama or the cloud instead.";

export function organsFromPayload(payload: OnboardingPayload | null | undefined): OrgansTruthV1 | null {
  const raw = payload?.organs_truth_v1 ?? payload?.intelligence?.organs_truth_v1;
  if (!raw || typeof raw !== "object") return null;
  return raw as OrgansTruthV1;
}

export function isWindowsFixture(payload: OnboardingPayload | null | undefined): boolean {
  const organs = organsFromPayload(payload);
  if (organs?.voice.blocked_providers.some((item) => item.id === "vllm")) {
    const reason = organs.voice.blocked_providers.find((item) => item.id === "vllm")?.reason_human ?? "";
    if (reason.toLowerCase().includes("windows")) return true;
  }
  const osName = String(
    (payload?.intelligence?.hardware as { os_name?: string } | undefined)?.os_name ?? "",
  );
  return osName.toLowerCase().startsWith("win");
}

export interface SmartSetupView {
  lungsStatus: string;
  lungsNextAction: string | null;
  voiceChoices: OrgansChoice[];
  selectedVoice: VoiceChoiceId;
  showCatalog: boolean;
  showInstall: boolean;
  continueEnabled: boolean;
  showVllmOption: boolean;
  nextSteps: string[];
  newsStatus: string;
  forceHighHelp: string;
}

export function resolveSmartSetupView(
  payload: OnboardingPayload | null | undefined,
  selectedVoice: VoiceChoiceId,
): SmartSetupView {
  const organs = organsFromPayload(payload);
  const windows = isWindowsFixture(payload);
  const choices = (organs?.operator_choices ?? defaultChoices(windows, selectedVoice)).filter(
    (choice) => choice.visible && (!windows || choice.id !== "vllm"),
  );
  const showVllm = choices.some((choice) => choice.id === "vllm");
  const voice = selectedVoice;
  const showCatalog = voice === "ollama";
  const ollamaMissing = Boolean(payload?.intelligence.missing.includes("ollama"));
  const modelMissing = Boolean(payload?.intelligence.missing.some((item) => item.startsWith("model:")));
  const showInstall = voice === "ollama" && (ollamaMissing || modelMissing || !payload?.intelligence.recommended_model_present);
  return {
    lungsStatus:
      organs?.lungs.human_status ??
      "The training engine is detected on this PC. LUMINA practises trades here — not with a chatbot.",
    lungsNextAction: organs?.lungs.next_action ?? null,
    voiceChoices: choices,
    selectedVoice: voice,
    showCatalog,
    showInstall,
    continueEnabled: true,
    showVllmOption: showVllm && !windows,
    nextSteps: organs?.next_honest_steps ?? [
      "Learning to trade does not wait for the assistant.",
      "Next: finish Setup, then Genesis / Birth. Voice can stay off.",
    ],
    newsStatus:
      organs?.news.human_status ??
      "News reading uses the thinking assistant (cloud first). It never places or sizes orders.",
    forceHighHelp:
      "Force high tier only picks a larger local talking model if memory allows. It never unlocks REAL trading and never installs vLLM on Windows. May be slow.",
  };
}

function defaultChoices(windows: boolean, selected: VoiceChoiceId): OrgansChoice[] {
  return [
    {
      id: "ollama",
      visible: true,
      enabled: true,
      default: selected === "ollama",
      label: "Local assistant (Ollama)",
      help: `${OLLAMA_GLOSS} Needed later for news headlines and questions. Not needed to start learning.`,
      consequence_if_yes: "We install Ollama and a tested model that fits this PC.",
      consequence_if_no: "You can use the cloud assistant or learn trades only.",
    },
    {
      id: "grok_remote",
      visible: true,
      enabled: true,
      default: selected === "grok_remote",
      label: "Cloud assistant (xAI)",
      help: `${XAI_GLOSS} LUMINA asks a cloud brain when it must read the live web (news, X).`,
      consequence_if_yes: "LUMINA uses an xAI key. No local GPU memory for talking.",
      consequence_if_no: "Stay on a local assistant or turn talking off.",
    },
    {
      id: "off",
      visible: true,
      enabled: true,
      default: selected === "off",
      label: "Off",
      help: "Learn trades only. You can add an assistant later. News reading stays off.",
      consequence_if_yes: "Learning to trade does not wait for the assistant.",
      consequence_if_no: "Pick a local or cloud assistant when you want explanations or news.",
    },
    {
      id: "vllm",
      visible: !windows,
      enabled: !windows,
      default: selected === "vllm",
      label: "Extra-fast local assistant (vLLM)",
      help: `${VLLM_GLOSS} Only on Linux/WSL2. Own installation. Does not replace the learning engine.`,
      consequence_if_yes: "LUMINA talks HTTP to a separate vLLM server.",
      consequence_if_no: "Use Ollama or the cloud instead.",
    },
  ];
}

export function windowsVllmReason(): string {
  return WINDOWS_VLLM_REASON;
}
