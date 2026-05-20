import { Loader2, Radio, WifiOff } from "lucide-react";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { pendingHighlightClass, warnOverlayPanelClass } from "@/lib/modePresentation";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import type { ConnectionStatus, TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface DecisionTheaterStatusHeroProps {
  connectionStatus: ConnectionStatus;
  hasLiveData: boolean;
  mode: TradingMode;
  className?: string;
}

export function DecisionTheaterStatusHero({
  connectionStatus,
  hasLiveData,
  mode,
  className,
}: DecisionTheaterStatusHeroProps) {
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);

  if (!apiKeyConfigured) {
    return <ApiKeySetupCallout className={className} />;
  }

  if (connectionStatus === "connecting" || connectionStatus === "reconnecting") {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-lg px-6 py-8 text-center",
          warnOverlayPanelClass(),
          className,
        )}
      >
        <Loader2 className={cn("size-8 animate-spin", pendingHighlightClass(mode))} />
        <div>
          <p className={cn("font-mono text-xs tracking-wide uppercase", pendingHighlightClass(mode))}>
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
          "flex flex-col items-center justify-center gap-3 rounded-lg px-6 py-8 text-center",
          warnOverlayPanelClass(),
          className,
        )}
      >
        <WifiOff className={cn("size-8", pendingHighlightClass(mode))} />
        <div>
          <p className={cn("font-mono text-xs tracking-wide uppercase", pendingHighlightClass(mode))}>
            Live stream offline
          </p>
          <p className="mt-1 max-w-sm text-xs text-muted-foreground">
            Showing last known state. Start the engine or check transport status in the deck
            header. System diagnostics are available under Ops.
          </p>
        </div>
      </div>
    );
  }

  if (connectionStatus === "disconnected" && hasLiveData) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-md px-3 py-2 text-xs",
          warnOverlayPanelClass(),
          pendingHighlightClass(mode),
          className,
        )}
      >
        <Radio className={cn("size-3.5 shrink-0", pendingHighlightClass(mode))} />
        <span>Live stream offline — displaying cached trades and reasoning.</span>
      </div>
    );
  }

  return null;
}
