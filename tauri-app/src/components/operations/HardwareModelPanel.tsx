import { useCallback, useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { fetchOnboardingHardware } from "@/lib/opsClient";
import { startSmartSetup } from "@/lib/setupClient";
import { cn } from "@/lib/utils";

interface CatalogEntry {
  key?: string;
  display_name?: string;
  ollama_tag?: string;
  is_recommended?: boolean;
  fits_hardware?: boolean;
  recommended_tier?: string;
  parameter_size_b?: number;
}

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

  const hardware = (payload?.hardware ?? payload?.intelligence ?? {}) as Record<string, unknown>;
  const intel = (payload?.intelligence ?? {}) as Record<string, unknown>;
  const hwNested = (intel.hardware ?? hardware) as Record<string, unknown>;
  const catalog = (Array.isArray(payload?.model_catalog) ? payload!.model_catalog : []) as CatalogEntry[];
  const recommended = catalog.find((m) => m.is_recommended) ?? catalog[0];
  const currentKey = String(intel.recommended_model_key ?? recommended?.key ?? "");
  const current = catalog.find((m) => m.key === currentKey) ?? recommended;
  const upgradeTargets = catalog
    .filter((m) => m.key && m.key !== current?.key && m.fits_hardware)
    .slice(0, 5);

  const runSmartSetup = async (extra?: { force_high_tier?: boolean; pull_extra_models?: boolean }) => {
    try {
      await startSmartSetup({
        install_ollama: true,
        download_recommended_model: true,
        selected_model_key: recommended?.key,
        ...extra,
      });
      toast.success("Smart setup started");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Smart setup failed");
    }
  };

  const tierReq = hwNested.tier_requirements ?? hardware.tier_requirements;

  return (
    <div className={cn("space-y-3 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <Cpu className="size-4 text-violet-300/90" />
        <h3 className="font-mono text-[11px] tracking-[0.14em] text-violet-200/90 uppercase">
          Hardware & Models
        </h3>
        <Button type="button" size="xs" variant="command-ghost" className="ml-auto" onClick={() => void refresh()}>
          Rescan
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="lumina-surface-muted rounded px-3 py-2">
          Tier: <span className="font-mono">{String(hwNested.tier ?? hardware.tier ?? "—")}</span>
        </div>
        <div className="lumina-surface-muted rounded px-3 py-2">
          RAM: <span className="font-mono">{String(hwNested.ram_gb ?? hardware.ram_gb ?? "—")} GB</span>
        </div>
        <div className="lumina-surface-muted rounded px-3 py-2">
          VRAM: <span className="font-mono">{String(hwNested.vram_gb ?? hardware.vram_gb ?? "—")} GB</span>
        </div>
        <div className="lumina-surface-muted rounded px-3 py-2">
          Unsloth:{" "}
          <span className="font-mono">
            {hwNested.unsloth_supported ?? hardware.unsloth_supported ? "Yes" : "No"}
          </span>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/15 p-3 text-xs">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Current model</p>
          <p className="mt-1 font-medium text-cyan-100/90">
            {(current?.display_name ?? currentKey) || "—"}
          </p>
        </div>
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/15 p-3 text-xs">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Recommended</p>
          <p className="mt-1 font-medium text-emerald-100/90">
            {recommended?.display_name ?? "—"}
          </p>
          {recommended ? (
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">
              RAM {recommended.parameter_size_b ? `${recommended.parameter_size_b}B` : "—"} · tier{" "}
              {recommended.recommended_tier ?? "—"}
            </p>
          ) : null}
        </div>
      </div>

      {tierReq ? (
        <details className="lumina-surface-muted rounded-lg p-3 text-[11px]">
          <summary className="cursor-pointer font-mono text-[10px] uppercase text-muted-foreground">
            Tier requirements
          </summary>
          <pre className="mt-2 max-h-28 overflow-auto font-mono text-[9px] text-muted-foreground">
            {JSON.stringify(tierReq, null, 2)}
          </pre>
        </details>
      ) : null}

      {upgradeTargets.length > 0 ? (
        <section className="lumina-surface-muted rounded-lg p-3">
          <p className="mb-2 font-mono text-[10px] uppercase text-muted-foreground">Upgrade targets</p>
          <ul className="space-y-1 text-[11px] text-muted-foreground">
            {upgradeTargets.map((model) => (
              <li key={model.key} className="font-mono">
                • {model.display_name}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" onClick={() => void runSmartSetup()}>
          Install / upgrade to recommended
        </Button>
        <Button type="button" size="sm" variant="command-primary" onClick={() => void runSmartSetup({ pull_extra_models: true })}>
          Pull extra models
        </Button>
      </div>

      <section className="lumina-surface-muted rounded-lg p-3">
        <p className="mb-2 font-mono text-[10px] uppercase text-muted-foreground">Model catalog</p>
        <ul className="space-y-1 text-[11px] text-muted-foreground">
          {catalog.slice(0, 8).map((item) => (
            <li key={item.key} className="font-mono">
              {item.display_name ?? item.key}
              {item.is_recommended ? " · recommended" : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
