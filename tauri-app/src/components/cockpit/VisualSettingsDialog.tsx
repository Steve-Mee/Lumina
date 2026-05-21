import { Settings2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  VISUAL_QUALITY_LABELS,
  VISUAL_QUALITY_PRESETS,
  type VisualQuality,
} from "@/lib/visualQualityPresets";
import { modeTextTier2Class, modeValueClass, utilityQualityChipClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { selectVisualQuality, useVisualSettingsStore } from "@/store/visualSettingsStore";

const QUALITY_ORDER: VisualQuality[] = ["low", "balanced", "high"];

export function VisualSettingsDialog() {
  const [open, setOpen] = useState(false);
  const operatorMode = useCoreStore(selectCurrentMode);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const setVisualQuality = useVisualSettingsStore((s) => s.setVisualQuality);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant="command-ghost"
          className="h-9 w-9 p-0"
          aria-label="Visual quality settings"
          title="Visual quality"
        >
          <Settings2 className="size-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className={cn(modeTextTier2Class(operatorMode))}>
            Visual Quality
          </DialogTitle>
          <DialogDescription>
            3D panels pause when off-screen to save GPU. Changes apply immediately.
          </DialogDescription>
        </DialogHeader>

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
                className={utilityQualityChipClass(operatorMode, active)}
              >
                <p className="font-mono text-xs tracking-wide text-foreground">
                  {meta.title}
                </p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  {meta.description}
                </p>
                <p className={cn("mt-1.5 font-mono text-[9px]", modeValueClass(operatorMode))}>
                  DPR {preset.dpr.join("–")} · AA {preset.antialias ? "on" : "off"} ·
                  particles ×{preset.particleScale}
                </p>
              </button>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
