import { LineChart } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { TrainingMonitorDialog } from "@/components/cockpit/TrainingMonitorDialog";
import { Button } from "@/components/ui/button";
import { useDeckPanelStore } from "@/store/deckPanelStore";
import { cn } from "@/lib/utils";

interface TrainingMonitorTriggerProps {
  className?: string;
}

export function TrainingMonitorTrigger({ className }: TrainingMonitorTriggerProps) {
  const [open, setOpen] = useState(false);
  const setActiveCenterTab = useDeckPanelStore((state) => state.setActiveCenterTab);

  const openPpoPanel = () => {
    setActiveCenterTab("ppo");
    toast("PPO Evolution panel opened", {
      description: "Switched to Command Center → PPO Evolution tab.",
    });
  };

  return (
    <>
      <Button
        type="button"
        variant="command-ghost"
        size="sm"
        className={cn("h-8", className)}
        onClick={openPpoPanel}
        onDoubleClick={() => setOpen(true)}
        title="Open PPO Evolution tab (double-click for fullscreen monitor)"
      >
        <LineChart className="size-3.5" aria-hidden />
        Training Monitor
      </Button>
      <TrainingMonitorDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
