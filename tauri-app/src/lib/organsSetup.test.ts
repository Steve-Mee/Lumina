import { describe, expect, it } from "vitest";

import type { OnboardingPayload } from "@/lib/onboardingSteps";
import { resolveSmartSetupView, type OrgansTruthV1 } from "@/lib/organsSetup";

function payloadWith(organs: OrgansTruthV1, extra?: Partial<OnboardingPayload>): OnboardingPayload {
  return {
    backend: { reachable: true, url: "http://127.0.0.1:8000" },
    setup_complete: false,
    skip_wizard: false,
    app_surface: "setup",
    birth: { status: "idle", artifacts_ok: false },
    intelligence: {
      ollama_installed: false,
      ollama_required: false,
      recommended_model_key: "qwen3.5-9b",
      recommended_ollama_tag: "qwen3.5:9b",
      recommended_model_present: false,
      recommended_provider: "vllm",
      hardware: { os_name: "Windows" },
      adaptive_intelligence: {},
      missing: ["ollama", "model:qwen3.5:9b"],
      organs_truth_v1: organs as unknown as Record<string, unknown>,
    },
    organs_truth_v1: organs as unknown as Record<string, unknown>,
    model_catalog: [
      {
        key: "qwen3.5-9b",
        display_name: "Qwen 9B",
        ollama_tag: "qwen3.5:9b",
        recommended_tier: "standard",
        parameter_size_b: 9,
        fits_hardware: true,
        is_recommended: true,
      },
    ],
    readiness: [],
    credentials: { missing: [], has_admin_api_key: true },
    required_steps: ["welcome", "birth"],
    wizard_steps: ["welcome", "birth"],
    step_status: {},
    defaults: {
      mode: "sim",
      sim: {},
      real: {},
      evolution: {},
      first_boot: {},
      risk_controller: {},
    },
    smart_setup_running: false,
    ...extra,
  };
}

const windowsOrgans: OrgansTruthV1 = {
  dto: "organs_truth_v1",
  lungs: {
    status: "ready",
    cuda_available: true,
    device_name: "RTX",
    human_status: "A graphics card is available. LUMINA will practise trades on it.",
    next_action: null,
  },
  voice: {
    status: "off",
    selected_provider: "off",
    allowed_providers: ["ollama", "grok_remote", "off"],
    blocked_providers: [
      {
        id: "vllm",
        reason_human:
          "This extra-fast local assistant only runs on Linux or WSL2. On this Windows PC we use Ollama or the cloud instead.",
      },
    ],
    human_status: "Thinking assistant is off.",
    next_action: null,
  },
  news: {
    workload: "voice",
    provider_preference: ["grok_remote", "ollama", "vllm"],
    can_run: false,
    order_path_coupled: false,
    human_status: "News reading is off until a thinking assistant is available. It never places or sizes orders.",
  },
  operator_choices: [
    {
      id: "ollama",
      visible: true,
      enabled: true,
      default: false,
      label: "Local assistant (Ollama)",
      help: "Ollama is a small local talking program. Safe to run next to learning.",
      consequence_if_yes: "We install Ollama and a tested model that fits this PC.",
      consequence_if_no: "Learn trades only.",
    },
    {
      id: "grok_remote",
      visible: true,
      enabled: true,
      default: false,
      label: "Cloud assistant (xAI)",
      help: "Cloud brain.",
      consequence_if_yes: "Uses an xAI key.",
      consequence_if_no: "Stay local or off.",
    },
    {
      id: "off",
      visible: true,
      enabled: true,
      default: true,
      label: "Off",
      help: "Learn trades only.",
      consequence_if_yes: "Learning to trade does not wait for the assistant.",
      consequence_if_no: "Pick an assistant later.",
    },
    {
      id: "vllm",
      visible: false,
      enabled: false,
      default: false,
      label: "Extra-fast local assistant (vLLM)",
      help: "Linux only.",
      consequence_if_yes: "HTTP only.",
      consequence_if_no: "Use Ollama.",
    },
  ],
  conflation_warnings: [],
  next_honest_steps: ["Learning to trade does not wait for the assistant."],
};

describe("resolveSmartSetupView", () => {
  it("exposes three card fields and keeps Continue enabled with Voice off", () => {
    const view = resolveSmartSetupView(payloadWith(windowsOrgans), "off");
    expect(view.lungsStatus.length).toBeGreaterThan(0);
    expect(view.voiceChoices.map((c) => c.id)).toEqual(["ollama", "grok_remote", "off"]);
    expect(view.nextSteps.join(" ")).toContain("Learning to trade does not wait for the assistant.");
    expect(view.continueEnabled).toBe(true);
    expect(view.showVllmOption).toBe(false);
  });

  it("hides vLLM on a Windows fixture even if recommended_provider is vllm", () => {
    const view = resolveSmartSetupView(payloadWith(windowsOrgans), "ollama");
    expect(view.showVllmOption).toBe(false);
    expect(view.voiceChoices.some((c) => c.id === "vllm")).toBe(false);
  });

  it("keeps the local model catalog visible when Ollama is selected", () => {
    const view = resolveSmartSetupView(payloadWith(windowsOrgans), "ollama");
    expect(view.showCatalog).toBe(true);
    expect(view.showInstall).toBe(true);
  });

  it("Off does not block Continue toward Genesis/Birth", () => {
    const view = resolveSmartSetupView(payloadWith(windowsOrgans), "off");
    expect(view.continueEnabled).toBe(true);
    expect(view.showInstall).toBe(false);
  });
});
