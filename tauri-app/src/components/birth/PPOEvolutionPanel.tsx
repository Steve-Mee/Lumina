import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

interface PPOEvolutionPanelProps {
  logs: PPOEvolutionMetric[];
  connected: boolean;
  className?: string;
}

/** @deprecated Prefer PPOEvolutionDashboard directly. Thin wrapper for backwards compatibility. */
export function PPOEvolutionPanel({ logs, connected, className }: PPOEvolutionPanelProps) {
  return (
    <PPOEvolutionDashboard
      logs={logs}
      connected={connected}
      title="PPO Evolution Live"
      compact
      className={className}
    />
  );
}
