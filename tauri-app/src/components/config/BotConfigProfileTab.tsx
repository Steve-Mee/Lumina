import { FieldCard, ToggleRow } from "@/components/config/BotConfigFormPrimitives";
import { HelpTip } from "@/components/ui/HelpTip";
import {
  applyPaperModePreset,
  applySimModePreset,
  type BotConfigDraft,
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

export interface BotConfigProfileTabProps {
  draft: BotConfigDraft;
  onChange: (patch: Partial<BotConfigDraft>) => void;
  onRequestRealConfirm: () => void;
  className?: string;
}

export function BotConfigProfileTab({
  draft,
  onChange,
  onRequestRealConfirm,
  className,
}: BotConfigProfileTabProps) {
  const simRealGuard = draft.mode === "sim_real_guard";
  const primaryMode: "paper" | "sim" | "real" =
    draft.mode === "paper" ? "paper" : draft.mode === "real" ? "real" : "sim";

  const handleModeSelect = (mode: "paper" | "sim" | "real") => {
    if (mode === "real") {
      onRequestRealConfirm();
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

  return (
    <div className={className}>
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
    </div>
  );
}
