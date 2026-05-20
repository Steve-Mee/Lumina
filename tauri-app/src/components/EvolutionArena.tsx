import { Suspense, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { DECK_LOADING_COPY } from "@/lib/deckLoadingCopy";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { VisibilityCanvas } from "@/components/cockpit/VisibilityCanvas";
import { EvolutionForceGraphScene } from "@/components/evolution/EvolutionForceGraphScene";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useDeckPanelStore } from "@/store/deckPanelStore";
import {
  approveProposal,
  rejectProposal,
  resolveDefaultChallengerName,
} from "@/lib/evolutionClient";
import { useEvolutionTree } from "@/hooks/useEvolutionTree";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { birthClearTimeoutMs, calmMode, evolutionPalette, truncateHash } from "@/lib/evolutionArenaTheme";
import { modeTitleClass } from "@/lib/modePresentation";
import { transitionOrNone } from "@/lib/motionPresets";
import type { EvolutionEdge, EvolutionNode } from "@/lib/evolutionTreeTypes";
import { cn } from "@/lib/utils";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import {
  selectRenderConfig,
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

interface EvolutionArenaProps {
  className?: string;
}

function NodeDetailDialog({
  node,
  incomingEdge,
  open,
  onOpenChange,
  mode,
}: {
  node: EvolutionNode | null;
  incomingEdge: EvolutionEdge | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: ReturnType<typeof selectCurrentMode>;
}) {
  if (!node) {
    return null;
  }

  const palette = evolutionPalette(mode);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className={cn("flex items-center gap-2", modeTitleClass(mode))}>
            {truncateHash(node.hash)}
            <span className="rounded bg-violet-500/15 px-1.5 py-0.5 text-[10px] tracking-wider uppercase text-violet-300">
              {node.status}
            </span>
          </DialogTitle>
          <DialogDescription>{node.reasoning}</DialogDescription>
        </DialogHeader>

        <div className="space-y-3 font-mono text-[11px]">
          <div>
            <p className="mb-1 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
              DNA
            </p>
            <p className="break-all text-cyan-100/90">{node.hash}</p>
            <p className="mt-1 text-muted-foreground">
              {node.promptId} · v{node.version}
            </p>
            {node.contentDigest ? (
              <p className="mt-1 break-all text-[10px] text-muted-foreground/80">
                digest: {node.contentDigest}
              </p>
            ) : null}
          </div>

          <div>
            <div className="mb-1 flex justify-between text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
              <span>Fitness</span>
              <span>{Math.round(node.fitness * 100)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.round(node.fitness * 100)}%`,
                  background: `linear-gradient(90deg, ${palette.secondary}, ${palette.primary})`,
                }}
              />
            </div>
          </div>

          <dl className="space-y-1.5">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Generation</dt>
              <dd>{node.generation}</dd>
            </div>
            {node.mutationDepth ? (
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Mutation depth</dt>
                <dd className="uppercase">{node.mutationDepth}</dd>
              </div>
            ) : null}
            {incomingEdge ? (
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Incoming edge</dt>
                <dd className="uppercase">{incomingEdge.mutationType}</dd>
              </div>
            ) : null}
            {node.parentIds.length > 0 ? (
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Parents</dt>
                <dd className="text-right">
                  {node.parentIds.map((hash) => truncateHash(hash)).join(", ")}
                </dd>
              </div>
            ) : null}
            {node.createdAt ? (
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Created</dt>
                <dd>{node.createdAt}</dd>
              </div>
            ) : null}
          </dl>
          {node.status === "proposed" ? (
            <div className="flex gap-2 pt-2">
              <Button
                type="button"
                size="xs"
                variant="command-primary"
                onClick={() => {
                  void approveProposal({
                    hash: node.hash,
                    challenger_name:
                      resolveDefaultChallengerName({
                        hash: node.hash,
                        challengers: [{ name: node.promptId }],
                      }) ?? node.promptId,
                  })
                    .then(() => toast.success("Mutation approved"))
                    .catch((e) =>
                      toast.error(e instanceof Error ? e.message : "Approve failed"),
                    );
                }}
              >
                Approve
              </Button>
              <Button
                type="button"
                size="xs"
                variant="command-ghost"
                data-intent="danger"
                onClick={() => {
                  void rejectProposal({
                    hash: node.hash,
                    reason: "Rejected from Evolution Arena",
                  })
                    .then(() => toast.success("Mutation rejected"))
                    .catch((e) =>
                      toast.error(e instanceof Error ? e.message : "Reject failed"),
                    );
                }}
              >
                Reject
              </Button>
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function EvolutionArena({ className }: EvolutionArenaProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const currentMode = useCoreStore(selectCurrentMode);
  const renderConfig = useVisualSettingsStore(selectRenderConfig);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const reducedMotion = prefersReducedMotion || visualQuality === "low";
  const isCalmMode = calmMode(currentMode);
  const { graph, newNodeIds, loading, error, clearNewNodes, refresh } = useEvolutionTree();
  const [selectedNode, setSelectedNode] = useState<EvolutionNode | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    if (newNodeIds.length === 0) {
      return;
    }
    const timer = setTimeout(() => {
      clearNewNodes();
    }, birthClearTimeoutMs(currentMode));
    return () => clearTimeout(timer);
  }, [newNodeIds, clearNewNodes, currentMode]);

  const incomingEdge = useMemo(() => {
    if (!selectedNode) {
      return null;
    }
    return graph.edges.find((edge) => edge.to === selectedNode.id) ?? null;
  }, [graph.edges, selectedNode]);

  const handleNodeClick = (node: EvolutionNode) => {
    if (node.status === "proposed") {
      setSelectedNode(node);
      setDialogOpen(true);
      return;
    }
    setSelectedNode(node);
    setDialogOpen(true);
  };

  return (
    <>
      <div
        className={cn(
          "evolution-arena-shell relative min-h-[220px] w-full",
          isCalmMode ? "evolution-arena-shell--real" : "evolution-arena-shell--sim",
          className,
        )}
        aria-label={`Evolution arena — ${graph.nodes.length} strategies`}
        role="img"
        data-mode={currentMode}
      >
        <AnimatePresence>
          {loading ? (
            <motion.div
              key="arena-loader"
              className="absolute inset-0 z-20 flex items-center justify-center bg-black/30 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={transitionOrNone(reducedMotion, modeMotion)}
            >
              <PanelLoader label={DECK_LOADING_COPY.evolutionArena} />
            </motion.div>
          ) : null}
        </AnimatePresence>
        <AnimatePresence>
          {error ? (
            <motion.div
              key="arena-error"
              className="absolute inset-x-3 top-3 z-30 rounded-lg border border-amber-500/35 bg-amber-950/80 px-3 py-2"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
            >
              <p className="font-mono text-[10px] text-amber-100/90">{error}</p>
              <Button
                type="button"
                size="xs"
                variant="command-ghost"
                className="mt-2"
                onClick={() => void refresh()}
              >
                Retry
              </Button>
            </motion.div>
          ) : null}
        </AnimatePresence>

        {!loading && !error && graph.nodes.length === 0 ? (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 px-6 text-center">
            <p
              className={cn(
                "mode-text-tier2 font-mono text-xs tracking-wide uppercase",
                modeTitleClass(currentMode),
              )}
            >
              No evolution tree yet
            </p>
            <p className="max-w-xs text-[11px] text-muted-foreground">
              Strategies appear here after birth completes and evolution proposals are recorded.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              <Button type="button" size="sm" variant="command-primary" onClick={() => void refresh()}>
                Refresh
              </Button>
              <Button
                type="button"
                size="sm"
                variant="command-ghost"
                onClick={() => useDeckPanelStore.getState().setActiveRightTab("monitor")}
              >
                Open Monitor
              </Button>
            </div>
          </div>
        ) : null}

        <motion.div
          className="h-full w-full"
          initial={{ opacity: 0 }}
          animate={{ opacity: loading ? 0.3 : 1 }}
          transition={transitionOrNone(reducedMotion, modeMotion)}
        >
          <Suspense
            fallback={
              <PanelLoader label={DECK_LOADING_COPY.forceGraph} className="min-h-[220px]" />
            }
          >
            <VisibilityCanvas
              panelName="Evolution Arena"
              idleLabel="Evolution arena paused — scroll into view"
              camera={{ position: [0, 0, 5.5], fov: 50 }}
            >
              <EvolutionForceGraphScene
                graph={graph}
                newNodeIds={newNodeIds}
                reducedMotion={reducedMotion}
                calmMode={isCalmMode}
                mode={currentMode}
                visualQuality={visualQuality}
                renderConfig={renderConfig}
                onNodeClick={handleNodeClick}
              />
            </VisibilityCanvas>
          </Suspense>
        </motion.div>
      </div>

      <NodeDetailDialog
        node={selectedNode}
        incomingEdge={incomingEdge}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode={currentMode}
      />
    </>
  );
}
