import { create } from "zustand";

import type { OnboardingPayload, OnboardingStepId } from "@/lib/onboardingSteps";
import type { MutationDepth, OperationsMode } from "@/lib/botConfigDraft";
import { hydrateBotConfigDraftFromPayload } from "@/lib/botConfigDraft";
import {
  fetchOnboardingStatus,
  postConfigure,
  postCredentials,
  startBirth,
  startSmartSetup,
  type ConfigurePayload,
} from "@/lib/setupClient";
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
  };
}

export type AppPhase = "loading" | "wizard" | "birth" | "cockpit";

function resolveAppPhase(
  payload: OnboardingPayload,
  priorPhase: AppPhase,
): AppPhase {
  const birthRunning = payload.birth.status === "running";
  const birthReady =
    payload.birth.artifacts_ok && payload.birth.status === "completed";

  if (priorPhase === "birth") return "birth";
  if (birthRunning) return "birth";
  if (
    payload.skip_wizard ||
    (payload.setup_complete && birthReady && !birthRunning)
  ) {
    return "cockpit";
  }
  if (priorPhase === "cockpit") return "cockpit";
  return "wizard";
}

interface OnboardingState {
  phase: AppPhase;
  payload: OnboardingPayload | null;
  currentStepIndex: number;
  draft: OnboardingDraft;
  error: string | null;
  activating: boolean;
  smartSetupRunning: boolean;
  refresh: () => Promise<void>;
  enterCockpit: () => void;
  setPhase: (phase: AppPhase) => void;
  completeBirthTransition: () => void;
  setStepIndex: (index: number) => void;
  updateDraft: (patch: Partial<OnboardingDraft>) => void;
  runSmartSetup: () => Promise<void>;
  saveCredentials: () => Promise<boolean>;
  saveConfiguration: () => Promise<boolean>;
  activateBirth: () => Promise<boolean>;
  hydrateDraftFromPayload: (payload: OnboardingPayload) => void;
}

const defaultDraft = (): OnboardingDraft => ({
  mode: "sim",
  selected_model_key: "",
  credentials: {
    LUMINA_JWT_SECRET_KEY: "",
    CROSSTRADE_TOKEN: "",
    CROSSTRADE_ACCOUNT: "",
    LUMINA_ADMIN_API_KEY: "",
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
  },
});

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  phase: "loading",
  payload: null,
  currentStepIndex: 0,
  draft: defaultDraft(),
  error: null,
  activating: false,
  smartSetupRunning: false,

  enterCockpit: () => set({ phase: "cockpit" }),

  setPhase: (phase) => set({ phase }),

  completeBirthTransition: () => set({ phase: "cockpit" }),

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
        },
        credentials: {
          ...get().draft.credentials,
          LUMINA_ADMIN_API_KEY:
            get().draft.credentials.LUMINA_ADMIN_API_KEY.trim() ||
            resolveMonitoringApiKey() ||
            "",
        },
      },
    });
  },

  refresh: async () => {
    try {
      const payload = await fetchOnboardingStatus();
      get().hydrateDraftFromPayload(payload);
      const priorPhase = get().phase;
      set({
        payload,
        error: null,
        smartSetupRunning: payload.smart_setup_running,
        currentStepIndex: priorPhase === "loading" ? 0 : get().currentStepIndex,
        phase: resolveAppPhase(payload, priorPhase),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load onboarding status";
      set({
        error: message,
        phase: "wizard",
        payload: null,
        currentStepIndex: 0,
      });
    }
  },

  runSmartSetup: async () => {
    const { draft } = get();
    set({ smartSetupRunning: true, error: null });
    try {
      await startSmartSetup({
        install_ollama: true,
        download_recommended_model: true,
        selected_model_key: draft.selected_model_key || undefined,
      });
    } catch (err) {
      set({
        smartSetupRunning: false,
        error: err instanceof Error ? err.message : "Smart setup failed",
      });
    }
  },

  saveCredentials: async () => {
    const { draft } = get();
    try {
      persistMonitoringApiKey(draft.credentials.LUMINA_ADMIN_API_KEY);
      const result = await postCredentials(draft.credentials);
      await get().refresh();
      return result.success;
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Failed to save credentials" });
      return false;
    }
  },

  saveConfiguration: async () => {
    const { draft } = get();
    const body: ConfigurePayload = {
      mode: draft.mode,
      credentials: draft.credentials,
      risk: draft.risk,
      evolution: draft.evolution,
      training: {
        ...draft.training,
        allow_minimal_synthetic_fallback: draft.training.allow_minimal_synthetic_fallback,
        require_real_simulator_data: draft.training.prefer_real_data_only,
      },
      selected_model_key: draft.selected_model_key || undefined,
    };
    try {
      const result = await postConfigure(body);
      await get().refresh();
      return result.success;
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Configure failed" });
      return false;
    }
  },

  activateBirth: async () => {
    set({ activating: true, error: null });
    try {
      const { draft, payload } = get();
      if (!payload?.setup_complete) {
        const ok = await get().saveConfiguration();
        if (!ok) {
          set({ activating: false });
          return false;
        }
      }
      useBirthStore.getState().setTargetTrades(draft.training.training_trades);
      await startBirth(draft.training.training_trades);
      set({ phase: "birth", activating: false });
      return true;
    } catch (err) {
      set({
        activating: false,
        error: err instanceof Error ? err.message : "Birth activation failed",
      });
      return false;
    }
  },
}));

export function selectActiveSteps(payload: OnboardingPayload | null): OnboardingStepId[] {
  if (!payload) return ["backend"];
  if (payload.wizard_steps.length > 0) return payload.wizard_steps;
  return payload.required_steps;
}
