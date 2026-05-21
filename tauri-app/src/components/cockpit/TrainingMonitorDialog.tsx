import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { modeTextTier2Class, modeValueClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import { usePPOEvolutionLive } from "@/context/PPOEvolutionContext";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";

interface TrainingMonitorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TrainingMonitorDialog({ open, onOpenChange }: TrainingMonitorDialogProps) {
  const { logs, connected } = usePPOEvolutionLive();
  const operatorMode = useCoreStore(selectCurrentMode);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle
            className={cn(
              "font-mono text-sm tracking-[0.18em] uppercase",
              modeTextTier2Class(operatorMode),
            )}
          >
            Training Monitor
          </DialogTitle>
          <DialogDescription>
            Live PPO policy evolution — operator mode{" "}
            <span className={cn("font-mono", modeValueClass(operatorMode))}>{operatorMode}</span>
          </DialogDescription>
        </DialogHeader>
        <PPOEvolutionDashboard
          logs={logs}
          connected={connected}
          showAdvancedFeatures
          className="border-0 bg-transparent p-0 shadow-none"
        />
      </DialogContent>
    </Dialog>
  );
}
