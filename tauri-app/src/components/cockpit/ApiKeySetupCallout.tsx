import { KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSettingsDialogStore } from "@/store/settingsDialogStore";
import { cn } from "@/lib/utils";

interface ApiKeySetupCalloutProps {
  className?: string;
  compact?: boolean;
}

export function ApiKeySetupCallout({ className, compact }: ApiKeySetupCalloutProps) {
  const openSettings = useSettingsDialogStore((s) => s.openSettings);

  return (
    <div
      className={cn(
        "rounded-lg border border-amber-500/30 bg-amber-950/25 p-4 text-sm text-amber-100/90",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <KeyRound className="mt-0.5 size-5 shrink-0 text-amber-300/90" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-amber-100">Admin API key required</p>
          {!compact ? (
            <p className="mt-1 text-xs leading-relaxed text-amber-100/75">
              Engine controls, monitoring, and evolution approvals need your dashboard admin key
              (same value as in <span className="font-mono">.env</span> / config).
            </p>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="command-primary"
            className="mt-3"
            onClick={() => openSettings("apiKey")}
          >
            Open Settings
          </Button>
        </div>
      </div>
    </div>
  );
}
