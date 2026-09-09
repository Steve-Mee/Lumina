import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { fetchSmartSetupProgress } from "@/lib/setupClient";
import type { ModelCatalogEntry, OnboardingPayload } from "@/lib/onboardingSteps";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import { CUDA_GLOSS, type VoiceChoiceId, resolveSmartSetupView } from "@/lib/organsSetup";
import { cn } from "@/lib/utils";

interface SmartSetupStepProps {
  payload: OnboardingPayload;
  running: boolean;
  selectedModelKey: string;
  onSelectModel: (key: string) => void;
  onRun: (options?: {
    force_high_tier?: boolean;
    pull_extra_models?: boolean;
    voice_provider?: VoiceChoiceId;
  }) => void;
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
  const defaultVoice = (payload.intelligence.voice_provider as VoiceChoiceId | undefined) ?? "ollama";
  const [voice, setVoice] = useState<VoiceChoiceId>(defaultVoice);

  const view = resolveSmartSetupView(payload, voice);
  const catalog = payload.model_catalog ?? [];
  const activeKey =
    selectedModelKey ||
    payload.intelligence.recommended_model_key ||
    catalog.find((m) => m.is_recommended)?.key ||
    "";
  const selectedEntry = catalog.find((m) => m.key === activeKey);

  useEffect(() => {
    if (!running) return;
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
        if (!prog.running) {
          onRefresh();
        }
      } catch {
        /* ignore poll errors */
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [running, onRefresh]);

  useEffect(() => {
    if (!failed && !running) return;
    void fetchSmartSetupProgress().then((prog) => {
      setInstructions(prog.instructions?.steps ?? []);
      setInstructionSummary(String(prog.instructions?.summary ?? ""));
    });
  }, [failed, running]);

  const handleContinue = () => {
    if (voice !== "ollama") {
      onRun({ force_high_tier: forceHighTier, pull_extra_models: pullExtraModels, voice_provider: voice });
    }
    onContinue();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto max-w-xl p-2 md:p-4"
    >
      <h2 className="mb-2 text-lg font-semibold">How LUMINA is wired</h2>
      <p className="mb-6 text-sm text-muted-foreground">
        Two organs. The training engine learns trades. The thinking assistant talks. They are not
        alternatives.
      </p>

      <section className={cn("mb-4 rounded-lg border border-white/10 p-4", luminaSurfaceMutedClass(""))}>
        <h3 className="text-sm font-semibold">How LUMINA learns trades</h3>
        <p className="mt-2 text-sm">{view.lungsStatus}</p>
        <p className="mt-2 text-xs text-muted-foreground">{CUDA_GLOSS}</p>
        {view.lungsNextAction && (
          <div className="mt-3">
            <p className="text-xs text-muted-foreground">
              Does not install the talking assistant.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 overflow-x-auto rounded bg-black/40 px-2 py-1 text-[11px] text-cyan-100/90">
                {view.lungsNextAction}
              </code>
              <Button type="button" variant="outline" size="sm" onClick={() => copyCommand(view.lungsNextAction!)}>
                Copy
              </Button>
            </div>
          </div>
        )}
      </section>

      <section className={cn("mb-4 rounded-lg border border-white/10 p-4", luminaSurfaceMutedClass(""))}>
        <h3 className="text-sm font-semibold">How LUMINA reads and explains</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Not needed to start learning. News reading uses this assistant later and never places orders.
        </p>
        <div className="mt-3 space-y-2">
          {view.voiceChoices.map((choice) => {
            const selected = voice === choice.id;
            return (
              <label
                key={choice.id}
                className={cn(
                  "block rounded-lg border px-3 py-3 text-sm",
                  selected ? "border-cyan-400/45 bg-cyan-400/10" : "border-white/10",
                  !choice.enabled && "opacity-60",
                )}
              >
                <span className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="voice-provider"
                    checked={selected}
                    disabled={!choice.enabled}
                    onChange={() => setVoice(choice.id as VoiceChoiceId)}
                  />
                  <span className="font-medium">{choice.label}</span>
                </span>
                <p className="mt-1 text-xs text-muted-foreground">{choice.help}</p>
                {selected && (
                  <p className="mt-1 text-xs text-cyan-100/80">{choice.consequence_if_yes}</p>
                )}
              </label>
            );
          })}
        </div>
        {!view.showVllmOption && (
          <p className="mt-2 text-xs text-muted-foreground">
            Extra-fast local assistant (vLLM) is not available on this Windows PC.
          </p>
        )}
      </section>

      <section className={cn("mb-4 rounded-lg border border-white/10 p-4", luminaSurfaceMutedClass(""))}>
        <h3 className="text-sm font-semibold">What happens next</h3>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-sm">
          {view.nextSteps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
        <p className="mt-2 text-sm font-medium">Learning to trade does not wait for the assistant.</p>
        <p className="mt-1 text-xs text-muted-foreground">{view.newsStatus}</p>
      </section>

      {view.showCatalog && catalog.length > 0 && (
        <div className="mb-6">
          <label className="mb-2 block text-xs tracking-wider text-muted-foreground uppercase">
            Local talking model
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
                      Heavier than your current hardware — may run slowly.
                    </p>
                  )}
                </button>
              );
            })}
          </div>
          {selectedEntry && (
            <p className="mt-2 text-xs text-muted-foreground">
              Selected: {selectedEntry.display_name} ({selectedEntry.recommended_tier} tier). Size
              unknown — check the model card if the catalog does not list download size.
            </p>
          )}
        </div>
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

      {(failed || (!running && instructions.length > 0)) && (
        <div className="mb-6 rounded-lg border border-white/10 p-4">
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
                    <Button type="button" variant="outline" size="sm" onClick={() => copyCommand(step.command!)}>
                      Copy
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-4 space-y-2 text-sm">
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-1"
            checked={forceHighTier}
            onChange={(e) => setForceHighTier(e.target.checked)}
          />
          <span>
            Larger local talking model
            <span className="block text-xs text-muted-foreground">{view.forceHighHelp}</span>
          </span>
        </label>
        {view.showInstall && (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={pullExtraModels}
              onChange={(e) => setPullExtraModels(e.target.checked)}
            />
            Download extra recommended talking models
          </label>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        {view.showInstall && (
          <Button
            className="onboarding-cta"
            onClick={() =>
              onRun({ force_high_tier: forceHighTier, pull_extra_models: pullExtraModels, voice_provider: voice })
            }
            disabled={running || !activeKey}
          >
            {running ? "Installing…" : "Install local assistant"}
          </Button>
        )}
        <Button className="onboarding-cta" onClick={handleContinue} disabled={running}>
          Continue
        </Button>
      </div>
    </motion.div>
  );
}
