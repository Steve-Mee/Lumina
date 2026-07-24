import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import {
  BotConfigForm,
  envelopeConsequenceLine,
  envelopeSummaryLine,
} from "@/components/config/BotConfigForm";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { HelpTip } from "@/components/ui/HelpTip";
import {
  defaultBotConfigDraft,
  type BotConfigDraft,
  toBotConfigPayload,
} from "@/lib/botConfigDraft";
import { helpFor } from "@/lib/helpTexts";
import { postBotConfig } from "@/lib/setupClient";
import { useBotConfigStore } from "@/store/botConfigStore";
import { useOnboardingStore } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

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

  const handleSeal = async () => {
    setSaving(true);
    try {
      // Playground = SIM capital path (fictional money, real order flow via Fabric).
      const sealedDraft: BotConfigDraft = {
        ...draft,
        mode: draft.mode === "real" ? "sim" : draft.mode,
      };
      const result = await postBotConfig({
        ...toBotConfigPayload(sealedDraft),
        seal_sim_envelope: true,
      });
      if (!result.success) {
        toast.error("Could not seal Risk Envelope");
        return;
      }
      toast.success("SIM envelope sealed — Playground open");
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Seal failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="risk-envelope-screen fixed inset-0 z-[80] flex flex-col bg-[var(--lumina-void)]"
      role="dialog"
      aria-label="Seal SIM risk envelope for playground"
    >
      <EvolutionLadderStrip className="shrink-0" showBlockers />
      <div className="risk-envelope-grid mx-auto w-full max-w-6xl min-h-0 flex-1 p-4">
        <aside className="risk-envelope-stage">
          <div className="px-4 text-center">
            <p className="font-mono text-[0.55rem] tracking-[0.16em] text-cyan-400/80 uppercase">
              Post-birth · Playground gate
            </p>
            <h2 className="mt-2 text-lg font-semibold text-cyan-50">Seal SIM Risk Envelope</h2>
            <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
              Birth built the organism. Now decide how hard it may trade with{" "}
              <strong className="text-cyan-200/90">fictional capital</strong> on NinjaTrader
              SIM — real order path, no live money.
            </p>
          </div>
          <div className="risk-envelope-stage__summary">
            <p className="risk-envelope-stage__summary-line">{summary}</p>
            <p className="risk-envelope-stage__summary-consequence">{consequence}</p>
          </div>
        </aside>

        <section className="risk-envelope-panel lumina-glass lumina-glass--overlay flex flex-col overflow-hidden">
          <div className="risk-envelope-panel__toolbar">
            <div>
              <p className="risk-envelope-panel__toolbar-title">Risk envelope</p>
              <p className="mt-0.5 font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
                Required before Playground SIM trading
              </p>
            </div>
            <HelpTip text={helpFor("config_birth_sim_runtime") ?? ""} />
          </div>

          <div className="risk-envelope-banner risk-envelope-banner--info mx-2 mt-2 shrink-0">
            <p className="text-[11px] leading-relaxed">
              <strong className="text-cyan-200/90">What we need:</strong> pick SIM (or
              sim_real_guard), set Kelly / daily kill-switch / open risk, and evolution remmen.
              REAL target stays locked until the maturity ladder says go.
            </p>
          </div>

          <div className="risk-envelope-panel__body min-h-0 flex-1 overflow-hidden">
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

          <div className="risk-envelope-cta-bar">
            <p className="mb-2 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
              Next: Command Deck · SIM live + Evolution
            </p>
            <button
              type="button"
              className={cn("onboarding-cta w-full py-5", saving && "opacity-70")}
              disabled={saving || !loaded}
              onClick={() => void handleSeal()}
            >
              {saving ? "Sealing…" : "Seal SIM envelope & open Playground"}
            </button>
          </div>
        </section>
      </div>
    </motion.div>
  );
}
