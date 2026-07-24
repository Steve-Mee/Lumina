import { useMemo, useState, type ReactNode } from "react";

import { HelpTip } from "@/components/ui/HelpTip";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  applyPaperModePreset,
  applyRealModePreset,
  applySimModePreset,
  type BotConfigDraft,
  type MutationDepth,
} from "@/lib/botConfigDraft";
import { CONSEQUENCE_HINTS, helpFor } from "@/lib/helpTexts";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import {
  FULL_SIZE_INSTRUMENTS,
  INSTRUMENT_LEGEND,
  MICRO_INSTRUMENTS,
  findInstrument,
  normalizeInstrumentRoot,
} from "@/lib/instrumentsCatalog";
import { realBadgeClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

export type BotConfigFormVariant = "deck" | "dialog";

interface BotConfigFormProps {
  draft: BotConfigDraft;
  onChange: (patch: Partial<BotConfigDraft>) => void;
  showModeCallout?: boolean;
  operatorMode?: "SIM" | "REAL";
  /** deck = tabbed glass form (onboarding); dialog = compact tabbed form (settings). */
  variant?: BotConfigFormVariant;
  className?: string;
}

const MUTATION_OPTIONS: {
  value: MutationDepth;
  label: string;
  hint: string;
  risk: string;
}[] = [
  {
    value: "conservative",
    label: "Conservative",
    hint: "Minimal hyperparameter drift",
    risk: "Slowest learning, safest policy steps.",
  },
  {
    value: "moderate",
    label: "Moderate",
    hint: "Balanced exploration",
    risk: "Default middle ground for controlled growth.",
  },
  {
    value: "radical",
    label: "Radical",
    hint: "SIM only — deep mutations",
    risk: "Fastest change; constitution blocks this in REAL.",
  },
];

const MODE_CARDS: {
  mode: "paper" | "sim" | "real";
  title: string;
  blurb: string;
  consequence: string;
  tipKey: string;
}[] = [
  {
    mode: "paper",
    title: "Paper",
    blurb: "Broker paper / practice account",
    consequence: CONSEQUENCE_HINTS.paper_path,
    tipKey: "config_paper",
  },
  {
    mode: "sim",
    title: "Sim",
    blurb: "Internal simulation — recommended first boot",
    consequence: CONSEQUENCE_HINTS.sim_loose,
    tipKey: "config_sim",
  },
  {
    mode: "real",
    title: "Real",
    blurb: "Live capital target (post-maturity)",
    consequence: CONSEQUENCE_HINTS.real_target,
    tipKey: "config_real",
  },
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

function FieldCard({
  label,
  tip,
  hint,
  children,
  className,
}: {
  label: string;
  tip?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("risk-envelope-field-card", className)}>
      <div className="mb-1 flex items-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      {children}
      {hint ? <p className="risk-envelope-field-hint">{hint}</p> : null}
    </div>
  );
}

function ToggleRow({
  label,
  tip,
  hint,
  checked,
  onChange,
  warn,
}: {
  label: string;
  tip?: string;
  hint?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  warn?: string | null;
}) {
  return (
    <label className="risk-envelope-toggle-row">
      <input
        type="checkbox"
        className="mt-0.5 size-3.5 shrink-0 accent-cyan-400"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="text-sm text-foreground/90">{label}</span>
          {tip ? <HelpTip text={tip} /> : null}
        </span>
        {hint ? <span className="mt-0.5 block text-[11px] text-muted-foreground">{hint}</span> : null}
        {warn ? <span className="mt-0.5 block text-[11px] text-amber-300/85">{warn}</span> : null}
      </span>
    </label>
  );
}

function kellyConsequence(kelly: number, isReal: boolean): string {
  if (isReal) {
    return kelly <= 0.25
      ? CONSEQUENCE_HINTS.kelly_real_safe
      : CONSEQUENCE_HINTS.kelly_real_hot;
  }
  if (kelly >= 0.75) return CONSEQUENCE_HINTS.kelly_high;
  if (kelly <= 0.25) return "Low Kelly — small size, slower growth, shallower drawdowns.";
  return "Balanced Kelly — size scales with edge confidence.";
}

function dailyCapConsequence(cap: number | null): string {
  if (cap == null || cap === 0) return CONSEQUENCE_HINTS.daily_none;
  return CONSEQUENCE_HINTS.daily_on;
}

function openRiskConsequence(value: number, isReal: boolean): string {
  if (isReal && value <= 200) return CONSEQUENCE_HINTS.open_risk_tight;
  if (value >= 2500) return CONSEQUENCE_HINTS.open_risk_high;
  return CONSEQUENCE_HINTS.open_risk_tight;
}

export function envelopeSummaryLine(draft: BotConfigDraft): string {
  const cap =
    draft.risk.daily_loss_cap == null ? "None" : `$${draft.risk.daily_loss_cap}`;
  return [
    `Mode ${draft.mode.toUpperCase()}`,
    `Kelly ${draft.risk.kelly_fraction.toFixed(2)}`,
    `Day cap ${cap}`,
    `Open $${draft.risk.max_total_open_risk}`,
    `Mut ${draft.evolution.max_mutation_depth}`,
    draft.evolution.approval_required ? "Approval ON" : "Approval OFF",
  ].join(" · ");
}

export function envelopeConsequenceLine(draft: BotConfigDraft): string {
  if (draft.mode === "real") return CONSEQUENCE_HINTS.real_target;
  if (draft.mode === "paper") return CONSEQUENCE_HINTS.paper_path;
  if (draft.mode === "sim_real_guard") {
    return "SIM with REAL-like guards — still no live capital; tighter rehearsal.";
  }
  if (
    draft.risk.daily_loss_cap == null &&
    draft.risk.kelly_fraction >= 0.75 &&
    draft.evolution.max_mutation_depth === "radical"
  ) {
    return CONSEQUENCE_HINTS.sim_loose;
  }
  return "Envelope set — Birth stays SIM until you graduate to live capital.";
}

export type EnvelopeChipState = "idle" | "ok" | "partial" | "fail" | "warn";

export function resolveEnvelopeChips(draft: BotConfigDraft): {
  mode: EnvelopeChipState;
  risk: EnvelopeChipState;
  evolution: EnvelopeChipState;
  birth: EnvelopeChipState;
} {
  const isReal = draft.mode === "real";
  const looseSim =
    !isReal &&
    draft.risk.kelly_fraction >= 0.75 &&
    draft.risk.daily_loss_cap == null;

  let risk: EnvelopeChipState = "ok";
  if (isReal) {
    const hot =
      draft.risk.kelly_fraction > 0.25 ||
      draft.risk.daily_loss_cap == null ||
      draft.risk.max_total_open_risk > 500;
    risk = hot ? "warn" : "ok";
  } else if (looseSim) {
    risk = "partial";
  }

  let evolution: EnvelopeChipState = "ok";
  if (isReal && draft.evolution.max_mutation_depth === "radical") {
    evolution = "fail";
  } else if (
    draft.evolution.aggressive_evolution ||
    draft.evolution.max_mutation_depth === "radical"
  ) {
    evolution = draft.evolution.approval_required ? "partial" : "warn";
  } else if (!draft.evolution.approval_required) {
    evolution = "partial";
  }

  return {
    mode: isReal ? "warn" : draft.mode === "sim_real_guard" ? "partial" : "ok",
    risk,
    evolution,
    birth: "ok",
  };
}

export function BotConfigForm({
  draft,
  onChange,
  showModeCallout = false,
  operatorMode,
  variant = "dialog",
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
    onChange(
      simRealGuard
        ? { ...applySimModePreset(draft), mode: "sim_real_guard" }
        : applySimModePreset(draft),
    );
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

  const tabShell = variant === "deck" ? "risk-envelope-tabs" : "bot-config-tabs";
  const tabListClass =
    variant === "deck"
      ? "risk-envelope-tab-list risk-envelope-tab-list--4"
      : "bot-config-tab-list";
  const tabBodyClass =
    variant === "deck" ? "risk-envelope-tab-body" : "bot-config-tab-body";
  const tabContentClass =
    variant === "deck" ? "risk-envelope-tab-content" : "bot-config-tab-content";

  const summary = useMemo(() => envelopeSummaryLine(draft), [draft]);
  const consequence = useMemo(() => envelopeConsequenceLine(draft), [draft]);

  return (
    <>
      <div
        className={cn(
          "bot-config-form",
          variant === "deck" && "bot-config-form--deck",
          className,
        )}
      >
        {showModeCallout && operatorMode ? (
          <div className="risk-envelope-banner risk-envelope-banner--info mb-3">
            <p>
              <span className="font-mono text-cyan-200">HUD mode:</span> {operatorMode}{" "}
              (runtime)
            </p>
            <p className="mt-1">
              <span className="font-mono text-cyan-200">Target mode:</span>{" "}
              {draft.mode.toUpperCase()} (saved to config.yaml)
            </p>
          </div>
        ) : null}

        {variant === "dialog" ? (
          <div className="risk-envelope-summary mb-3" title={helpFor("config_envelope_summary")}>
            <p className="risk-envelope-summary__line font-mono">{summary}</p>
            <p className="risk-envelope-summary__consequence">{consequence}</p>
          </div>
        ) : null}

        <Tabs defaultValue="profile" className={tabShell}>
          <TabsList className={tabListClass}>
            <TabsTrigger value="profile">Profile</TabsTrigger>
            <TabsTrigger value="envelope">Envelope</TabsTrigger>
            <TabsTrigger value="evolution">Evolution</TabsTrigger>
            <TabsTrigger value="operator">Operator</TabsTrigger>
          </TabsList>

          <div className={tabBodyClass}>
            <TabsContent value="profile" className={tabContentClass}>
              <div className="mb-1 flex items-center gap-1.5">
                <h3 className="bot-config-section-title mb-0">Target operations mode</h3>
                <HelpTip text={helpFor("config_target_mode") ?? ""} />
              </div>
              <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
                Choose where this profile is aimed. During Birth the engine stays{" "}
                <strong className="text-cyan-300/90">SIM</strong> (fail-closed). This is
                your <em>target</em> after maturity gates — not live capital right now.
              </p>

              <div className="risk-envelope-mode-grid">
                {MODE_CARDS.map((card) => {
                  const active = primaryMode === card.mode;
                  return (
                    <button
                      key={card.mode}
                      type="button"
                      onClick={() => handleModeSelect(card.mode)}
                      title={helpFor(card.tipKey)}
                      className={cn(
                        "risk-envelope-mode-card",
                        active && "risk-envelope-mode-card--active",
                        active && card.mode === "real" && "risk-envelope-mode-card--real",
                        active && card.mode === "paper" && "risk-envelope-mode-card--paper",
                        active && card.mode === "sim" && "risk-envelope-mode-card--sim",
                        !active &&
                          luminaSurfaceMutedClass(
                            "border border-white/10 text-muted-foreground hover:border-white/20",
                          ),
                        active &&
                          card.mode === "real" &&
                          cn(realBadgeClass(), "border-transparent"),
                      )}
                      aria-pressed={active}
                    >
                      <span className="risk-envelope-mode-card__title">{card.title}</span>
                      <span className="risk-envelope-mode-card__blurb">{card.blurb}</span>
                      <span className="risk-envelope-mode-card__risk">{card.consequence}</span>
                    </button>
                  );
                })}
              </div>

              {primaryMode === "sim" ? (
                <FieldCard
                  label="SIM real-guard"
                  tip={helpFor("config_sim_real_guard")}
                  hint="Still no live capital — extra brakes that mimic REAL risk discipline."
                  className="mt-3"
                >
                  <ToggleRow
                    label="Use sim_real_guard"
                    checked={simRealGuard}
                    onChange={(checked) =>
                      onChange({
                        ...draft,
                        mode: checked ? "sim_real_guard" : "sim",
                      })
                    }
                    hint="REAL-limited SIM with extra capital protection (matches advanced mode)."
                  />
                </FieldCard>
              ) : null}

              <FieldCard
                label="Primary instrument"
                tip={helpFor("config_instrument")}
                hint={
                  findInstrument(draft.preferences.instrument)?.note ??
                  "Root symbol for runtime · front-month resolved on NinjaTrader."
                }
                className="mt-3"
              >
                <p className="mb-2 text-[10px] leading-relaxed text-muted-foreground">
                  {INSTRUMENT_LEGEND}
                </p>
                <label className="mb-1 block font-mono text-[0.5rem] tracking-[0.12em] text-cyan-400/70 uppercase">
                  Recommended micros
                </label>
                <select
                  className="onboarding-field w-full font-mono"
                  value={normalizeInstrumentRoot(draft.preferences.instrument)}
                  onChange={(e) =>
                    onChange({
                      preferences: {
                        ...draft.preferences,
                        instrument: normalizeInstrumentRoot(e.target.value),
                      },
                    })
                  }
                >
                  <optgroup label="Micros (recommended)">
                    {MICRO_INSTRUMENTS.map((item) => (
                      <option key={item.root} value={item.root}>
                        {item.root} — {item.name}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Full-size CME (higher $ risk)">
                    {FULL_SIZE_INSTRUMENTS.map((item) => (
                      <option key={item.root} value={item.root}>
                        {item.root} — {item.name}
                      </option>
                    ))}
                  </optgroup>
                </select>
                {findInstrument(draft.preferences.instrument)?.tier === "full" ? (
                  <p className="mt-2 text-[10px] leading-relaxed text-amber-300/85">
                    Full-size contract — roughly 10× micro notional. Prefer MES/MNQ until
                    apprenticeship is proven.
                  </p>
                ) : null}
                <p className="mt-1.5 text-[10px] text-muted-foreground">
                  Platforms:{" "}
                  {findInstrument(draft.preferences.instrument)?.platforms ??
                    "NinjaTrader 8 + Fabric"}
                </p>
              </FieldCard>
            </TabsContent>

            <TabsContent value="envelope" className={tabContentClass}>
              <div className="mb-1 flex items-center gap-1.5">
                <h3 className="bot-config-section-title mb-0">Risk envelope</h3>
                <HelpTip text={helpFor("config_envelope_summary") ?? ""} />
              </div>
              <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
                These numbers define how much capital the system may put at risk. Tighter
                is safer. Loose SIM envelopes are for learning — never copy them blindly
                into REAL.
              </p>

              <div className="space-y-3">
                <FieldCard
                  label="Kelly fraction"
                  tip={helpFor("kelly_fraction")}
                  hint={kellyConsequence(draft.risk.kelly_fraction, isReal)}
                >
                  <ConfigRange
                    label="Kelly fraction"
                    hideLabel
                    value={draft.risk.kelly_fraction}
                    min={0.05}
                    max={1}
                    step={0.05}
                    format={(v) => v.toFixed(2)}
                    onChange={(kelly_fraction) =>
                      onChange({ risk: { ...draft.risk, kelly_fraction } })
                    }
                    hot={isReal ? draft.risk.kelly_fraction > 0.25 : draft.risk.kelly_fraction >= 0.85}
                  />
                </FieldCard>

                <FieldCard
                  label="Daily loss cap (USD)"
                  tip={helpFor("daily_loss_cap")}
                  hint={dailyCapConsequence(draft.risk.daily_loss_cap)}
                >
                  <ConfigRange
                    label="Daily loss cap"
                    hideLabel
                    value={draft.risk.daily_loss_cap ?? 0}
                    min={-500}
                    max={0}
                    step={10}
                    format={(v) =>
                      v === 0 && draft.risk.daily_loss_cap === null ? "None" : `$${v}`
                    }
                    onChange={(daily_loss_cap) =>
                      onChange({
                        risk: {
                          ...draft.risk,
                          daily_loss_cap: daily_loss_cap === 0 ? null : daily_loss_cap,
                        },
                      })
                    }
                    hot={isReal && draft.risk.daily_loss_cap == null}
                  />
                </FieldCard>

                <FieldCard
                  label="Max total open risk (USD)"
                  tip={helpFor("max_total_open_risk")}
                  hint={openRiskConsequence(draft.risk.max_total_open_risk, isReal)}
                >
                  <ConfigRange
                    label="Max total open risk"
                    hideLabel
                    value={draft.risk.max_total_open_risk}
                    min={50}
                    max={5000}
                    step={50}
                    format={(v) => `$${v}`}
                    onChange={(max_total_open_risk) =>
                      onChange({ risk: { ...draft.risk, max_total_open_risk } })
                    }
                    hot={draft.risk.max_total_open_risk >= 3000}
                  />
                </FieldCard>

                <FieldCard
                  label="Capital safety threshold (USD)"
                  tip={helpFor("real_capital_safety_threshold")}
                  hint={CONSEQUENCE_HINTS.capital_floor}
                >
                  <ConfigRange
                    label="Capital safety threshold"
                    hideLabel
                    value={draft.risk.real_capital_safety_threshold_usd}
                    min={100}
                    max={10000}
                    step={100}
                    format={(v) => `$${v}`}
                    onChange={(real_capital_safety_threshold_usd) =>
                      onChange({
                        risk: { ...draft.risk, real_capital_safety_threshold_usd },
                      })
                    }
                  />
                </FieldCard>
              </div>

              {isReal ? (
                <div className="risk-envelope-banner risk-envelope-banner--real mt-3" role="status">
                  <p className="font-mono text-[0.55rem] tracking-[0.14em] uppercase text-rose-200/90">
                    REAL target armed
                  </p>
                  <p className="mt-1 text-[11px] leading-relaxed text-rose-100/75">
                    Live capital only after maturity gates. Expect quarter-Kelly, daily
                    hard stop, tight open risk, no radical mutations, and approval on.
                  </p>
                </div>
              ) : null}
            </TabsContent>

            <TabsContent value="evolution" className={tabContentClass}>
              <div className="mb-1 flex items-center gap-1.5">
                <h3 className="bot-config-section-title mb-0">Evolution governance</h3>
                <HelpTip text={helpFor("max_mutation_depth") ?? ""} />
              </div>
              <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
                How hard the organism may rewrite itself — and whether you hold the
                final key. Agents propose; you (or Final Arbitration) decide.
              </p>

              <FieldCard
                label="Aggressive evolution"
                tip={helpFor("aggressive_evolution")}
                hint={
                  isReal
                    ? "Not recommended for REAL — prefer stable, approved steps."
                    : "Faster exploration in SIM; pair with approval if you want control."
                }
              >
                <ToggleRow
                  label="Enable aggressive evolution"
                  checked={draft.evolution.aggressive_evolution}
                  onChange={(aggressive_evolution) =>
                    onChange({
                      evolution: { ...draft.evolution, aggressive_evolution },
                    })
                  }
                  warn={
                    isReal && draft.evolution.aggressive_evolution
                      ? "Aggressive evolution + REAL target is high risk."
                      : null
                  }
                />
              </FieldCard>

              <FieldCard
                label="Mutation depth"
                tip={helpFor("max_mutation_depth")}
                className="mt-3"
              >
                <div className="mt-1 grid gap-2">
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
                          "risk-envelope-mutation-card",
                          active && "risk-envelope-mutation-card--active",
                          disabled && "cursor-not-allowed opacity-40",
                          !active &&
                            !disabled &&
                            luminaSurfaceMutedClass(
                              "border border-white/10 hover:border-white/20",
                            ),
                        )}
                        aria-pressed={active}
                      >
                        <p className="font-mono text-xs text-foreground">{option.label}</p>
                        <p className="mt-0.5 text-[10px] text-muted-foreground">
                          {option.hint}
                        </p>
                        <p className="mt-1 text-[10px] text-cyan-200/55">{option.risk}</p>
                        {disabled ? (
                          <p className="mt-1 text-[10px] text-rose-300/80">
                            {CONSEQUENCE_HINTS.radical_blocked}
                          </p>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              </FieldCard>

              <FieldCard
                label="Human approval"
                tip={helpFor("approval_required")}
                hint={
                  draft.evolution.approval_required
                    ? CONSEQUENCE_HINTS.approval_on
                    : CONSEQUENCE_HINTS.approval_off
                }
                className="mt-3"
              >
                <ToggleRow
                  label="Require operator approval for mutations"
                  checked={draft.evolution.approval_required}
                  onChange={(approval_required) =>
                    onChange({
                      evolution: { ...draft.evolution, approval_required },
                    })
                  }
                  hint="Approve or reject from Decision Theater and Evolution deck."
                />
              </FieldCard>
            </TabsContent>

            <TabsContent value="operator" className={tabContentClass}>
              <div className="mb-1 flex items-center gap-1.5">
                <h3 className="bot-config-section-title mb-0">Operator preferences</h3>
              </div>
              <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
                Comfort and diagnostics only — these do not change the risk envelope or
                place capital at risk.
              </p>

              <FieldCard label="Comfort">
                <div className="space-y-2">
                  <ToggleRow
                    label="Voice (TTS + input)"
                    tip={helpFor("config_voice_enabled")}
                    checked={draft.preferences.voice_enabled}
                    onChange={(voice_enabled) =>
                      onChange({
                        preferences: { ...draft.preferences, voice_enabled },
                      })
                    }
                  />
                  <ToggleRow
                    label="Live chart screen share"
                    tip={helpFor("config_screen_share")}
                    checked={draft.preferences.screen_share_enabled}
                    onChange={(screen_share_enabled) =>
                      onChange({
                        preferences: { ...draft.preferences, screen_share_enabled },
                      })
                    }
                  />
                </div>
              </FieldCard>

              <FieldCard label="Diagnostics" className="mt-3">
                <div className="space-y-3">
                  <ToggleRow
                    label="Dashboard feedback paths"
                    tip={helpFor("dashboard_enabled")}
                    checked={draft.preferences.dashboard_enabled}
                    onChange={(dashboard_enabled) =>
                      onChange({
                        preferences: { ...draft.preferences, dashboard_enabled },
                      })
                    }
                  />
                  <ToggleRow
                    label="Runtime trace"
                    tip={helpFor("runtime_trace")}
                    checked={draft.preferences.runtime_trace}
                    onChange={(runtime_trace) =>
                      onChange({
                        preferences: { ...draft.preferences, runtime_trace },
                      })
                    }
                  />
                  <div>
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1.5 font-mono text-[0.55rem] tracking-wide text-muted-foreground uppercase">
                        Runtime trace interval
                        <HelpTip text={helpFor("runtime_trace_interval") ?? ""} />
                      </span>
                      <span className="font-mono text-xs text-cyan-200/80">
                        {draft.preferences.runtime_trace_interval_sec}s
                      </span>
                    </div>
                    <ConfigRange
                      label="Runtime trace interval"
                      hideLabel
                      value={draft.preferences.runtime_trace_interval_sec}
                      min={0}
                      max={10}
                      step={1}
                      format={(v) => `${v}s`}
                      onChange={(v) =>
                        onChange({
                          preferences: {
                            ...draft.preferences,
                            runtime_trace_interval_sec: v,
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1.5 font-mono text-[0.55rem] tracking-wide text-muted-foreground uppercase">
                        Latency SLA
                        <HelpTip text={helpFor("latency_sla") ?? ""} />
                      </span>
                      <span className="font-mono text-xs text-cyan-200/80">
                        {draft.preferences.latency_sla_ms} ms
                      </span>
                    </div>
                    <ConfigRange
                      label="Latency SLA"
                      hideLabel
                      value={draft.preferences.latency_sla_ms}
                      min={150}
                      max={1000}
                      step={50}
                      format={(v) => `${v} ms`}
                      onChange={(v) =>
                        onChange({
                          preferences: { ...draft.preferences, latency_sla_ms: v },
                        })
                      }
                    />
                  </div>
                </div>
              </FieldCard>
            </TabsContent>
          </div>
        </Tabs>
      </div>

      <Dialog open={realConfirmOpen} onOpenChange={setRealConfirmOpen}>
        <DialogContent className="border-rose-500/30 bg-[color-mix(in_srgb,var(--lumina-void)_92%,#2a1018)]">
          <DialogHeader>
            <DialogTitle className="text-rose-100">Enable REAL target mode?</DialogTitle>
            <DialogDescription className="space-y-3 text-rose-100/70">
              <span className="block">
                You are setting a <strong className="text-rose-100">live capital target</strong>{" "}
                in config.yaml. Birth runtime remains SIM until maturity gates pass. Confirming
                applies the REAL safety preset:
              </span>
              <ul className="list-disc space-y-1.5 pl-4 text-left text-[12px] leading-relaxed">
                <li>Kelly fraction forced toward quarter-Kelly (0.25)</li>
                <li>Daily loss hard stop armed (e.g. −$150)</li>
                <li>Max open risk tightened (e.g. $150)</li>
                <li>Radical mutations disabled — constitution enforces this live</li>
                <li>Operator approval required for mutations</li>
                <li>Aggressive evolution turned off</li>
              </ul>
              <span className="block text-[11px] text-rose-200/60">
                Runtime HUD mode is separate until the engine reloads config. Wrong settings
                here can put real money at risk after promotion — capital preservation first.
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRealConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              className="bg-rose-600/90 text-white hover:bg-rose-500"
              onClick={confirmReal}
            >
              Confirm REAL target
            </Button>
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
  hideLabel = false,
  hot = false,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
  hideLabel?: boolean;
  hot?: boolean;
}) {
  const pct = max === min ? 0 : ((value - min) / (max - min)) * 100;

  return (
    <div className={cn("risk-envelope-slider", hot && "risk-envelope-slider--hot")}>
      {!hideLabel ? (
        <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
          <span>{label}</span>
          <span className={cn("font-mono", hot && "text-amber-300")}>{format(value)}</span>
        </label>
      ) : (
        <div className="mb-1.5 flex justify-end">
          <span
            className={cn(
              "font-mono text-sm tabular-nums",
              hot ? "text-amber-300" : "text-cyan-200/90",
            )}
          >
            {format(value)}
          </span>
        </div>
      )}
      <div className="risk-envelope-slider__track-wrap">
        <div
          className="risk-envelope-slider__fill"
          style={{ width: `${pct}%` }}
          aria-hidden
        />
        <input
          type="range"
          className="risk-envelope-slider__input config-range w-full"
          min={min}
          max={max}
          step={step}
          value={value}
          aria-label={label}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </div>
    </div>
  );
}

export { patchDraft };
