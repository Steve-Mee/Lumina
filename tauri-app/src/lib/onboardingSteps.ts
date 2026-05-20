export type OnboardingStepId =
  | "welcome"
  | "backend"
  | "ollama"
  | "model"
  | "credentials"
  | "configuration"
  | "birth";

export type StepStatus = "pending" | "done" | "running" | "blocked";

export interface ModelCatalogEntry {
  key: string;
  display_name: string;
  ollama_tag: string;
  recommended_tier: string;
  parameter_size_b: number;
  fits_hardware: boolean;
  is_recommended: boolean;
}

export interface ReadinessRow {
  id: string;
  label: string;
  status: "ok" | "missing" | "pending";
}

export interface OnboardingPayload {
  backend: { reachable: boolean; url: string; latency_ms?: number; error?: string };
  setup_complete: boolean;
  skip_wizard: boolean;
  birth: {
    status: string;
    message?: string;
    progress?: Record<string, unknown>;
    artifacts_ok: boolean;
    artifacts_label?: string;
  };
  intelligence: {
    ollama_installed: boolean;
    ollama_required: boolean;
    recommended_model_key: string;
    recommended_ollama_tag: string;
    recommended_model_present: boolean;
    recommended_provider: string;
    hardware: Record<string, unknown>;
    adaptive_intelligence: Record<string, unknown>;
    missing: string[];
  };
  model_catalog: ModelCatalogEntry[];
  readiness: ReadinessRow[];
  credentials: {
    missing: string[];
    has_admin_api_key: boolean;
    env_path?: string;
    present?: Record<string, boolean>;
    wizard_required?: boolean;
    skip_reason?: "env_configured" | "setup_complete" | null;
  };
  workspace_root?: string;
  required_steps: OnboardingStepId[];
  wizard_steps: OnboardingStepId[];
  step_status: Record<string, StepStatus>;
  defaults: {
    mode: string;
    sim: Record<string, unknown>;
    real: Record<string, unknown>;
    evolution: Record<string, unknown>;
    first_boot: Record<string, unknown>;
    risk_controller: Record<string, unknown>;
  };
  smart_setup_running: boolean;
}

export const STEP_LABELS: Record<OnboardingStepId, string> = {
  welcome: "Welcome",
  backend: "Backend",
  ollama: "Ollama",
  model: "Model",
  credentials: "Credentials",
  configuration: "Configuration",
  birth: "Birth Phase",
};

/** Client-side mirror of server gate for tests and UI hints. */
export function shouldEnterCockpit(payload: OnboardingPayload): boolean {
  if (payload.skip_wizard) return true;
  if (
    payload.setup_complete &&
    (payload.birth.status === "running" || payload.birth.artifacts_ok)
  ) {
    return true;
  }
  const pending = payload.wizard_steps.filter((s) => s !== "welcome");
  if (pending.length === 0 && payload.setup_complete) {
    return payload.birth.status === "running" || payload.birth.artifacts_ok;
  }
  return false;
}

export function visibleSteps(steps: OnboardingStepId[]): OnboardingStepId[] {
  return steps.filter((s) => s !== "welcome");
}

export function resolveWizardSteps(required: OnboardingStepId[]): OnboardingStepId[] {
  const pending = required.filter((step) => step !== "welcome");
  if (pending.length <= 2) return pending;
  return required;
}
