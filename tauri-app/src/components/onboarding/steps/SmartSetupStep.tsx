import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { fetchSmartSetupProgress } from "@/lib/setupClient";
import type { ModelCatalogEntry, OnboardingPayload } from "@/lib/onboardingSteps";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import { distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

interface SmartSetupStepProps {
  payload: OnboardingPayload;
  running: boolean;
  selectedModelKey: string;
  onSelectModel: (key: string) => void;
  onRun: (options?: { force_high_tier?: boolean; pull_extra_models?: boolean }) => void;
  onContinue: () => void;
  onRefresh: () => void;
}

interface InstructionStep {
  title: string;
  command?: string;
  manual?: string;
}

function copyCommand(command: string) {
  void navigator.clipboard.writeText(command);
  toast.success("Command copied");
}

export function SmartSetupStep({
  payload,
  running,
  selectedModelKey,
  onSelectModel,
  onRun,
  onContinue,
  onRefresh,
}: SmartSetupStepProps) {
  const [progressMsg, setProgressMsg] = useState("");
  const [percent, setPercent] = useState(0);
  const [failed, setFailed] = useState(false);
  const [instructions, setInstructions] = useState<InstructionStep[]>([]);
  const [instructionSummary, setInstructionSummary] = useState("");
  const [forceHighTier, setForceHighTier] = useState(false);
  const [pullExtraModels, setPullExtraModels] = useState(false);

  const needsOllama = payload.intelligence.missing.includes("ollama");
  const needsModel = payload.intelligence.missing.some((m) => m.startsWith("model:"));
  const ready =
    !needsOllama &&
    !needsModel &&
    payload.intelligence.recommended_model_present;

  const catalog = payload.model_catalog ?? [];
  const activeKey =
    selectedModelKey ||
    payload.intelligence.recommended_model_key ||
    catalog.find((m) => m.is_recommended)?.key ||
    "";

  useEffect(() => {
    if (!running && ready) return;
    const timer = setInterval(async () => {
      try {
        const prog = await fetchSmartSetupProgress();
        const statusRecord = prog.status ?? {};
        const phase = String(statusRecord.phase ?? "");
        const errorText = String(statusRecord.smart_setup_error ?? "");
        setProgressMsg(phase || errorText || "Working…");
        setFailed(phase === "failed" || Boolean(errorText));
        const steps = statusRecord.steps;
        if (Array.isArray(steps) && steps.length > 0) {
          setPercent(Math.min(95, steps.length * 8));
        }
        const manualSteps = prog.instructions?.steps ?? [];
        setInstructions(manualSteps);
        setInstructionSummary(String(prog.instructions?.summary ?? ""));
        if (!prog.running && ready) {
          onRefresh();
        }
      } catch {
        /* ignore poll errors */
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [running, ready, onRefresh]);

  useEffect(() => {
    if (ready) setPercent(100);
  }, [ready]);

  useEffect(() => {
    if (!failed && !running) return;
    void fetchSmartSetupProgress().then((prog) => {
      setInstructions(prog.instructions?.steps ?? []);
      setInstructionSummary(String(prog.instructions?.summary ?? ""));
    });
  }, [failed, running]);

  const tier = String(
    (payload.intelligence.adaptive_intelligence as { tier?: string })?.tier ?? "light",
  ).toUpperCase();

  const selectedEntry = catalog.find((m) => m.key === activeKey);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto max-w-xl p-2 md:p-4"
    >
      <h2 className="mb-2 text-lg font-semibold">Intelligence Stack</h2>
      <p className="mb-6 text-sm text-muted-foreground">
        Hardware tier <span className="text-cyan-300/90">{tier}</span> — choose a LUMINA-tested
        trading model for your stack.
      </p>

      <ul className="mb-6 space-y-2 text-sm">
        <li className={needsOllama ? "text-amber-300/90" : "text-emerald-400/90"}>
          Ollama: {payload.intelligence.ollama_installed ? "Installed" : "Missing"}
        </li>
        <li className={needsModel ? "text-amber-300/90" : "text-emerald-400/90"}>
          Model: {payload.intelligence.recommended_model_present ? "Ready" : "Not pulled"}
        </li>
      </ul>

      {catalog.length > 0 && payload.intelligence.recommended_provider === "ollama" && (
        <div className="mb-6">
          <label className="mb-2 block text-xs tracking-wider text-muted-foreground uppercase">
            Trading-capable model
          </label>
          <div className="space-y-2">
            {catalog.map((model: ModelCatalogEntry) => {
              const selected = model.key === activeKey;
              return (
                <button
                  key={model.key}
                  type="button"
                  onClick={() => onSelectModel(model.key)}
                  className={cn(
                    "w-full rounded-lg border px-3 py-3 text-left text-sm transition-all",
                    selected
                      ? "border-cyan-400/45 bg-cyan-400/10"
                      : luminaSurfaceMutedClass("border border-white/10 hover:border-white/20"),
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{model.display_name}</span>
                    {model.is_recommended && (
                      <span className="text-[10px] tracking-wider text-cyan-300/80 uppercase">
                        Recommended
                      </span>
                    )}
                  </div>
                  <p className="mt-1 font-mono text-xs text-muted-foreground">{model.ollama_tag}</p>
                  {!model.fits_hardware && (
                    <p className="mt-1 text-xs text-amber-300/90">
                      Heavier than your current hardware tier — may run slowly.
                    </p>
                  )}
                </button>
              );
            })}
          </div>
          {selectedEntry && (
            <p className="mt-2 text-xs text-muted-foreground">
              Selected: {selectedEntry.display_name} ({selectedEntry.recommended_tier} tier)
            </p>
          )}
        </div>
      )}

      {payload.intelligence.recommended_provider !== "ollama" && (
        <p className={cn("mb-4 rounded-lg p-3 text-xs", distressPanelClass())}>
          <span className={warnOverlayBodyClass()}>
            High-tier provider ({payload.intelligence.recommended_provider}) requires manual vLLM
            setup. See launcher documentation for GPU requirements.
          </span>
        </p>
      )}

      {(running || percent > 0) && (
        <div className="mb-6">
          <div className="mb-1 h-1.5 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-violet-500 transition-all duration-500"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">{progressMsg || "Starting…"}</p>
        </div>
      )}

      {(failed || (!ready && !running && instructions.length > 0)) && (
        <div className={cn("mb-6 rounded-lg p-4", distressPanelClass())}>
          <p className="mb-2 text-xs font-semibold tracking-wider uppercase text-muted-foreground">
            Manual setup fallback
          </p>
          {instructionSummary && (
            <p className="mb-3 text-xs text-muted-foreground">{instructionSummary}</p>
          )}
          <ul className="space-y-3">
            {instructions.map((step) => (
              <li key={step.title} className={luminaSurfaceMutedClass("rounded border border-white/10 p-3")}>
                <p className="text-sm font-medium">{step.title}</p>
                {step.manual && <p className="mt-1 text-xs text-muted-foreground">{step.manual}</p>}
                {step.command && (
                  <div className="mt-2 flex items-center gap-2">
                    <code className="flex-1 overflow-x-auto rounded bg-black/40 px-2 py-1 text-[11px] text-cyan-100/90">
                      {step.command}
                    </code>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => copyCommand(step.command!)}
                    >
                      Copy
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!ready && payload.intelligence.recommended_provider === "ollama" && (
        <div className="mb-4 space-y-2 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={forceHighTier}
              onChange={(e) => setForceHighTier(e.target.checked)}
            />
            Force high tier profile
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={pullExtraModels}
              onChange={(e) => setPullExtraModels(e.target.checked)}
            />
            Download extra recommended models
          </label>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        {!ready && payload.intelligence.recommended_provider === "ollama" && (
          <Button
            className="onboarding-cta"
            onClick={() => onRun({ force_high_tier: forceHighTier, pull_extra_models: pullExtraModels })}
            disabled={running || !activeKey}
          >
            {running ? "Installing…" : "Install & Configure"}
          </Button>
        )}
        {ready && (
          <Button className="onboarding-cta" onClick={onContinue}>
            Continue
          </Button>
        )}
      </div>
    </motion.div>
  );
}
