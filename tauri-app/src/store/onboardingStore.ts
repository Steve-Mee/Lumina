import { create } from "zustand";

import type { OnboardingPayload, OnboardingStepId } from "@/lib/onboardingSteps";
import {
  fetchOnboardingStatus,
  postConfigure,
  startBirth,
  startSmartSetup,
  type ConfigurePayload,
} from "@/lib/setupClient";

export interface OnboardingDraft {
  mode: "sim" | "real";
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
  };
  training: {
    training_trades: number;
    prefer_real_data_only: boolean;
    max_real_days: number;
  };
}

interface OnboardingState {
  phase: "loading" | "wizard" | "cockpit";
  payload: OnboardingPayload | null;
  currentStepIndex: number;
  draft: OnboardingDraft;
  error: string | null;
  activating: boolean;
  smartSetupRunning: boolean;
  refresh: () => Promise<void>;
  enterCockpit: () => void;
  setStepIndex: (index: number) => void;
  updateDraft: (patch: Partial<OnboardingDraft>) => void;
  runSmartSetup: () => Promise<void>;
  saveConfiguration: () => Promise<boolean>;
  activateBirth: () => Promise<boolean>;
  hydrateDraftFromPayload: (payload: OnboardingPayload) => void;
}

const defaultDraft = (): OnboardingDraft => ({
  mode: "sim",
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
  },
  training: {
    training_trades: 25000,
    prefer_real_data_only: true,
    max_real_days: 56,
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
    const d = payload.defaults;
    const modeKey = payload.defaults.mode === "real" ? "real" : "sim";
    const modeDefaults = (d[modeKey as "sim" | "real"] ?? {}) as Record<string, unknown>;
    const rc = d.risk_controller as Record<string, unknown>;
    const fb = d.first_boot as Record<string, unknown>;
    const evo = d.evolution as Record<string, unknown>;
    set({
      draft: {
        mode: payload.defaults.mode === "real" ? "real" : "sim",
        credentials: get().draft.credentials,
        risk: {
          kelly_fraction: Number(modeDefaults.kelly_fraction ?? 1.0),
          daily_loss_cap:
            modeDefaults.daily_loss_cap != null ? Number(modeDefaults.daily_loss_cap) : null,
          max_total_open_risk: Number(
            modeDefaults.max_total_open_risk ?? rc.max_total_open_risk ?? 3000,
          ),
          real_capital_safety_threshold_usd: Number(rc.real_capital_safety_threshold_usd ?? 1000),
        },
        evolution: {
          approval_required: Boolean(
            modeDefaults.approval_required ?? evo.approval_required ?? true,
          ),
          aggressive_evolution: Boolean(modeDefaults.aggressive_evolution ?? true),
        },
        training: {
          training_trades: Number(fb.training_trades ?? 25000),
          prefer_real_data_only: Boolean(fb.prefer_real_data_only ?? true),
          max_real_days: Number(fb.max_real_days ?? 56),
        },
      },
    });
  },

  refresh: async () => {
    try {
      const payload = await fetchOnboardingStatus();
      get().hydrateDraftFromPayload(payload);
      const skip =
        payload.skip_wizard ||
        (payload.setup_complete &&
          (payload.birth.status === "running" || payload.birth.artifacts_ok));
      const visible = payload.required_steps.filter((s) => s !== "welcome");
      const shortPath = visible.length <= 2;
      const priorPhase = get().phase;
      let currentStepIndex = get().currentStepIndex;
      if (priorPhase === "loading" || (shortPath && currentStepIndex === 0)) {
        currentStepIndex = shortPath && payload.required_steps.length > 1 ? 1 : 0;
      }
      set({
        payload,
        error: null,
        smartSetupRunning: payload.smart_setup_running,
        currentStepIndex,
        phase: skip ? "cockpit" : priorPhase === "cockpit" ? "cockpit" : "wizard",
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
    set({ smartSetupRunning: true, error: null });
    try {
      await startSmartSetup({ install_ollama: true, download_recommended_model: true });
    } catch (err) {
      set({
        smartSetupRunning: false,
        error: err instanceof Error ? err.message : "Smart setup failed",
      });
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
        allow_minimal_synthetic_fallback: false,
        require_real_simulator_data: draft.training.prefer_real_data_only,
      },
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
      await startBirth(draft.training.training_trades);
      set({ phase: "cockpit", activating: false });
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
  if (!payload) return ["welcome"];
  return payload.required_steps;
}
