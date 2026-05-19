import { Loader2, Radio, WifiOff } from "lucide-react";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { Button } from "@/components/ui/button";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import { useDeckPanelStore } from "@/store/deckPanelStore";
import type { ConnectionStatus } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface DecisionTheaterStatusHeroProps {
  connectionStatus: ConnectionStatus;
  hasLiveData: boolean;
  className?: string;
}

export function DecisionTheaterStatusHero({
  connectionStatus,
  hasLiveData,
  className,
}: DecisionTheaterStatusHeroProps) {
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const setActiveRightTab = useDeckPanelStore((s) => s.setActiveRightTab);

  if (!apiKeyConfigured) {
    return <ApiKeySetupCallout className={className} />;
  }

  if (connectionStatus === "connecting" || connectionStatus === "reconnecting") {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-lg border border-cyan-500/25 bg-cyan-950/20 px-6 py-8 text-center",
          className,
        )}
      >
        <Loader2 className="size-8 animate-spin text-cyan-300/90" />
        <div>
          <p className="font-mono text-xs tracking-wide text-cyan-200 uppercase">
            {connectionStatus === "reconnecting" ? "Reconnecting to live core" : "Connecting to live core"}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Decision brief will populate when the WebSocket stream is live.
          </p>
        </div>
      </div>
    );
  }

  if (connectionStatus === "disconnected" && !hasLiveData) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-lg border border-amber-500/25 bg-amber-950/20 px-6 py-8 text-center",
          className,
        )}
      >
        <WifiOff className="size-8 text-amber-300/90" />
        <div>
          <p className="font-mono text-xs tracking-wide text-amber-200 uppercase">
            Live stream offline
          </p>
          <p className="mt-1 max-w-sm text-xs text-muted-foreground">
            Showing last known state. Start the engine or check backend health to resume live
            decisions.
          </p>
        </div>
        <Button type="button" size="sm" variant="secondary" onClick={() => setActiveRightTab("monitor")}>
          Open Monitor
        </Button>
      </div>
    );
  }

  if (connectionStatus === "disconnected" && hasLiveData) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-md border border-amber-500/20 bg-amber-950/15 px-3 py-2 text-xs text-amber-100/85",
          className,
        )}
      >
        <Radio className="size-3.5 shrink-0 text-amber-300/90" />
        <span>Live stream offline — displaying cached trades and reasoning.</span>
        <Button
          type="button"
          size="xs"
          variant="ghost"
          className="ml-auto shrink-0"
          onClick={() => setActiveRightTab("monitor")}
        >
          Monitor
        </Button>
      </div>
    );
  }

  return null;
}
