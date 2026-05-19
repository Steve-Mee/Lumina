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
import { cn } from "@/lib/utils";
import {
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

const QUALITY_ORDER: VisualQuality[] = ["low", "balanced", "high"];

export function VisualSettingsDialog() {
  const [open, setOpen] = useState(false);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const setVisualQuality = useVisualSettingsStore((s) => s.setVisualQuality);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-9 w-9 p-0 text-muted-foreground hover:text-cyan-200"
          aria-label="Visual quality settings"
          title="Visual quality"
        >
          <Settings2 className="size-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-cyan-100">Visual Quality</DialogTitle>
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
                className={cn(
                  "rounded-lg border px-3 py-2.5 text-left transition-colors",
                  active
                    ? "border-cyan-400/40 bg-cyan-500/10"
                    : "border-white/10 bg-black/20 hover:border-white/20",
                )}
              >
                <p className="font-mono text-xs tracking-wide text-foreground">
                  {meta.title}
                </p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  {meta.description}
                </p>
                <p className="mt-1.5 font-mono text-[9px] text-cyan-200/70">
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
