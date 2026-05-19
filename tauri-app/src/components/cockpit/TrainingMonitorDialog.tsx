import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto border-white/10 bg-black/90 backdrop-blur-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm tracking-[0.18em] text-cyan-200/90 uppercase">
            Training Monitor
          </DialogTitle>
          <DialogDescription>
            Live PPO policy evolution — operator mode{" "}
            <span className="font-mono text-cyan-300/90">{operatorMode}</span>
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
