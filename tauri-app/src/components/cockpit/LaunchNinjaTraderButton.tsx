import { isTauri } from "@tauri-apps/api/core";
import { MonitorPlay } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { NinjaTraderInstallDialog } from "@/components/cockpit/NinjaTraderInstallDialog";
import { Button } from "@/components/ui/button";
import { detectNinjaTrader, launchNinjaTrader } from "@/lib/ninjaTraderClient";
import { cn } from "@/lib/utils";

interface LaunchNinjaTraderButtonProps {
  className?: string;
}

export function LaunchNinjaTraderButton({ className }: LaunchNinjaTraderButtonProps) {
  const [installed, setInstalled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  useEffect(() => {
    if (!isTauri()) {
      return;
    }

    let cancelled = false;

    void detectNinjaTrader().then((result) => {
      if (!cancelled) {
        setInstalled(result.installed);
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleClick = async () => {
    setLoading(true);
    setLaunchError(null);

    try {
      const result = await launchNinjaTrader();

      if (result.launched) {
        setInstalled(true);
        toast.success("Opening NinjaTrader 8…");
        return;
      }

      if (!result.installed) {
        setInstalled(false);
        setDialogOpen(true);
        return;
      }

      setInstalled(true);
      const message =
        result.error ?? "Could not start NinjaTrader 8. Check install permissions.";
      setLaunchError(message);
      toast.error(message);
      setDialogOpen(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        size="lg"
        disabled={loading}
        onClick={() => void handleClick()}
        className={cn(
          "launch-ninjatrader-btn relative h-11 min-h-11 border-cyan-400/35 bg-cyan-500/15 px-4 font-mono text-[11px] tracking-[0.16em] text-cyan-100 uppercase shadow-[0_0_18px_oklch(0.75_0.15_195/18%)] hover:bg-cyan-500/25 hover:text-cyan-50",
          className,
        )}
        aria-label="Launch NinjaTrader 8"
        title={installed ? "Launch NinjaTrader 8" : "Install or launch NinjaTrader 8"}
      >
        {installed ? (
          <span
            className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_oklch(0.72_0.17_155/80%)]"
            aria-hidden
          />
        ) : null}
        <MonitorPlay className="mr-2 size-4 shrink-0" />
        {loading ? "Launching…" : "Launch NinjaTrader"}
      </Button>

      <NinjaTraderInstallDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        launchError={launchError}
      />
    </>
  );
}
