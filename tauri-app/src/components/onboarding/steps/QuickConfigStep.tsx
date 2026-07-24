import { useMemo, useState } from "react";
import { motion } from "framer-motion";

import {
  BotConfigForm,
  envelopeConsequenceLine,
  envelopeSummaryLine,
  resolveEnvelopeChips,
  type EnvelopeChipState,
} from "@/components/config/BotConfigForm";
import { CredentialsVaultOrganism } from "@/components/onboarding/CredentialsVaultOrganism";
import { HelpTip } from "@/components/ui/HelpTip";
import { helpFor } from "@/lib/helpTexts";
import type { BotConfigDraft } from "@/lib/botConfigDraft";
import { DEFAULT_INSTRUMENT_ROOT } from "@/lib/instrumentsCatalog";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

interface QuickConfigStepProps {
  draft: OnboardingDraft;
  onChange: (patch: Partial<OnboardingDraft>) => void;
  onContinue: () => void;
}

function StatusChip({
  label,
  state,
  tip,
}: {
  label: string;
  state: EnvelopeChipState;
  tip: string;
}) {
  return (
    <span
      className="risk-envelope-status-chip"
      data-state={state === "idle" ? undefined : state}
      title={tip}
    >
      <span className="risk-envelope-status-chip__dot" />
      {label}
    </span>
  );
}

function toBotDraft(
  draft: OnboardingDraft,
  preferences: BotConfigDraft["preferences"],
): BotConfigDraft {
  return {
    mode: draft.mode,
    risk: draft.risk,
    evolution: draft.evolution,
    preferences,
  };
}

export function QuickConfigStep({ draft, onChange, onContinue }: QuickConfigStepProps) {
  const [preferences, setPreferences] = useState<BotConfigDraft["preferences"]>({
    instrument: DEFAULT_INSTRUMENT_ROOT,
    voice_enabled: true,
    screen_share_enabled: true,
    dashboard_enabled: true,
    runtime_trace: true,
    runtime_trace_interval_sec: 2,
    latency_sla_ms: 300,
  });

  const botDraft = useMemo(
    () => toBotDraft(draft, preferences),
    [draft, preferences],
  );

  const chips = useMemo(() => resolveEnvelopeChips(botDraft), [botDraft]);
  const summary = useMemo(() => envelopeSummaryLine(botDraft), [botDraft]);
  const consequence = useMemo(() => envelopeConsequenceLine(botDraft), [botDraft]);

  const stageCaption =
    draft.mode === "real"
      ? "REAL target · capital later"
      : draft.mode === "sim_real_guard"
        ? "Guarded SIM · envelope tight"
        : draft.mode === "paper"
          ? "Paper path · no live capital"
          : "SIM envelope · learning first";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      className="risk-envelope-screen"
    >
      <div className="risk-envelope-grid">
        <aside className="risk-envelope-stage" aria-hidden={false}>
          <CredentialsVaultOrganism
            linked={draft.mode !== "real"}
            caption={stageCaption}
            className="my-auto"
          />
          <div className="risk-envelope-stage__summary">
            <p className="risk-envelope-stage__summary-line" title={helpFor("config_envelope_summary")}>
              {summary}
            </p>
            <p className="risk-envelope-stage__summary-consequence">{consequence}</p>
          </div>
        </aside>

        <section
          className="risk-envelope-panel lumina-glass lumina-glass--overlay"
          aria-label="Trading profile and risk envelope"
        >
          <div className="risk-envelope-panel__toolbar">
            <div className="min-w-0">
              <p className="risk-envelope-panel__toolbar-title">Risk envelope</p>
              <p className="mt-0.5 font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
                Target profile · capital preservation first
              </p>
            </div>
            <HelpTip
              text={helpFor("config_birth_sim_runtime") ?? ""}
              label="What is expected on this page"
            />
          </div>

          <div className="risk-envelope-banner risk-envelope-banner--info mx-2 mt-2 shrink-0">
            <p className="flex items-start gap-1.5 text-[11px] leading-relaxed">
              <span className="min-w-0">
                <strong className="text-cyan-200/90">What we need from you:</strong> pick a
                target mode, set how much risk is allowed, and decide how hard evolution may
                push. During Birth the runtime is always{" "}
                <strong className="text-cyan-300">SIM</strong> (fail-closed) — this page
                seals your post-birth profile, not live orders now.
              </span>
              <HelpTip text={helpFor("config_birth_sim_runtime") ?? ""} />
            </p>
          </div>

          <div
            className="risk-envelope-status-strip"
            role="status"
            aria-label="Envelope status"
          >
            <StatusChip
              label="MODE"
              state={chips.mode}
              tip={`Target mode: ${draft.mode}. ${helpFor("config_target_mode") ?? ""}`}
            />
            <StatusChip
              label="RISK"
              state={chips.risk}
              tip={
                chips.risk === "warn"
                  ? "REAL envelope looks loose vs constitution defaults — tighten Kelly, daily cap, or open risk."
                  : chips.risk === "partial"
                    ? "Loose SIM envelope — fine for learning; do not mirror into REAL."
                    : "Risk envelope within expected bounds for this mode."
              }
            />
            <StatusChip
              label="EVOLUTION"
              state={chips.evolution}
              tip={
                chips.evolution === "warn"
                  ? "Aggressive or radical evolution without a firm approval gate."
                  : chips.evolution === "partial"
                    ? "Exploration enabled — keep an eye on mutation approvals."
                    : "Evolution governance looks controlled."
              }
            />
            <StatusChip
              label="BIRTH"
              state={chips.birth}
              tip={helpFor("config_birth_sim_runtime") ?? "Birth runtime stays SIM."}
            />
          </div>

          <div className="risk-envelope-panel__body">
            <BotConfigForm
              variant="deck"
              draft={botDraft}
              onChange={(patch) => {
                if (patch.preferences) {
                  setPreferences((prev) => ({ ...prev, ...patch.preferences }));
                }
                onChange({
                  mode: patch.mode ?? draft.mode,
                  risk: patch.risk ? { ...draft.risk, ...patch.risk } : draft.risk,
                  evolution: patch.evolution
                    ? { ...draft.evolution, ...patch.evolution }
                    : draft.evolution,
                });
              }}
            />
          </div>

          <div className="risk-envelope-cta-bar">
            <p className="mb-2 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
              Next: Neural Genesis — birth goals & maturity charter
            </p>
            <button
              type="button"
              className={cn("onboarding-cta w-full py-5")}
              onClick={onContinue}
            >
              Seal profile & continue
            </button>
          </div>
        </section>
      </div>
    </motion.div>
  );
}
