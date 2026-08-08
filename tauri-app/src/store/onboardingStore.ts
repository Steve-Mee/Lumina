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
  postReadyForBirth,
  startSmartSetup,
  type ConfigurePayload,
} from "@/lib/setupClient";
import {
  isBirthStartSuccessful,
  startBirth,
} from "@/lib/birthClient";
import { mergeCredentialsIntoDraft } from "@/lib/credentialsPrefill";
import { persistMonitoringApiKey, resolveMonitoringApiKey } from "@/lib/monitoringClient";
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
}

export type { AppPhase } from "@/lib/onboardingPhase";

interface OnboardingState {
  phase: AppPhase;
  payload: OnboardingPayload | null;
  currentStepIndex: number;
  draft: OnboardingDraft;
  error: string | null;
  activating: boolean;
  birthPhaseCommitted: boolean;
  /** Operator reopened first-boot setup (credentials / Fabric test) from Birth. */
  setupReviewActive: boolean;
  /** Operator opened Command Deck from Phase Hub (session override of app_surface=hub). */
  operatorDeckActive: boolean;
  smartSetupRunning: boolean;
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
    max_real_days: 56,
    allow_minimal_synthetic_fallback: false,
    require_real_simulator_data: true,
    stage1_winrate_pass_threshold: 0.45,
  },
});

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  phase: "loading",
  payload: null,
  currentStepIndex: 0,
  draft: defaultDraft(),
  error: null,
  activating: false,
  birthPhaseCommitted: false,
  setupReviewActive: false,
  operatorDeckActive: false,
  smartSetupRunning: false,

  setPhase: (phase) => set({ phase }),

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
          max_real_days: Number((payload.defaults.first_boot as Record<string, unknown>).max_real_days ?? 56),
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
      set({
        draft: {
          ...get().draft,
          credentials: merged,
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
        const result = await postCredentials(draft.credentials);
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
    set({ activating: true, error: null, birthPhaseCommitted: true });
    try {
      // Fail-closed: Fabric diagnostic GREEN required before Genesis.
      try {
        const link = await fetchFabricLinkStatus();
        if (!link.green) {
          const message =
            "Fabric diagnostic must be GREEN before Birth. Open Setup & connection and run the test.";
          set({ activating: false, birthPhaseCommitted: false, error: message });
          toast.error(message);
          get().enterSetupReview("credentials");
          return false;
        }
      } catch {
        const message =
          "Could not verify Fabric link. Open Setup & connection and run Fabric diagnostic.";
        set({ activating: false, birthPhaseCommitted: false, error: message });
        toast.error(message);
        get().enterSetupReview("credentials");
        return false;
      }

      const { draft } = get();
      const configured = await get().saveConfiguration({ skipRefresh: true });
      if (!configured) {
        const message =
          get().error?.trim() || "Could not save genesis settings before birth.";
        set({ activating: false, birthPhaseCommitted: false, error: message });
        toast.error(message);
        return false;
      }

      useBirthStore.getState().setTargetTrades(draft.training.training_trades);
      useBirthStore.getState().beginBirthRun();
      const result = await startBirth(draft.training.training_trades);

      if (result.status === "already_completed") {
        const message = result.message?.trim() || "Birth phase already completed.";
        const artifactsOk = get().payload?.birth.artifacts_ok ?? false;
        if (artifactsOk) {
          toast.info(message);
          get().completeBirthTransition();
          set({ activating: false });
          return true;
        }
        toast.info(message);
        set({ phase: "birth", activating: false, birthPhaseCommitted: true });
        return true;
      }

      if (!isBirthStartSuccessful(result.status)) {
        const message =
          result.message?.trim() ||
          `Birth activation blocked (${String(result.status).replace(/_/g, " ")})`;
        set({ activating: false, birthPhaseCommitted: false, error: message });
        toast.error(message);
        return false;
      }

      if (result.status === "already_running") {
        toast.info(result.message ?? "Birth phase is already running.");
      }

      await get().refresh();
      await useBirthStore.getState().poll();
      set({ phase: "birth", activating: false, birthPhaseCommitted: true });
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Birth activation failed";
      set({
        activating: false,
        birthPhaseCommitted: false,
        error: message,
      });
      toast.error(message);
      return false;
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
