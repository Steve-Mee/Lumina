import { create } from "zustand";
import { toast } from "sonner";

import type { OnboardingPayload, OnboardingStepId } from "@/lib/onboardingSteps";
import type { MutationDepth, OperationsMode } from "@/lib/botConfigDraft";
import { mapAppPhase, resolvePhaseOnRefreshError, markPayloadBackendUnreachable, type AppPhase } from "@/lib/onboardingPhase";
import { hydrateBotConfigDraftFromPayload } from "@/lib/botConfigDraft";
import {
  fetchAndHydrateDeckApiKey,
  fetchDeckCredentialsPrefill,
  fetchFabricLinkStatus,
  fetchOnboardingStatus,
  postConfigure,
  postCredentials,
  postFabricConnectionTest,
  postReadyForBirth,
  startSmartSetup,
  type ConfigurePayload,
} from "@/lib/setupClient";
import {
  isBirthStartSuccessful,
  startBirth,
} from "@/lib/birthClient";
import type { BirthActivationStep } from "@/lib/birthOperatorMode";
import { mergeCredentialsIntoDraft } from "@/lib/credentialsPrefill";
import { persistMonitoringApiKey, resolveMonitoringApiKey } from "@/lib/monitoringClient";
import {
  startupSafeToastError,
  startupSafeToastMessage,
} from "@/lib/startupToastGate";
import { fetchTwinReadiness } from "@/lib/twinClient";
import { useBirthStore } from "@/store/birthStore";

export interface OnboardingDraft {
  mode: OperationsMode;
  selected_model_key: string;
  credentials: {
    LUMINA_JWT_SECRET_KEY: string;
    CROSSTRADE_TOKEN: string;
    CROSSTRADE_ACCOUNT: string;
    LUMINA_ADMIN_API_KEY: string;
    LUMINA_FABRIC_TOKEN: string;
    XAI_API_KEY: string;
    TELEGRAM_BOT_TOKEN: string;
    TELEGRAM_CHAT_ID: string;
  };
  smart_setup: {
    force_high_tier: boolean;
    pull_extra_models: boolean;
  };
  risk: {
    kelly_fraction: number;
    daily_loss_cap: number | null;
    max_total_open_risk: number;
    real_capital_safety_threshold_usd: number;
  };
  evolution: {
    approval_required: boolean;
    aggressive_evolution: boolean;
    max_mutation_depth: MutationDepth;
  };
  training: {
    training_trades: number;
    prefer_real_data_only: boolean;
    max_real_days: number;
    allow_minimal_synthetic_fallback: boolean;
    require_real_simulator_data: boolean;
    stage1_winrate_pass_threshold: number;
  };
  /** Operator Vault emergency CrossTrade MD fallback (YAML SSOT). */
  emergency_market_data_fallback: boolean;
}

export type { AppPhase } from "@/lib/onboardingPhase";

interface OnboardingState {
  phase: AppPhase;
  payload: OnboardingPayload | null;
  currentStepIndex: number;
  draft: OnboardingDraft;
  error: string | null;
  activating: boolean;
  /** Progress step while activating — never use `error` for progress copy. */
  activationStep: BirthActivationStep;
  birthPhaseCommitted: boolean;
  /** Operator reopened first-boot setup (credentials / Fabric test) from Birth. */
  setupReviewActive: boolean;
  /** Operator opened Command Deck from Phase Hub (session override of app_surface=hub). */
  operatorDeckActive: boolean;
  smartSetupRunning: boolean;
  /**
   * Systems Go finished this session (Fabric ready or operator degraded).
   * Until true, StartupReadiness cover stays up — no half-loaded Genesis.
   */
  ntStartupResolved: boolean;
  /** Operator chose "Continue without NinjaTrader link" this session. */
  ntLinkDeferred: boolean;
  /** Operator dismissed the degraded-link banner for this session. */
  ntDegradedBannerDismissed: boolean;
  /** Cold-start Fabric result — Setup reuses this instead of re-waiting. */
  fabricStartup: {
    green: boolean;
    certified: boolean;
    hostReady?: boolean;
    level?: string;
    reason: string;
    probedAt: number;
  } | null;
  setNtStartupResolved: (v: boolean) => void;
  setNtLinkDeferred: (v: boolean) => void;
  dismissNtDegradedBanner: () => void;
  setFabricStartup: (
    v: {
      green: boolean;
      certified: boolean;
      hostReady?: boolean;
      level?: string;
      reason: string;
      probedAt: number;
    } | null,
  ) => void;
  refresh: () => Promise<void>;
  setPhase: (phase: AppPhase) => void;
  enterSetupReview: (preferredStep?: OnboardingStepId) => void;
  exitSetupReview: () => void;
  /** Open Command Deck from Phase Hub without waiting for app_surface=deck. */
  enterOperatorDeck: () => void;
  /** Leave deck override and return to Phase Hub surface. */
  returnToPhaseHub: () => void;
  completeBirthTransition: () => void;
  setStepIndex: (index: number) => void;
  updateDraft: (patch: Partial<OnboardingDraft>) => void;
  runSmartSetup: (options?: {
    force_high_tier?: boolean;
    pull_extra_models?: boolean;
  }) => Promise<void>;
  saveCredentials: () => Promise<boolean>;
  saveConfiguration: (options?: { skipRefresh?: boolean }) => Promise<boolean>;
  activateBirth: () => Promise<boolean>;
  hydrateDraftFromPayload: (payload: OnboardingPayload) => void;
  importCredentialsFromEnv: () => Promise<boolean>;
}

const defaultDraft = (): OnboardingDraft => ({
  mode: "sim",
  selected_model_key: "",
  credentials: {
    LUMINA_JWT_SECRET_KEY: "",
    CROSSTRADE_TOKEN: "",
    CROSSTRADE_ACCOUNT: "",
    LUMINA_ADMIN_API_KEY: "",
    LUMINA_FABRIC_TOKEN: "",
    XAI_API_KEY: "",
    TELEGRAM_BOT_TOKEN: "",
    TELEGRAM_CHAT_ID: "",
  },
  smart_setup: {
    force_high_tier: false,
    pull_extra_models: false,
  },
  risk: {
    kelly_fraction: 1.0,
    daily_loss_cap: null,
    max_total_open_risk: 3000,
    real_capital_safety_threshold_usd: 1000,
  },
  evolution: {
    approval_required: true,
    aggressive_evolution: true,
    max_mutation_depth: "radical",
  },
  training: {
    training_trades: 25000,
    prefer_real_data_only: true,
    max_real_days: 365,
    allow_minimal_synthetic_fallback: false,
    require_real_simulator_data: true,
    stage1_winrate_pass_threshold: 0.45,
  },
  emergency_market_data_fallback: false,
});

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  phase: "loading",
  payload: null,
  currentStepIndex: 0,
  draft: defaultDraft(),
  error: null,
  activating: false,
  activationStep: "idle",
  birthPhaseCommitted: false,
  setupReviewActive: false,
  operatorDeckActive: false,
  smartSetupRunning: false,
  ntStartupResolved: false,
  ntLinkDeferred: false,
  ntDegradedBannerDismissed: false,
  fabricStartup: null,

  setPhase: (phase) => set({ phase }),
  setNtStartupResolved: (v) => set({ ntStartupResolved: v }),
  setFabricStartup: (v) => set({ fabricStartup: v }),
  setNtLinkDeferred: (v) =>
    set({
      ntLinkDeferred: v,
      // Degraded continue = systems go complete (review-only)
      ntStartupResolved: v ? true : get().ntStartupResolved,
      ntDegradedBannerDismissed: v ? false : get().ntDegradedBannerDismissed,
    }),
  dismissNtDegradedBanner: () => set({ ntDegradedBannerDismissed: true }),

  enterSetupReview: (preferredStep = "credentials") => {
    const steps = SETUP_REVIEW_STEPS;
    const preferred = preferredStep;
    let idx = steps.indexOf(preferred as OnboardingStepId);
    if (idx < 0) {
      idx = 0;
    }
    set({
      setupReviewActive: true,
      birthPhaseCommitted: false,
      phase: "wizard",
      currentStepIndex: Math.max(0, idx),
      error: null,
    });
  },

  exitSetupReview: () => {
    set({
      setupReviewActive: false,
      phase: "birth",
      birthPhaseCommitted: false,
      error: null,
    });
    void get().refresh();
  },

  completeBirthTransition: () => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("lumina.showCockpitWelcome", "1");
      } catch {
        // ignore storage failures
      }
    }
    void fetchAndHydrateDeckApiKey();
    set({ phase: "cockpit", birthPhaseCommitted: false, operatorDeckActive: false });
  },

  enterOperatorDeck: () => {
    void fetchAndHydrateDeckApiKey();
    set({
      phase: "cockpit",
      operatorDeckActive: true,
      setupReviewActive: false,
      error: null,
    });
  },

  returnToPhaseHub: () => {
    set({
      phase: "hub",
      operatorDeckActive: false,
      setupReviewActive: false,
      error: null,
    });
    void get().refresh();
  },

  setStepIndex: (index) => set({ currentStepIndex: index }),

  updateDraft: (patch) =>
    set((state) => ({
      draft: {
        ...state.draft,
        ...patch,
        credentials: { ...state.draft.credentials, ...(patch.credentials ?? {}) },
        risk: { ...state.draft.risk, ...(patch.risk ?? {}) },
        evolution: { ...state.draft.evolution, ...(patch.evolution ?? {}) },
        training: { ...state.draft.training, ...(patch.training ?? {}) },
      },
    })),

  hydrateDraftFromPayload: (payload) => {
    const botDraft = hydrateBotConfigDraftFromPayload(payload, get().draft);
    set({
      draft: {
        ...get().draft,
        mode: botDraft.mode,
        selected_model_key:
          get().draft.selected_model_key ||
          payload.intelligence.recommended_model_key ||
          payload.model_catalog.find((m) => m.is_recommended)?.key ||
          "",
        risk: botDraft.risk,
        evolution: botDraft.evolution,
        training: {
          training_trades: Number((payload.defaults.first_boot as Record<string, unknown>).training_trades ?? 25000),
          prefer_real_data_only: Boolean(
            (payload.defaults.first_boot as Record<string, unknown>).prefer_real_data_only ?? true,
          ),
          max_real_days: Number((payload.defaults.first_boot as Record<string, unknown>).max_real_days ?? 365),
          allow_minimal_synthetic_fallback: Boolean(
            (payload.defaults.first_boot as Record<string, unknown>).allow_minimal_synthetic_fallback ?? false,
          ),
          require_real_simulator_data: Boolean(
            (payload.defaults.first_boot as Record<string, unknown>).require_real_simulator_data ?? true,
          ),
          stage1_winrate_pass_threshold: Number(
            (payload.defaults.birth_v2 as Record<string, unknown> | undefined)
              ?.stage1_winrate_pass_threshold ?? 0.45,
          ),
        },
        credentials: mergeCredentialsIntoDraft(get().draft.credentials, {
          LUMINA_ADMIN_API_KEY:
            get().draft.credentials.LUMINA_ADMIN_API_KEY.trim() ||
            resolveMonitoringApiKey() ||
            "",
        }),
      },
    });
  },

  importCredentialsFromEnv: async () => {
    try {
      const snapshot = await fetchDeckCredentialsPrefill();
      const merged = mergeCredentialsIntoDraft(get().draft.credentials, snapshot.credentials);
      const adminKey = merged.LUMINA_ADMIN_API_KEY.trim();
      if (adminKey) {
        persistMonitoringApiKey(adminKey);
      }
      const emergency = Boolean(
        snapshot.emergency_market_data_fallback ??
          snapshot.fallback_on_fabric_failure ??
          get().draft.emergency_market_data_fallback,
      );
      set({
        draft: {
          ...get().draft,
          credentials: merged,
          emergency_market_data_fallback: emergency,
        },
      });
      return true;
    } catch {
      return false;
    }
  },

  refresh: async () => {
    try {
      const payload = await fetchOnboardingStatus();
      get().hydrateDraftFromPayload(payload);
      void get().importCredentialsFromEnv();
      const priorPhase = get().phase;
      const activating = get().activating;
      const preservedError = get().error;
      const setupReviewActive = get().setupReviewActive;
      set({
        payload,
        error: activating ? preservedError : null,
        smartSetupRunning: payload.smart_setup_running,
        currentStepIndex: priorPhase === "loading" ? 0 : get().currentStepIndex,
        phase: activating
          ? priorPhase === "loading"
            ? "wizard"
            : priorPhase
          : mapAppPhase(payload, {
              priorPhase,
              birthPhaseCommitted: get().birthPhaseCommitted,
              activating: false,
              setupReviewActive,
              operatorDeckActive: get().operatorDeckActive,
            }),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load onboarding status";
      const priorPhase = get().phase;
      const lastPayload = get().payload;
      const payloadAfterError =
        lastPayload != null ? markPayloadBackendUnreachable(lastPayload, message) : null;
      set({
        error: message,
        phase: resolvePhaseOnRefreshError(
          priorPhase,
          payloadAfterError ?? lastPayload,
          get().setupReviewActive,
        ),
        payload: payloadAfterError ?? lastPayload,
        currentStepIndex: priorPhase === "loading" ? 0 : get().currentStepIndex,
      });
    }
  },

  runSmartSetup: async (options) => {
    const { draft } = get();
    set({ smartSetupRunning: true, error: null });
    try {
      await startSmartSetup({
        install_ollama: true,
        download_recommended_model: true,
        selected_model_key: draft.selected_model_key || undefined,
        force_high_tier: options?.force_high_tier ?? draft.smart_setup.force_high_tier,
        pull_extra_models: options?.pull_extra_models ?? draft.smart_setup.pull_extra_models,
      });
    } catch (err) {
      set({
        smartSetupRunning: false,
        error: err instanceof Error ? err.message : "Smart setup failed",
      });
    }
  },

  saveCredentials: async () => {
    const { draft, payload } = get();
    try {
      const applyOnboarding = (next: OnboardingPayload) => {
        get().hydrateDraftFromPayload(next);
        const priorPhase = get().phase;
        set({
          payload: next,
          phase: mapAppPhase(next, {
            priorPhase,
            birthPhaseCommitted: get().birthPhaseCommitted,
            activating: false,
            setupReviewActive: get().setupReviewActive,
            operatorDeckActive: get().operatorDeckActive,
          }),
        });
      };

      const jwt = draft.credentials.LUMINA_JWT_SECRET_KEY.trim();
      const wizardRequired = payload?.credentials.wizard_required !== false;
      const setupComplete = Boolean(payload?.setup_complete);

      // Persist vault secrets whenever the form has a JWT (active seal / re-seal).
      // Backend /credentials also seeds SIM + mark_complete on modern backends.
      if (wizardRequired || jwt) {
        if (!jwt) {
          set({ error: "JWT secret is required to seal the vault" });
          return false;
        }
        persistMonitoringApiKey(draft.credentials.LUMINA_ADMIN_API_KEY);
        const result = await postCredentials({
          ...draft.credentials,
          emergency_market_data_fallback: Boolean(draft.emergency_market_data_fallback),
        });
        if (result.onboarding) {
          applyOnboarding(result.onboarding);
        } else {
          await get().refresh();
        }
        if (!result.success) {
          return false;
        }
        // Modern backends seed setup on /credentials. Older ones may leave setup incomplete.
        if (!get().payload?.setup_complete) {
          try {
            const ready = await postReadyForBirth();
            if (ready.onboarding) applyOnboarding(ready.onboarding);
            else await get().refresh();
          } catch {
            // Fallback: classic configure path (pre-lifecycle-v2 backends).
            return await get().saveConfiguration({ skipRefresh: false });
          }
        }
        return true;
      }

      // No draft secrets + wizard not required: env already holds vault keys.
      if (setupComplete) {
        // Re-open from Birth / review — nothing to write; allow continue.
        await get().refresh();
        return true;
      }

      // First boot with env-configured vault, setup not marked complete yet.
      try {
        const ready = await postReadyForBirth();
        if (ready.onboarding) applyOnboarding(ready.onboarding);
        else await get().refresh();
        return ready.success;
      } catch {
        // Older backend without /ready-for-birth — use /configure with draft defaults.
        return await get().saveConfiguration({ skipRefresh: false });
      }
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Failed to save credentials" });
      return false;
    }
  },

  saveConfiguration: async (options?: { skipRefresh?: boolean }) => {
    const { draft } = get();
    const body: ConfigurePayload = {
      mode: draft.mode,
      credentials: draft.credentials,
      risk: draft.risk,
      evolution: draft.evolution,
      training: {
        ...draft.training,
        allow_minimal_synthetic_fallback: draft.training.allow_minimal_synthetic_fallback,
        require_real_simulator_data: draft.training.require_real_simulator_data,
        stage1_winrate_pass_threshold: draft.training.stage1_winrate_pass_threshold,
      },
      selected_model_key: draft.selected_model_key || undefined,
    };
    try {
      const result = await postConfigure(body);
      if (!result.success) {
        const failures = result.steps.filter((step) => step.success === false);
        const message =
          failures[0]?.message?.trim() ||
          failures[0]?.step?.trim() ||
          "Configuration could not be saved";
        set({ error: message });
        return false;
      }
      if (options?.skipRefresh) {
        if (result.onboarding) {
          get().hydrateDraftFromPayload(result.onboarding);
          set({ payload: result.onboarding });
        }
        return true;
      }
      await get().refresh();
      return true;
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Configure failed" });
      return false;
    }
  },

  activateBirth: async () => {
    if (get().activating) {
      return false;
    }
    // Intent sticky: land on Birth phase immediately so launch shell is visible
    // (wizard BirthActivateStep must not keep the operator during Fabric/history wait).
    set({
      phase: "birth",
      activating: true,
      activationStep: "fabric",
      error: null,
      birthPhaseCommitted: true,
      setupReviewActive: false,
    });
    useBirthStore.setState({
      genesisPinned: false,
      runPinned: false,
      pollError: null,
    });
    const failActivation = async (message: string, opts?: { setupReview?: boolean }) => {
      // Stay on genesis/decision — never flash orphan recovery surface.
      set({
        phase: opts?.setupReview ? get().phase : "birth",
        activating: false,
        activationStep: "idle",
        birthPhaseCommitted: false,
        error: message,
      });
      if (opts?.setupReview) {
        get().enterSetupReview("credentials");
        set({ error: message });
      } else {
        useBirthStore.setState({
          uiPhase: "idle",
          birthSurface: "genesis",
          genesisPinned: true,
          runPinned: false,
          pollError: message,
        });
        await useBirthStore.getState().poll().catch(() => undefined);
      }
    };
    try {
      // Fail-closed: Fabric link GREEN required before Genesis.
      try {
        startupSafeToastMessage("Connecting to NinjaTrader Fabric…");
        let link = await fetchFabricLinkStatus();
        // Fail-closed: gate_birth_ok (host + recent proof) or live GREEN with proof.
        let ready = Boolean(
          link.gate_birth_ok ||
            (link.green && (link.proof?.certified || link.proof?.badge_ok)),
        );
        if (!ready) {
          try {
            const report = await postFabricConnectionTest({
              include_safe_mode: false,
              instrument: "",
            });
            if (report?.overall === "green" || report?.certified) {
              link = await fetchFabricLinkStatus();
              ready = Boolean(
                link.gate_birth_ok ||
                  (link.green &&
                    (link.proof?.certified ||
                      link.proof?.badge_ok ||
                      report.overall === "green")) ||
                  (link.host_ready &&
                    (link.proof?.certified || report.overall === "green")),
              );
            }
          } catch {
            /* keep not-ready */
          }
        }
        if (!ready) {
          const message =
            "Connecting to NinjaTrader Fabric failed or host/proof not ready. " +
            "Start NinjaTrader (datafeed Connected), open New → LUMINA, then Setup → Test connection. " +
            `(live=${link.level || "?"} ${link.meaning || link.reason || ""})`;
          startupSafeToastError(message);
          await failActivation(message, { setupReview: true });
          return false;
        }
      } catch {
        const message =
          "Could not verify Fabric link while connecting to NinjaTrader. " +
          "Open Setup & connection and run Test connection.";
        startupSafeToastError(message);
        await failActivation(message, { setupReview: true });
        return false;
      }

      set({ activationStep: "twin" });

      // Fail-closed: Twin base curriculum (Operator Vault → Twin) required before Birth.
      try {
        const twin = await fetchTwinReadiness();
        if (!twin.birth_ready && !twin.base_trained) {
          const message =
            "Twin base training is not complete. Open Operator Vault → Twin and finish the base curriculum before Birth can start.";
          startupSafeToastError(message);
          await failActivation(message, { setupReview: true });
          return false;
        }
      } catch {
        const message =
          "Could not verify Twin Birth-ready status. Open Operator Vault → Twin and complete base training.";
        startupSafeToastError(message);
        await failActivation(message, { setupReview: true });
        return false;
      }

      set({ activationStep: "history" });

      const { draft } = get();
      const configured = await get().saveConfiguration({ skipRefresh: true });
      if (!configured) {
        const message =
          get().error?.trim() || "Could not save genesis settings before birth.";
        toast.error(message);
        await failActivation(message);
        return false;
      }

      useBirthStore.getState().setTargetTrades(draft.training.training_trades);
      set({ activationStep: "engine" });
      // Hard wall: never leave UI stuck on VERIFYING if backend stalls (CT hang).
      const START_TIMEOUT_MS = 90_000;
      const result = await Promise.race([
        startBirth(draft.training.training_trades),
        new Promise<never>((_, reject) => {
          window.setTimeout(() => {
            reject(
              new Error(
                "Birth start timed out after 90s (history preflight). " +
                  "Ensure Fabric path is used (not CrossTrade) and NT historical_bars is GREEN.",
              ),
            );
          }, START_TIMEOUT_MS);
        }),
      ]);

      if (result.status === "already_completed") {
        const message = result.message?.trim() || "Birth phase already completed.";
        const artifactsOk = get().payload?.birth.artifacts_ok ?? false;
        if (artifactsOk) {
          toast.info(message);
          get().completeBirthTransition();
          set({ activating: false, activationStep: "done" });
          return true;
        }
        toast.info(message);
        set({
          phase: "birth",
          activating: false,
          activationStep: "done",
          birthPhaseCommitted: true,
        });
        return true;
      }

      if (!isBirthStartSuccessful(result.status)) {
        const message =
          result.message?.trim() ||
          `Birth activation blocked (${String(result.status).replace(/_/g, " ")})`;
        toast.error(message);
        await failActivation(message);
        return false;
      }

      if (result.status === "already_running") {
        toast.info(result.message ?? "Birth phase is already running.");
      }

      useBirthStore.getState().beginBirthRun();
      await get().refresh();
      await useBirthStore.getState().poll();
      set({
        phase: "birth",
        activating: false,
        activationStep: "done",
        birthPhaseCommitted: true,
        error: null,
      });
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Birth activation failed";
      toast.error(message);
      await failActivation(message);
      return false;
    } finally {
      // Belt-and-suspenders: never leave activating stuck.
      if (get().activating) {
        set({ activating: false, activationStep: "idle" });
      }
    }
  },
}));

/** Steps shown when operator reopens setup from Birth (post-install connection & config). */
export const SETUP_REVIEW_STEPS: OnboardingStepId[] = ["credentials", "configuration"];

export function selectActiveSteps(payload: OnboardingPayload | null): OnboardingStepId[] {
  if (useOnboardingStore.getState().setupReviewActive) {
    return SETUP_REVIEW_STEPS;
  }
  if (!payload) return ["backend"];
  if (payload.wizard_steps.length > 0) return payload.wizard_steps;
  return payload.required_steps;
}
