import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  BotConfigForm,
  envelopeConsequenceLine,
  envelopeSummaryLine,
} from "@/components/config/BotConfigForm";
import { playgroundSealBlocker } from "@/components/config/botConfigEnvelope";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import {
  PhaseCtaBar,
  PhaseGenesisFrame,
  PhasePanelToolbar,
} from "@/components/shared/PhaseCinematicFrames";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import {
  defaultBotConfigDraft,
  type BotConfigDraft,
  toBotConfigPayload,
} from "@/lib/botConfigDraft";
import { helpFor } from "@/lib/helpTexts";
import { postBotConfig } from "@/lib/setupClient";
import { useBotConfigStore } from "@/store/botConfigStore";
import { useOnboardingStore } from "@/store/onboardingStore";

/**
 * Post-birth Playground gate: seal SIM Risk Envelope before live SIM trading.
 * Birth trains the brain; this seals how hard it may trade with fictional capital.
 */
export function PlaygroundEnvelopeSeal() {
  const refresh = useOnboardingStore((s) => s.refresh);
  const loadFromBackend = useBotConfigStore((s) => s.loadFromBackend);
  const [draft, setDraft] = useState<BotConfigDraft>(() => defaultBotConfigDraft());
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await loadFromBackend();
      if (cancelled) return;
      const storeDraft = useBotConfigStore.getState().draft;
      setDraft(storeDraft);
      setLoaded(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadFromBackend]);

  const summary = envelopeSummaryLine(draft);
  const consequence = envelopeConsequenceLine(draft);
  const sealBlocker = playgroundSealBlocker(draft);

  const handleSeal = async () => {
    if (sealBlocker) {
      toast.error(sealBlocker);
      return;
    }
    setSaving(true);
    try {
      const result = await postBotConfig({
        ...toBotConfigPayload(draft),
        seal_sim_envelope: true,
      });
      if (!result.success || result.playground_envelope_sealed !== true) {
        toast.error(sealBlocker ?? "Seal refused. Set a negative daily loss cap and an open-risk cap.");
        return;
      }
      toast.success(
        `SIM envelope sealed. Daily loss cap ${result.daily_loss_cap}, open risk ${result.max_total_open_risk}.`,
      );
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Seal failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <OnboardingShell className="birth-phase-screen birth-phase-screen--cinematic onboarding-shell--form">
      <div className="birth-phase-cinematic relative mx-auto flex h-dvh min-h-0 w-full max-w-none flex-col overflow-hidden">
        <LuminaPhaseHeader
          eyebrow="Playground"
          title="Seal SIM envelope"
          status="Required before SIM crawl"
          tone="cyan"
          variant="strip"
          className="lumina-phase-header relative z-20"
        />
        <EvolutionLadderStrip activePhase="playground" className="relative z-20" />
        <PhaseGenesisFrame ariaLabel="Seal SIM risk envelope">
          <PhasePanelToolbar
            title="Risk envelope"
            subtitle="Required before Playground SIM trading"
            titleTip={helpFor("config_birth_sim_runtime") ?? ""}
          />
          <div className="risk-envelope-banner risk-envelope-banner--info mx-2 mt-2 shrink-0">
            <p className="text-[11px] leading-relaxed">
              <strong className="text-cyan-200/90">What we need:</strong> pick SIM (or
              sim_real_guard), set Kelly / daily kill-switch / open risk, and evolution remmen.
              REAL target stays locked until the maturity ladder says go.
            </p>
            <p className="mt-1 font-mono text-[10px] text-white/40">
              {summary} · {consequence}
            </p>
          </div>
          <div className="birth-genesis-panel__body min-h-0 flex-1 overflow-hidden">
            {loaded ? (
              <BotConfigForm
                variant="deck"
                draft={draft}
                onChange={(patch) =>
                  setDraft((prev) => ({
                    ...prev,
                    ...patch,
                    risk: { ...prev.risk, ...(patch.risk ?? {}) },
                    evolution: { ...prev.evolution, ...(patch.evolution ?? {}) },
                    preferences: { ...prev.preferences, ...(patch.preferences ?? {}) },
                  }))
                }
              />
            ) : (
              <p className="p-4 font-mono text-xs text-muted-foreground">Loading envelope…</p>
            )}
          </div>
          <PhaseCtaBar
            footnote={sealBlocker ?? "Next: Playground cinematic · SIM live"}
            primaryLabel={saving ? "SEALING…" : "SEAL SIM ENVELOPE"}
            onPrimary={() => void handleSeal()}
            primaryDisabled={saving || !loaded || sealBlocker !== null}
            primaryActivating={saving}
          />
        </PhaseGenesisFrame>
      </div>
    </OnboardingShell>
  );
}
