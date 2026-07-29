import {
  dailyCapConsequence,
  kellyConsequence,
  openRiskConsequence,
} from "@/components/config/botConfigEnvelope";
import {
  ConfigRange,
  FieldCard,
} from "@/components/config/BotConfigFormPrimitives";
import { HelpTip } from "@/components/ui/HelpTip";
import type { BotConfigDraft } from "@/lib/botConfigDraft";
import { CONSEQUENCE_HINTS, helpFor } from "@/lib/helpTexts";

export interface BotConfigEnvelopeTabProps {
  draft: BotConfigDraft;
  onChange: (patch: Partial<BotConfigDraft>) => void;
  className?: string;
}

export function BotConfigEnvelopeTab({
  draft,
  onChange,
  className,
}: BotConfigEnvelopeTabProps) {
  const isReal = draft.mode === "real";

  return (
    <div className={className}>
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
    </div>
  );
}
