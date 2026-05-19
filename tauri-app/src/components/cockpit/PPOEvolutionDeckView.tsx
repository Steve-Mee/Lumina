import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";
import { TrainingControlBar } from "@/components/operations/TrainingControlBar";
import { usePPOEvolutionLive } from "@/context/PPOEvolutionContext";
import { cn } from "@/lib/utils";

interface PPOEvolutionDeckViewProps {
  className?: string;
}

export function PPOEvolutionDeckView({ className }: PPOEvolutionDeckViewProps) {
  const { logs, connected } = usePPOEvolutionLive();

  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col overflow-hidden",
        className,
      )}
    >
      <TrainingControlBar className="shrink-0 px-2 pt-2" compact />
      <div className="min-h-0 flex-1 overflow-y-auto pr-1 [scrollbar-color:rgba(255,255,255,0.15)_transparent] [scrollbar-width:thin]">
        <PPOEvolutionDashboard
          logs={logs}
          connected={connected}
          showAdvancedFeatures
          className="border-0 bg-transparent p-2 shadow-none"
        />
      </div>
    </div>
  );
}