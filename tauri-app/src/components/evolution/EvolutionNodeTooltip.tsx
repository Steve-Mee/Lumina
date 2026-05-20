import { Html } from "@react-three/drei";

import { truncateHash } from "@/lib/evolutionArenaTheme";
import type { EvolutionEdge, EvolutionNode } from "@/lib/evolutionTreeTypes";
import { cn } from "@/lib/utils";

interface EvolutionNodeTooltipProps {
  node: EvolutionNode;
  incomingEdge: EvolutionEdge | null;
  visible: boolean;
}

const STATUS_CLASS: Record<EvolutionNode["status"], string> = {
  champion: "evolution-node-tooltip__status--champion",
  active: "evolution-node-tooltip__status--active",
  archived: "evolution-node-tooltip__status--archived",
  proposed: "evolution-node-tooltip__status--proposed",
  rejected: "evolution-node-tooltip__status--rejected",
};

export function EvolutionNodeTooltip({
  node,
  incomingEdge,
  visible,
}: EvolutionNodeTooltipProps) {
  return (
    <Html
      center
      distanceFactor={6}
      occlude={false}
      zIndexRange={[40, 0]}
      style={{
        pointerEvents: "none",
        opacity: visible ? 1 : 0,
        transform: "translateY(-12px)",
      }}
    >
      <div
        className={cn(
          "evolution-node-tooltip lumina-glass",
          visible ? "evolution-node-tooltip--visible" : "evolution-node-tooltip--hidden",
        )}
        role="tooltip"
      >
        <div className="evolution-node-tooltip__header">
          <span className="evolution-node-tooltip__hash">{truncateHash(node.hash)}</span>
          <span className={cn("evolution-node-tooltip__status", STATUS_CLASS[node.status])}>
            {node.status}
          </span>
        </div>

        <p className="evolution-node-tooltip__fitness">
          Fitness <strong>{Math.round(node.fitness * 100)}%</strong>
        </p>

        <dl className="evolution-node-tooltip__meta">
          <div>
            <dt>Gen</dt>
            <dd>{node.generation}</dd>
          </div>
          {node.mutationDepth ? (
            <div>
              <dt>Depth</dt>
              <dd className="uppercase">{node.mutationDepth}</dd>
            </div>
          ) : null}
          {incomingEdge ? (
            <div>
              <dt>Edge</dt>
              <dd className="uppercase">{incomingEdge.mutationType}</dd>
            </div>
          ) : null}
        </dl>

        <p className="evolution-node-tooltip__reasoning">{node.reasoning}</p>

        {node.status === "proposed" ? (
          <p className="evolution-node-tooltip__hint">Click to approve or reject</p>
        ) : null}
      </div>
    </Html>
  );
}
