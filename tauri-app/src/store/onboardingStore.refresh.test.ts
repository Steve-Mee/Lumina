import { beforeEach, describe, expect, it, vi } from "vitest";

import { useOnboardingStore } from "@/store/onboardingStore";

vi.mock("@/lib/setupClient", () => ({
  fetchOnboardingStatus: vi.fn(),
  postConfigure: vi.fn(),
  postCredentials: vi.fn(),
  startBirth: vi.fn(),
  startSmartSetup: vi.fn(),
  fetchDeckCredentialsPrefill: vi.fn().mockResolvedValue({ credentials: {} }),
  fetchAndHydrateDeckApiKey: vi.fn().mockResolvedValue(true),
  isBirthStartSuccessful: vi.fn(),
}));

import { fetchOnboardingStatus } from "@/lib/setupClient";

const setupCompletePayload = {
  setup_complete: true,
  skip_wizard: false,
  app_surface: "birth" as const,
  wizard_steps: ["birth"],
  required_steps: ["birth"],
  step_status: {},
  birth: { status: "idle", artifacts_ok: false },
  credentials: { missing: [], has_admin_api_key: true, wizard_required: false },
  intelligence: {
    ollama_installed: true,
    ollama_required: true,
    recommended_model_key: "qwen",
    recommended_ollama_tag: "qwen3.5:4b",
    recommended_model_present: true,
    recommended_provider: "ollama",
    hardware: {},
    adaptive_intelligence: {},
    missing: [],
  },
  model_catalog: [],
  readiness: [],
  defaults: {
    mode: "sim",
    sim: {},
    real: {},
    evolution: {},
    first_boot: {},
    risk_controller: {},
  },
  smart_setup_running: false,
  backend: { reachable: true, url: "http://127.0.0.1:8000" },
} as const;

describe("onboardingStore.refresh", () => {
  beforeEach(() => {
    useOnboardingStore.setState({
      phase: "loading",
      payload: null,
      error: null,
      currentStepIndex: 0,
      activating: false,
      birthPhaseCommitted: false,
    });
    vi.mocked(fetchOnboardingStatus).mockReset();
  });

  it("T8 cold start fetch failure → wizard with no payload", async () => {
    vi.mocked(fetchOnboardingStatus).mockRejectedValue(new Error("Network error"));

    await useOnboardingStore.getState().refresh();

    const state = useOnboardingStore.getState();
    expect(state.phase).toBe("wizard");
    expect(state.payload).toBeNull();
    expect(state.error).toContain("Network error");
  });

  it("T8 mid-session fetch failure marks backend unreachable on cached payload", async () => {
    useOnboardingStore.setState({
      phase: "wizard",
      payload: {
        ...setupCompletePayload,
        app_surface: "setup",
        setup_complete: true,
      } as never,
    });
    vi.mocked(fetchOnboardingStatus).mockRejectedValue(new Error("Backend unreachable"));

    await useOnboardingStore.getState().refresh();

    const state = useOnboardingStore.getState();
    expect(state.phase).toBe("wizard");
    expect(state.payload?.backend.reachable).toBe(false);
    expect(state.payload?.backend.error).toContain("Backend unreachable");
    expect(state.payload?.setup_complete).toBe(true);
  });

  it("refresh failure preserves cockpit when last surface was deck", async () => {
    useOnboardingStore.setState({
      phase: "cockpit",
      payload: {
        ...setupCompletePayload,
        app_surface: "deck",
        skip_wizard: true,
        birth: { status: "completed", artifacts_ok: true },
      } as never,
    });
    vi.mocked(fetchOnboardingStatus).mockRejectedValue(new Error("Backend unreachable"));

    await useOnboardingStore.getState().refresh();

    const state = useOnboardingStore.getState();
    expect(state.phase).toBe("cockpit");
    expect(state.payload?.backend.reachable).toBe(false);
  });

  it("refresh failure preserves birth when last surface was birth", async () => {
    useOnboardingStore.setState({
      phase: "birth",
      payload: { ...setupCompletePayload } as never,
    });
    vi.mocked(fetchOnboardingStatus).mockRejectedValue(new Error("Backend unreachable"));

    await useOnboardingStore.getState().refresh();

    expect(useOnboardingStore.getState().phase).toBe("birth");
  });

  it("successful refresh maps app_surface to phase", async () => {
    vi.mocked(fetchOnboardingStatus).mockResolvedValue({
      ...setupCompletePayload,
      app_surface: "birth",
    } as never);

    await useOnboardingStore.getState().refresh();

    expect(useOnboardingStore.getState().phase).toBe("birth");
    expect(useOnboardingStore.getState().error).toBeNull();
  });
});
