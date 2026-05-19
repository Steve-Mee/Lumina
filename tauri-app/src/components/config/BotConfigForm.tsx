import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  applyPaperModePreset,
  applyRealModePreset,
  applySimModePreset,
  type BotConfigDraft,
  type MutationDepth,
} from "@/lib/botConfigDraft";
import { cn } from "@/lib/utils";

interface BotConfigFormProps {
  draft: BotConfigDraft;
  onChange: (patch: Partial<BotConfigDraft>) => void;
  showModeCallout?: boolean;
  operatorMode?: "SIM" | "REAL";
  className?: string;
}

const MUTATION_OPTIONS: { value: MutationDepth; label: string; hint: string }[] = [
  { value: "conservative", label: "Conservative", hint: "Minimal hyperparameter drift" },
  { value: "moderate", label: "Moderate", hint: "Balanced exploration" },
  { value: "radical", label: "Radical", hint: "SIM only — deep mutations" },
];

function patchDraft(
  draft: BotConfigDraft,
  patch: Partial<BotConfigDraft>,
): BotConfigDraft {
  return {
    ...draft,
    ...patch,
    risk: { ...draft.risk, ...(patch.risk ?? {}) },
    evolution: { ...draft.evolution, ...(patch.evolution ?? {}) },
  };
}

export function BotConfigForm({
  draft,
  onChange,
  showModeCallout = false,
  operatorMode,
  className,
}: BotConfigFormProps) {
  const [realConfirmOpen, setRealConfirmOpen] = useState(false);
  const isReal = draft.mode === "real";
  const simRealGuard = draft.mode === "sim_real_guard";
  const primaryMode: "paper" | "sim" | "real" =
    draft.mode === "paper" ? "paper" : draft.mode === "real" ? "real" : "sim";

  const handleModeSelect = (mode: "paper" | "sim" | "real") => {
    if (mode === "real") {
      setRealConfirmOpen(true);
      return;
    }
    if (mode === "paper") {
      onChange(applyPaperModePreset(draft));
      return;
    }
    onChange(simRealGuard ? { ...applySimModePreset(draft), mode: "sim_real_guard" } : applySimModePreset(draft));
  };

  const confirmReal = () => {
    onChange(applyRealModePreset(draft));
    setRealConfirmOpen(false);
  };

  const setMutationDepth = (depth: MutationDepth) => {
    if (isReal && depth === "radical") {
      return;
    }
    onChange({
      evolution: { ...draft.evolution, max_mutation_depth: depth },
    });
  };

  return (
    <>
      <div className={cn("bot-config-form space-y-6", className)}>
        {showModeCallout && operatorMode ? (
          <div className="rounded-md border border-cyan-500/20 bg-cyan-950/20 px-3 py-2 text-[11px] text-cyan-100/80">
            <p>
              <span className="font-mono text-cyan-200">HUD mode:</span> {operatorMode} (runtime)
            </p>
            <p className="mt-1">
              <span className="font-mono text-cyan-200">Target mode:</span>{" "}
              {draft.mode.toUpperCase()} (saved to config.yaml)
            </p>
          </div>
        ) : null}

        <section>
          <h3 className="bot-config-section-title">Target operations mode</h3>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {(["paper", "sim", "real"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => handleModeSelect(mode)}
                className={cn(
                  "rounded-lg border px-3 py-2.5 text-sm font-semibold tracking-wider uppercase transition-all",
                  primaryMode === mode
                    ? mode === "real"
                      ? "border-amber-500/50 bg-amber-500/10 text-amber-200"
                      : mode === "paper"
                        ? "border-violet-400/50 bg-violet-500/10 text-violet-200"
                        : "border-cyan-400/50 bg-cyan-400/10 text-cyan-200"
                    : "border-white/10 bg-black/20 text-muted-foreground hover:border-white/20",
                )}
              >
                {mode}
              </button>
            ))}
          </div>
          {primaryMode === "sim" ? (
            <label className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={simRealGuard}
                onChange={(e) =>
                  onChange({
                    ...draft,
                    mode: e.target.checked ? "sim_real_guard" : "sim",
                  })
                }
              />
              <span>
                Use <span className="font-mono text-cyan-200/80">sim_real_guard</span> — REAL-limited
                SIM with extra capital protection (matches Streamlit advanced mode).
              </span>
            </label>
          ) : null}
        </section>

        <section>
          <h3 className="bot-config-section-title">Risk parameters</h3>
          <div className="mt-3 space-y-4">
            <ConfigRange
              label="Kelly fraction"
              value={draft.risk.kelly_fraction}
              min={0.05}
              max={1}
              step={0.05}
              format={(v) => v.toFixed(2)}
              onChange={(kelly_fraction) => onChange({ risk: { ...draft.risk, kelly_fraction } })}
            />
            <ConfigRange
              label="Daily loss cap (USD)"
              value={draft.risk.daily_loss_cap ?? 0}
              min={-500}
              max={0}
              step={10}
              format={(v) => (v === 0 && draft.risk.daily_loss_cap === null ? "None" : `$${v}`)}
              onChange={(daily_loss_cap) =>
                onChange({
                  risk: {
                    ...draft.risk,
                    daily_loss_cap: daily_loss_cap === 0 ? null : daily_loss_cap,
                  },
                })
              }
            />
            <ConfigRange
              label="Max total open risk (USD)"
              value={draft.risk.max_total_open_risk}
              min={50}
              max={5000}
              step={50}
              format={(v) => `$${v}`}
              onChange={(max_total_open_risk) =>
                onChange({ risk: { ...draft.risk, max_total_open_risk } })
              }
            />
          </div>
        </section>

        <section>
          <h3 className="bot-config-section-title">Capital allocation</h3>
          <div className="mt-3">
            <ConfigRange
              label="Capital safety threshold (USD)"
              value={draft.risk.real_capital_safety_threshold_usd}
              min={100}
              max={10000}
              step={100}
              format={(v) => `$${v}`}
              onChange={(real_capital_safety_threshold_usd) =>
                onChange({ risk: { ...draft.risk, real_capital_safety_threshold_usd } })
              }
            />
          </div>
        </section>

        <section>
          <h3 className="bot-config-section-title">Evolution aggressiveness</h3>
          <label className="mt-3 flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={draft.evolution.aggressive_evolution}
              onChange={(e) =>
                onChange({
                  evolution: { ...draft.evolution, aggressive_evolution: e.target.checked },
                })
              }
            />
            <span>
              Aggressive evolution
              {isReal ? (
                <span className="block text-[11px] text-amber-300/80">Not recommended for REAL</span>
              ) : null}
            </span>
          </label>
        </section>

        <section>
          <h3 className="bot-config-section-title">Mutation governance</h3>
          <div className="mt-2 grid gap-2">
            {MUTATION_OPTIONS.map((option) => {
              const disabled = isReal && option.value === "radical";
              const active = draft.evolution.max_mutation_depth === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={disabled}
                  onClick={() => setMutationDepth(option.value)}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-left transition-colors",
                    active
                      ? "border-violet-400/40 bg-violet-500/10"
                      : "border-white/10 bg-black/20 hover:border-white/20",
                    disabled && "cursor-not-allowed opacity-40",
                  )}
                >
                  <p className="font-mono text-xs text-foreground">{option.label}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">{option.hint}</p>
                </button>
              );
            })}
          </div>
        </section>

        <section>
          <h3 className="bot-config-section-title">Human approval</h3>
          <label className="mt-3 flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={draft.evolution.approval_required}
              onChange={(e) =>
                onChange({
                  evolution: { ...draft.evolution, approval_required: e.target.checked },
                })
              }
            />
            <span>
              Require operator approval for mutations
              <span className="block text-[11px] text-muted-foreground">
                Approve or reject from Decision Theater and Evolution deck
              </span>
            </span>
          </label>
        </section>

        <section>
          <h3 className="bot-config-section-title">Runtime preferences</h3>
          <div className="mt-3 space-y-3">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground uppercase">Instrument</label>
              <select
                className="onboarding-field w-full font-mono"
                value={draft.preferences.instrument}
                onChange={(e) =>
                  onChange({ preferences: { ...draft.preferences, instrument: e.target.value } })
                }
              >
                {["ES", "NQ", "YM", "RTY", "CL", "GC"].map((symbol) => (
                  <option key={symbol} value={symbol}>
                    {symbol}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={draft.preferences.voice_enabled}
                onChange={(e) =>
                  onChange({
                    preferences: { ...draft.preferences, voice_enabled: e.target.checked },
                  })
                }
              />
              <span>Voice (TTS + input)</span>
            </label>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={draft.preferences.screen_share_enabled}
                onChange={(e) =>
                  onChange({
                    preferences: { ...draft.preferences, screen_share_enabled: e.target.checked },
                  })
                }
              />
              <span>Live chart screen share</span>
            </label>
          </div>
        </section>
      </div>

      <Dialog open={realConfirmOpen} onOpenChange={setRealConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enable REAL target mode?</DialogTitle>
            <DialogDescription>
              REAL configuration applies stricter risk caps and disables radical mutations.
              Runtime HUD mode is separate until the engine reloads config.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRealConfirmOpen(false)}>
              Cancel
            </Button>
            <Button onClick={confirmReal}>Confirm REAL</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ConfigRange({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
        <span>{label}</span>
        <span>{format(value)}</span>
      </label>
      <input
        type="range"
        className="config-range w-full"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

export { patchDraft };
