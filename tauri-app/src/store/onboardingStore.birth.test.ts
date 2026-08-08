import { beforeEach, describe, expect, it, vi } from "vitest";

import { useBirthStore } from "@/store/birthStore";
import { useOnboardingStore } from "@/store/onboardingStore";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock("@/lib/setupClient", () => ({
  fetchOnboardingStatus: vi.fn(),
  postConfigure: vi.fn(),
  postCredentials: vi.fn(),
  startSmartSetup: vi.fn(),
  fetchDeckCredentialsPrefill: vi.fn(),
  fetchAndHydrateDeckApiKey: vi.fn().mockResolvedValue(true),
  fetchFabricLinkStatus: vi.fn(),
}));

vi.mock("@/lib/birthClient", () => ({
  startBirth: vi.fn(),
  isBirthStartSuccessful: (status: string) =>
    status === "started" || status === "already_running",
}));

import { fetchFabricLinkStatus, fetchOnboardingStatus, postConfigure } from "@/lib/setupClient";
import { startBirth } from "@/lib/birthClient";
import { toast } from "sonner";

const basePayload = {
  setup_complete: true,
  skip_wizard: false,
  app_surface: "birth" as const,
  wizard_steps: ["birth"],
  required_steps: ["birth"],
  step_status: {},
  birth: { status: "idle", artifacts_ok: false },
  credentials: { wizard_required: false },
  defaults: { first_boot: {} },
  intelligence: {},
  model_catalog: [],
  smart_setup_running: false,
  backend: { reachable: true, url: "http://127.0.0.1:8000" },
} as never;

describe("onboardingStore.activateBirth", () => {
  beforeEach(() => {
    useOnboardingStore.setState({
      phase: "wizard",
      payload: basePayload,
      draft: useOnboardingStore.getState().draft,
      error: null,
      activating: false,
      birthPhaseCommitted: false,
    });
    useBirthStore.setState({ targetTrades: 25000 });
    vi.mocked(postConfigure).mockReset();
    vi.mocked(startBirth).mockReset();
    vi.mocked(fetchOnboardingStatus).mockReset();
    vi.mocked(fetchFabricLinkStatus).mockReset();
    vi.mocked(toast.error).mockReset();
    vi.mocked(toast.info).mockReset();
    vi.mocked(fetchOnboardingStatus).mockResolvedValue(basePayload);
    vi.mocked(fetchFabricLinkStatus).mockResolvedValue({
      green: true,
      reason: "ok",
      certificate: null,
      halt: null,
    });
    vi.spyOn(useBirthStore.getState(), "poll").mockResolvedValue(undefined as never);
    vi.spyOn(useBirthStore.getState(), "beginBirthRun").mockImplementation(() => undefined);
  });

  it("starts birth immediately when setup is already complete (no re-configure)", async () => {
    vi.mocked(postConfigure).mockResolvedValue({ success: true, steps: [] });
    vi.mocked(startBirth).mockResolvedValue({
      status: "started",
      message: "Birth Phase started in background",
    });

    const ok = await useOnboardingStore.getState().activateBirth();

    expect(ok).toBe(true);
    // Re-configure blocked the start chain; skip when setup_complete.
    expect(postConfigure).not.toHaveBeenCalled();
    expect(startBirth).toHaveBeenCalledWith(25000);
    expect(useOnboardingStore.getState().phase).toBe("birth");
    expect(useOnboardingStore.getState().birthPhaseCommitted).toBe(true);
  });

  it("persists genesis settings when setup is incomplete", async () => {
    useOnboardingStore.setState({
      payload: { ...basePayload, setup_complete: false } as never,
    });
    vi.mocked(postConfigure).mockResolvedValue({ success: true, steps: [] });
    vi.mocked(startBirth).mockResolvedValue({
      status: "started",
      message: "Birth Phase started in background",
    });

    const ok = await useOnboardingStore.getState().activateBirth();

    expect(ok).toBe(true);
    expect(postConfigure).toHaveBeenCalledTimes(1);
    expect(startBirth).toHaveBeenCalledWith(25000);
  });

  it("surfaces configure failures instead of failing silently", async () => {
    useOnboardingStore.setState({
      payload: { ...basePayload, setup_complete: false } as never,
    });
    vi.mocked(postConfigure).mockResolvedValue({
      success: false,
      steps: [{ success: false, step: "config_update", message: "Config write failed" }],
    });

    const ok = await useOnboardingStore.getState().activateBirth();

    expect(ok).toBe(false);
    expect(startBirth).not.toHaveBeenCalled();
    expect(useOnboardingStore.getState().phase).toBe("wizard");
    expect(useOnboardingStore.getState().birthPhaseCommitted).toBe(false);
    expect(useOnboardingStore.getState().error).toContain("Config write failed");
    expect(toast.error).toHaveBeenCalled();
  });

  it("stays on wizard when backend rejects start", async () => {
    vi.mocked(postConfigure).mockResolvedValue({ success: true, steps: [] });
    vi.mocked(startBirth).mockResolvedValue({
      status: "rejected",
      message: "Historische data niet beschikbaar",
    });

    const ok = await useOnboardingStore.getState().activateBirth();

    expect(ok).toBe(false);
    expect(useOnboardingStore.getState().phase).toBe("wizard");
    expect(useOnboardingStore.getState().birthPhaseCommitted).toBe(false);
    expect(useOnboardingStore.getState().error).toContain("Historische data");
    expect(toast.error).toHaveBeenCalled();
  });

  it("advances to birth when session is already running", async () => {
    vi.mocked(postConfigure).mockResolvedValue({ success: true, steps: [] });
    vi.mocked(startBirth).mockResolvedValue({
      status: "already_running",
      message: "Birth Phase is already running",
    });

    const ok = await useOnboardingStore.getState().activateBirth();

    expect(ok).toBe(true);
    expect(useOnboardingStore.getState().phase).toBe("birth");
    expect(toast.info).toHaveBeenCalled();
  });

  it("enters phase hub when birth is already completed with artifacts", async () => {
    useOnboardingStore.setState({
      payload: {
        ...basePayload,
        app_surface: "hub",
        birth: { status: "completed", artifacts_ok: true },
      } as never,
    });
    vi.mocked(postConfigure).mockResolvedValue({ success: true, steps: [] });
    vi.mocked(startBirth).mockResolvedValue({
      status: "already_completed",
      message: "Birth already complete",
    });

    const ok = await useOnboardingStore.getState().activateBirth();

    expect(ok).toBe(true);
    expect(useOnboardingStore.getState().phase).toBe("hub");
    expect(toast.info).toHaveBeenCalled();
  });

  it("ignores duplicate activate calls while in flight", async () => {
    vi.mocked(startBirth).mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ status: "started" }), 20);
        }),
    );

    const store = useOnboardingStore.getState();
    const first = store.activateBirth();
    const second = store.activateBirth();
    await Promise.all([first, second]);

    expect(startBirth).toHaveBeenCalledTimes(1);
  });
});
