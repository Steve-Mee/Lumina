import { isTauri } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  NINJATRADER_DEFAULT_PATH,
  NINJATRADER_DOWNLOAD_URL,
  NINJATRADER_PATH_ENV,
} from "@/lib/ninjaTraderClient";

interface NinjaTraderInstallDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  launchError?: string | null;
}

async function openDownloadPage(): Promise<void> {
  if (isTauri()) {
    await openUrl(NINJATRADER_DOWNLOAD_URL);
    return;
  }

  window.open(NINJATRADER_DOWNLOAD_URL, "_blank", "noopener,noreferrer");
}

export function NinjaTraderInstallDialog({
  open,
  onOpenChange,
  launchError = null,
}: NinjaTraderInstallDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-cyan-100">
            NinjaTrader 8 not found
          </DialogTitle>
          <DialogDescription className="leading-relaxed">
            LUMINA connects to markets through NinjaTrader 8. Install it on this
            machine, then use Launch NinjaTrader from the command deck.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm text-muted-foreground">
          {launchError ? (
            <p className="rounded-md border border-red-400/30 bg-red-950/30 px-3 py-2 text-red-200">
              {launchError}
            </p>
          ) : null}

          <ol className="list-decimal space-y-2 pl-5">
            <li>Download NinjaTrader 8 from the official site.</li>
            <li>Run the installer and sign in to your account.</li>
            <li>Connect your data feed and broker or sim account.</li>
            <li>Return here and click Launch NinjaTrader again.</li>
          </ol>

          <p>
            Default install location:
            <code className="mt-1 block rounded border border-white/10 bg-black/30 px-2 py-1 font-mono text-[11px] text-cyan-100/90">
              {NINJATRADER_DEFAULT_PATH}
            </code>
          </p>

          <p>
            Custom install? Set{" "}
            <code className="font-mono text-[11px] text-cyan-100/90">
              {NINJATRADER_PATH_ENV}
            </code>{" "}
            to the full path of <code className="font-mono text-[11px]">NinjaTrader.exe</code>{" "}
            before starting LUMINA.
          </p>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button
            type="button"
            className="bg-cyan-600/80 text-cyan-50 hover:bg-cyan-600"
            onClick={() => void openDownloadPage()}
          >
            <ExternalLink className="mr-2 size-4" />
            Open download page
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
