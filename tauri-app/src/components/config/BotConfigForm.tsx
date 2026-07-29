import { useMemo, useState } from "react";

import {
  envelopeConsequenceLine,
  envelopeSummaryLine,
} from "@/components/config/botConfigEnvelope";
import { BotConfigEnvelopeTab } from "@/components/config/BotConfigEnvelopeTab";
import { BotConfigEvolutionTab } from "@/components/config/BotConfigEvolutionTab";
import { BotConfigOperatorTab } from "@/components/config/BotConfigOperatorTab";
import { BotConfigProfileTab } from "@/components/config/BotConfigProfileTab";
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
import { applyRealModePreset, type BotConfigDraft } from "@/lib/botConfigDraft";
import { helpFor } from "@/lib/helpTexts";
import { cn } from "@/lib/utils";

export type { EnvelopeChipState } from "@/components/config/botConfigEnvelope";
export {
  envelopeConsequenceLine,
  envelopeSummaryLine,
  patchDraft,
  resolveEnvelopeChips,
} from "@/components/config/botConfigEnvelope";

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

export function BotConfigForm({
  draft,
  onChange,
  showModeCallout = false,
  operatorMode,
  variant = "dialog",
  className,
}: BotConfigFormProps) {
  const [realConfirmOpen, setRealConfirmOpen] = useState(false);

  const confirmReal = () => {
    onChange(applyRealModePreset(draft));
    setRealConfirmOpen(false);
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
              <BotConfigProfileTab
                draft={draft}
                onChange={onChange}
                onRequestRealConfirm={() => setRealConfirmOpen(true)}
              />
            </TabsContent>

            <TabsContent value="envelope" className={tabContentClass}>
              <BotConfigEnvelopeTab draft={draft} onChange={onChange} />
            </TabsContent>

            <TabsContent value="evolution" className={tabContentClass}>
              <BotConfigEvolutionTab draft={draft} onChange={onChange} />
            </TabsContent>

            <TabsContent value="operator" className={tabContentClass}>
              <BotConfigOperatorTab draft={draft} onChange={onChange} />
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
