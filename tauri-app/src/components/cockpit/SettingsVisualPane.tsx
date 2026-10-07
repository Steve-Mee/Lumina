import { Button } from "@/components/ui/button";
import { resetCommandDeckTour } from "@/components/cockpit/CommandDeckTour";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import { readHudLayoutPrefs } from "@/lib/hudSignalLayout";
import {
  VISUAL_QUALITY_LABELS,
  VISUAL_QUALITY_PRESETS,
  type VisualQuality,
} from "@/lib/visualQualityPresets";
import { cn } from "@/lib/utils";
import { useHudLayoutPrefsStore } from "@/store/hudLayoutPrefsStore";
import {
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";
import { useState } from "react";

const QUALITY_ORDER: VisualQuality[] = ["low", "balanced", "high"];

/** Visual tab extracted so SettingsDialog can host the account tab. */
export function SettingsVisualPane({
  operatorMode,
  onReplayTour,
}: {
  operatorMode: string;
  onReplayTour: () => void;
}) {
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const setVisualQuality = useVisualSettingsStore((s) => s.setVisualQuality);
  const [hudPrefs, setHudPrefs] = useState(readHudLayoutPrefs);
  const setHudPrefsStore = useHudLayoutPrefsStore((s) => s.setPrefs);

  return (
    <div className="space-y-4">
      <div className="grid gap-2">
        {QUALITY_ORDER.map((quality) => {
          const preset = VISUAL_QUALITY_PRESETS[quality];
          const meta = VISUAL_QUALITY_LABELS[quality];
          const active = visualQuality === quality;
          return (
            <button
              key={quality}
              type="button"
              onClick={() => setVisualQuality(quality)}
              className={cn(
                "rounded-lg border px-3 py-2.5 text-left transition-colors",
                active
                  ? operatorMode === "REAL"
                    ? "border-slate-500/40 bg-slate-700/25"
                    : "border-cyan-400/40 bg-cyan-500/10"
                  : luminaSurfaceMutedClass("border border-white/10 hover:border-white/20"),
              )}
            >
              <p className="font-mono text-xs tracking-wide text-foreground">{meta.title}</p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">{meta.description}</p>
              <p className="mt-1.5 font-mono text-[9px] text-cyan-200/70">
                DPR {preset.dpr.join("–")} · particles ×{preset.particleScale}
              </p>
            </button>
          );
        })}
      </div>
      {operatorMode === "SIM" ? (
        <div className={luminaSurfaceMutedClass("rounded-lg border border-white/10 p-3")}>
          <p className="font-mono text-xs tracking-wide text-foreground">HUD hero signal</p>
          <p className="mt-1 text-[10px] text-muted-foreground">
            Primary HUD slot — secondary contextual moves to Performance annex when session idle.
          </p>
          <Button
            type="button"
            size="sm"
            variant="command-ghost"
            className="mt-2"
            onClick={() => {
              const next = {
                ...hudPrefs,
                heroPrimary: (hudPrefs.heroPrimary === "fortress" ? "equity" : "fortress") as
                  | "equity"
                  | "fortress",
              };
              setHudPrefsStore(next);
              setHudPrefs(next);
            }}
          >
            {hudPrefs.heroPrimary === "fortress" ? "Show equity as hero" : "Show fortress arc as hero"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="command-ghost"
            className="mt-2 ml-2"
            onClick={() => {
              const next = { ...hudPrefs, showPnlInSim: !hudPrefs.showPnlInSim };
              setHudPrefsStore(next);
              setHudPrefs(next);
            }}
          >
            {hudPrefs.showPnlInSim ? "Annex: regime hint" : "Annex: P&L hint"}
          </Button>
        </div>
      ) : null}
      <div className={luminaSurfaceMutedClass("rounded-lg border border-white/10 p-3")}>
        <p className="text-xs text-muted-foreground">Guided walkthrough of the command deck layout.</p>
        <Button
          type="button"
          size="sm"
          variant="command-ghost"
          className="mt-2"
          onClick={() => {
            resetCommandDeckTour();
            onReplayTour();
          }}
        >
          Replay command deck tour
        </Button>
      </div>
    </div>
  );
}
