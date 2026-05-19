import { useCallback, useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { fetchOnboardingHardware } from "@/lib/opsClient";
import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { cn } from "@/lib/utils";

export function HardwareModelPanel({ className }: { className?: string }) {
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setPayload(await fetchOnboardingHardware());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Hardware scan failed");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const hardware = (payload?.hardware ?? {}) as Record<string, unknown>;
  const catalog = Array.isArray(payload?.model_catalog) ? payload!.model_catalog : [];

  const runSmartSetup = async () => {
    try {
      const base = resolveBackendBaseUrl();
      await fetch(`${base}/api/setup/smart-setup`, { method: "POST" });
      toast.success("Smart setup started");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Smart setup failed");
    }
  };

  return (
    <div className={cn("space-y-3 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <Cpu className="size-4 text-violet-300/90" />
        <h3 className="font-mono text-[11px] tracking-[0.14em] text-violet-200/90 uppercase">
          Hardware & Models
        </h3>
        <Button type="button" size="xs" variant="ghost" className="ml-auto" onClick={() => void refresh()}>
          Rescan
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          Tier: <span className="font-mono">{String(hardware.tier ?? "—")}</span>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          RAM: <span className="font-mono">{String(hardware.ram_gb ?? "—")} GB</span>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          VRAM: <span className="font-mono">{String(hardware.vram_gb ?? "—")} GB</span>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          Model: <span className="font-mono">{String(hardware.recommended_model ?? "—")}</span>
        </div>
      </div>

      <Button type="button" size="sm" onClick={() => void runSmartSetup()}>
        Run model upgrade (Smart Setup)
      </Button>

      <section className="rounded-lg border border-white/10 bg-black/25 p-3">
        <p className="mb-2 font-mono text-[10px] uppercase text-muted-foreground">Model catalog</p>
        <ul className="space-y-1 text-[11px] text-muted-foreground">
          {catalog.slice(0, 8).map((item, idx) => (
            <li key={idx} className="font-mono">
              {String((item as Record<string, unknown>).name ?? JSON.stringify(item))}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
