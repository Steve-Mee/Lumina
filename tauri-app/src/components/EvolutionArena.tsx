import { OrbitControls } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from "d3-force-3d";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import * as THREE from "three";

import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { VisibilityCanvas } from "@/components/cockpit/VisibilityCanvas";

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
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { springSoft } from "@/lib/motionPresets";
import type {
  EvolutionEdge,
  EvolutionGraph,
  EvolutionNode,
} from "@/lib/evolutionTreeTypes";
import { cn } from "@/lib/utils";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import {
  selectRenderConfig,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

interface EvolutionArenaProps {
  className?: string;
}

interface SimNode extends EvolutionNode {
  x: number;
  y: number;
  z: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

interface BurstParticle {
  id: number;
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  life: number;
}

const BURST_DURATION_S = 1.2;

function truncateHash(hash: string, head = 8, tail = 6): string {
  if (hash.length <= head + tail + 3) {
    return hash;
  }
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`;
}

function nodeRadius(fitness: number): number {
  return 0.12 + fitness * 0.18;
}

function fitnessColor(fitness: number): string {
  if (fitness >= 0.7) {
    return "#00e5ff";
  }
  if (fitness >= 0.55) {
    return "#a855f7";
  }
  return "#64748b";
}

function MutationBurst({
  origin,
  active,
  reducedMotion,
  burstParticles,
}: {
  origin: THREE.Vector3 | null;
  active: boolean;
  reducedMotion: boolean;
  burstParticles: number;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const particlesRef = useRef<BurstParticle[]>([]);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  useEffect(() => {
    if (!active || !origin || reducedMotion) {
      particlesRef.current = [];
      return;
    }

    particlesRef.current = Array.from({ length: burstParticles }, (_, i) => {
      const direction = new THREE.Vector3(
        (Math.random() - 0.5) * 2,
        (Math.random() - 0.5) * 2,
        (Math.random() - 0.5) * 2,
      ).normalize();
      return {
        id: i,
        position: origin.clone(),
        velocity: direction.multiplyScalar(0.8 + Math.random() * 1.4),
        life: 1,
      };
    });
  }, [active, origin, reducedMotion, burstParticles]);

  useFrame((_, delta) => {
    const mesh = meshRef.current;
    if (!mesh || particlesRef.current.length === 0) {
      return;
    }

    let alive = 0;
    for (const particle of particlesRef.current) {
      particle.life -= delta / BURST_DURATION_S;
      if (particle.life <= 0) {
        continue;
      }
      alive += 1;
      particle.position.addScaledVector(particle.velocity, delta);
      particle.velocity.multiplyScalar(0.96);

      dummy.position.copy(particle.position);
      dummy.scale.setScalar(0.035 * particle.life);
      dummy.updateMatrix();
      mesh.setMatrixAt(particle.id, dummy.matrix);
    }

    mesh.instanceMatrix.needsUpdate = true;

    if (alive === 0) {
      particlesRef.current = [];
    }
  });

  if (!active || !origin || reducedMotion) {
    return null;
  }

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, burstParticles]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial color="#fbbf24" transparent opacity={0.85} />
    </instancedMesh>
  );
}

function GraphEdges({
  edges,
  positions,
}: {
  edges: EvolutionEdge[];
  positions: Map<string, THREE.Vector3>;
}) {
  const geometry = useMemo(() => {
    const points: number[] = [];
    for (const edge of edges) {
      const from = positions.get(edge.from);
      const to = positions.get(edge.to);
      if (!from || !to) {
        continue;
      }
      points.push(from.x, from.y, from.z, to.x, to.y, to.z);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    return geo;
  }, [edges, positions]);

  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color="#22d3ee" transparent opacity={0.45} />
    </lineSegments>
  );
}

function GraphNode({
  node,
  position,
  isNew,
  reducedMotion,
  onSelect,
}: {
  node: EvolutionNode;
  position: THREE.Vector3;
  isNew: boolean;
  reducedMotion: boolean;
  onSelect: (node: EvolutionNode) => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const radius = nodeRadius(node.fitness);
  const color = fitnessColor(node.fitness);
  const isChampion = node.status === "champion";
  const isProposed = node.status === "proposed";

  useFrame(({ clock }) => {
    if (meshRef.current && isProposed && !reducedMotion) {
      const mat = meshRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 0.35 + Math.sin(clock.getElapsedTime() * 4) * 0.25;
    }
    if (ringRef.current && isChampion) {
      ringRef.current.rotation.x += 0.01;
      ringRef.current.rotation.y += 0.015;
    }
  });

  return (
    <group position={position}>
      {isChampion ? (
        <mesh ref={ringRef}>
          <torusGeometry args={[radius + 0.08, 0.012, 8, 24]} />
          <meshBasicMaterial color="#fbbf24" transparent opacity={0.85} />
        </mesh>
      ) : null}
      <mesh
        ref={meshRef}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(node);
        }}
        scale={isNew && !reducedMotion ? 1.15 : 1}
      >
        <sphereGeometry args={[radius, 20, 20]} />
        <meshStandardMaterial
          color={color}
          emissive={isProposed ? "#f59e0b" : color}
          emissiveIntensity={isProposed ? 0.45 : 0.25}
          roughness={0.35}
          metalness={0.55}
        />
      </mesh>
    </group>
  );
}

function ForceGraphScene({
  graph,
  newNodeIds,
  reducedMotion,
  forceTicksPerFrame,
  burstParticles,
  onNodeSelect,
}: {
  graph: EvolutionGraph;
  newNodeIds: string[];
  reducedMotion: boolean;
  forceTicksPerFrame: number;
  burstParticles: number;
  onNodeSelect: (node: EvolutionNode) => void;
}) {
  const simulationRef = useRef<ReturnType<typeof forceSimulation> | null>(null);
  const simNodesRef = useRef<SimNode[]>([]);
  const [positions, setPositions] = useState<Map<string, THREE.Vector3>>(new Map());
  const tickBudgetRef = useRef(240);

  useEffect(() => {
    const simNodes: SimNode[] = graph.nodes.map((node, index) => ({
      ...node,
      x: Math.cos(index) * 1.5,
      y: (index - graph.nodes.length / 2) * 0.35,
      z: Math.sin(index) * 1.5,
    }));

    const links = graph.edges.map((edge) => ({
      source: edge.from,
      target: edge.to,
    }));

    const linkForce = forceLink(links) as unknown as {
      id: (fn: (node: SimNode) => string) => {
        distance: (d: number) => { strength: (s: number) => unknown };
      };
    };
    const collideForce = forceCollide() as unknown as {
      radius: (fn: (node: SimNode) => number) => unknown;
    };
    const chargeForce = forceManyBody() as unknown as {
      strength: (s: number) => unknown;
    };

    const simulation = forceSimulation(simNodes, 3)
      .force("link", linkForce.id((node) => node.id).distance(1.1).strength(0.7))
      .force("charge", chargeForce.strength(-140))
      .force("center", forceCenter(0, 0, 0))
      .force(
        "collide",
        collideForce.radius((node) => nodeRadius(node.fitness) + 0.08),
      )
      .alpha(1)
      .alphaDecay(reducedMotion ? 0.08 : 0.02);

    simulationRef.current = simulation;
    simNodesRef.current = simNodes;
    tickBudgetRef.current = 240;

    return () => {
      simulation.stop();
      simulationRef.current = null;
    };
  }, [graph, reducedMotion]);

  useFrame(() => {
    const simulation = simulationRef.current;
    const simNodes = simNodesRef.current;
    if (!simulation || simNodes.length === 0) {
      return;
    }

    if (simulation.alpha() > 0.02 && tickBudgetRef.current > 0) {
      for (let i = 0; i < forceTicksPerFrame; i += 1) {
        if (simulation.alpha() <= 0.02 || tickBudgetRef.current <= 0) {
          break;
        }
        simulation.tick();
        tickBudgetRef.current -= 1;
      }
    }

    const next = new Map<string, THREE.Vector3>();
    for (const node of simNodes) {
      next.set(node.id, new THREE.Vector3(node.x ?? 0, node.y ?? 0, node.z ?? 0));
    }
    setPositions(next);
  });

  const burstOrigin = useMemo(() => {
    if (newNodeIds.length === 0) {
      return null;
    }
    return positions.get(newNodeIds[0]) ?? null;
  }, [newNodeIds, positions]);

  return (
    <>
      <ambientLight intensity={0.45} />
      <pointLight position={[4, 5, 6]} intensity={1.1} color="#a855f7" />
      <pointLight position={[-5, -3, 4]} intensity={0.7} color="#22d3ee" />

      <GraphEdges edges={graph.edges} positions={positions} />
      {graph.nodes.map((node) => {
        const position = positions.get(node.id);
        if (!position) {
          return null;
        }
        return (
          <GraphNode
            key={node.id}
            node={node}
            position={position}
            isNew={newNodeIds.includes(node.id)}
            reducedMotion={reducedMotion}
            onSelect={onNodeSelect}
          />
        );
      })}

      <MutationBurst
        origin={burstOrigin}
        active={newNodeIds.length > 0}
        reducedMotion={reducedMotion}
        burstParticles={burstParticles}
      />

      <OrbitControls enablePan={false} minDistance={3} maxDistance={12} />
    </>
  );
}

function NodeDetailDialog({
  node,
  incomingEdge,
  open,
  onOpenChange,
}: {
  node: EvolutionNode | null;
  incomingEdge: EvolutionEdge | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!node) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-violet-100">
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
                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"
                style={{ width: `${Math.round(node.fitness * 100)}%` }}
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
                onClick={() => {
                  void approveProposal({
                    hash: node.hash,
                    challenger_name: resolveDefaultChallengerName({ hash: node.hash, challengers: [{ name: node.promptId }] }) ?? node.promptId,
                  })
                    .then(() => toast.success("Mutation approved"))
                    .catch((e) => toast.error(e instanceof Error ? e.message : "Approve failed"));
                }}
              >
                Approve
              </Button>
              <Button
                type="button"
                size="xs"
                variant="secondary"
                onClick={() => {
                  void rejectProposal({ hash: node.hash, reason: "Rejected from Evolution Arena" })
                    .then(() => toast.success("Mutation rejected"))
                    .catch((e) => toast.error(e instanceof Error ? e.message : "Reject failed"));
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
  const currentMode = useCoreStore(selectCurrentMode);
  const renderConfig = useVisualSettingsStore(selectRenderConfig);
  const reducedMotion = prefersReducedMotion || currentMode === "REAL";
  const { graph, newNodeIds, loading, error, clearNewNodes, refresh } = useEvolutionTree();
  const [selectedNode, setSelectedNode] = useState<EvolutionNode | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    if (newNodeIds.length === 0) {
      return;
    }
    const timer = setTimeout(() => {
      clearNewNodes();
    }, BURST_DURATION_S * 1000);
    return () => clearTimeout(timer);
  }, [newNodeIds, clearNewNodes]);

  const incomingEdge = useMemo(() => {
    if (!selectedNode) {
      return null;
    }
    return graph.edges.find((edge) => edge.to === selectedNode.id) ?? null;
  }, [graph.edges, selectedNode]);

  const handleNodeSelect = (node: EvolutionNode) => {
    setSelectedNode(node);
    setDialogOpen(true);
  };

  return (
    <>
      <div
        className={cn("evolution-arena-shell relative min-h-[220px] w-full", className)}
        aria-label={`Evolution arena — ${graph.nodes.length} strategies`}
        role="img"
      >
        <AnimatePresence>
          {loading ? (
            <motion.div
              key="arena-loader"
              className="absolute inset-0 z-20 flex items-center justify-center bg-black/30 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <PanelLoader label="Syncing evolution tree…" />
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
                variant="secondary"
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
            <p className="font-mono text-xs tracking-wide text-cyan-200/90 uppercase">
              No evolution tree yet
            </p>
            <p className="max-w-xs text-[11px] text-muted-foreground">
              Strategies appear here after birth completes and evolution proposals are recorded.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              <Button type="button" size="sm" variant="secondary" onClick={() => void refresh()}>
                Refresh
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
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
          transition={springSoft}
        >
        <Suspense
          fallback={
            <PanelLoader label="Initializing force graph…" className="min-h-[220px]" />
          }
        >
          <VisibilityCanvas
            panelName="Evolution Arena"
            idleLabel="Evolution arena paused — scroll into view"
            camera={{ position: [0, 0, 5.5], fov: 50 }}
          >
            <ForceGraphScene
              graph={graph}
              newNodeIds={newNodeIds}
              reducedMotion={reducedMotion}
              forceTicksPerFrame={renderConfig.forceTicksPerFrame}
              burstParticles={renderConfig.burstParticles}
              onNodeSelect={handleNodeSelect}
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
      />
    </>
  );
}
