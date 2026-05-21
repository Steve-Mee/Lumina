import { OrbitControls } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from "d3-force-3d";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { CinematicBloom } from "@/components/cockpit/CinematicBloom";
import { EvolutionGraphEdges } from "@/components/evolution/EvolutionGraphEdges";
import { EvolutionGraphNode } from "@/components/evolution/EvolutionGraphNode";
import { MutationBirthEffect } from "@/components/evolution/MutationBirthEffect";
import {
  birthEffectParams,
  dustParticleCount,
  evolutionDustDriftScale,
  evolutionPalette,
  nodeRadius,
} from "@/lib/evolutionArenaTheme";
import type {
  EvolutionGraph,
  EvolutionNode,
} from "@/lib/evolutionTreeTypes";
import type { RenderConfig, VisualQuality } from "@/lib/visualQualityPresets";
import type { TradingMode } from "@/store/coreStore";

interface SimNode extends EvolutionNode {
  x: number;
  y: number;
  z: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

interface EvolutionForceGraphSceneProps {
  graph: EvolutionGraph;
  newNodeIds: string[];
  reducedMotion: boolean;
  calmMode: boolean;
  mode: TradingMode;
  visualQuality: VisualQuality;
  renderConfig: RenderConfig;
  onNodeClick: (node: EvolutionNode) => void;
}

const LOCKED_CAMERA_DISTANCE = 5.5;

function ArenaCameraRig({
  calmMode,
  reducedMotion,
  focusTarget,
}: {
  calmMode: boolean;
  reducedMotion: boolean;
  focusTarget: THREE.Vector3 | null;
}) {
  const { camera } = useThree();
  const orbitRef = useRef(0);
  const focusRef = useRef<THREE.Vector3 | null>(null);
  const basePosition = useMemo(
    () => new THREE.Vector3(0, 0, LOCKED_CAMERA_DISTANCE),
    [],
  );

  useEffect(() => {
    camera.position.copy(basePosition);
    camera.lookAt(0, 0, 0);
  }, [basePosition, camera]);

  useEffect(() => {
    focusRef.current = focusTarget;
  }, [focusTarget]);

  useFrame((_, delta) => {
    if (reducedMotion) {
      camera.position.copy(basePosition);
      camera.lookAt(0, 0, 0);
      return;
    }

    const focus = focusRef.current;
    if (focus) {
      const eased = basePosition.clone().lerp(
        new THREE.Vector3(focus.x * 0.22, focus.y * 0.18 + 0.35, LOCKED_CAMERA_DISTANCE - 0.35),
        0.08,
      );
      camera.position.lerp(eased, Math.min(1, delta * 3.5));
      camera.lookAt(focus.x * 0.15, focus.y * 0.12, 0);
      return;
    }

    if (!calmMode) {
      orbitRef.current += delta * 0.14;
      const sway = Math.sin(orbitRef.current) * 0.28;
      const lift = Math.sin(orbitRef.current * 0.7) * 0.08;
      camera.position.set(sway, lift, LOCKED_CAMERA_DISTANCE);
      camera.lookAt(0, 0, 0);
      return;
    }

    camera.position.copy(basePosition);
    camera.lookAt(0, 0, 0);
  });

  return (
    <OrbitControls
      enablePan={false}
      enableZoom={false}
      enableRotate={false}
      minDistance={LOCKED_CAMERA_DISTANCE}
      maxDistance={LOCKED_CAMERA_DISTANCE}
    />
  );
}

function AmbientDust({
  count,
  palette,
  reducedMotion,
  mode,
}: {
  count: number;
  palette: ReturnType<typeof evolutionPalette>;
  reducedMotion: boolean;
  mode: TradingMode;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const driftScale = evolutionDustDriftScale(mode);
  const particles = useMemo(() => {
    if (count === 0) {
      return [];
    }
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      offset: Math.random() * Math.PI * 2,
      radius: 1.8 + Math.random() * 2.2,
      speed: (0.08 + Math.random() * 0.12) * driftScale,
      y: (Math.random() - 0.5) * 2.5,
    }));
  }, [count, driftScale]);

  useFrame(({ clock }) => {
    const mesh = meshRef.current;
    if (!mesh || reducedMotion || particles.length === 0) {
      return;
    }
    const t = clock.getElapsedTime();
    const wobble = mode === "SIM";
    for (const p of particles) {
      const angle = t * p.speed + p.offset;
      const wobbleY = wobble ? Math.sin(t * 0.4 + p.offset) * 0.04 : 0;
      dummy.position.set(
        Math.cos(angle) * p.radius,
        p.y + wobbleY,
        Math.sin(angle) * p.radius,
      );
      dummy.scale.setScalar(0.012 + (p.id % 3) * 0.004);
      dummy.updateMatrix();
      mesh.setMatrixAt(p.id, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  });

  if (count === 0 || reducedMotion) {
    return null;
  }

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 4, 4]} />
      <meshBasicMaterial
        color={palette.primary}
        transparent
        opacity={0.28}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </instancedMesh>
  );
}

export function EvolutionForceGraphScene({
  graph,
  newNodeIds,
  reducedMotion,
  calmMode,
  mode,
  visualQuality,
  renderConfig,
  onNodeClick,
}: EvolutionForceGraphSceneProps) {
  const simulationRef = useRef<ReturnType<typeof forceSimulation> | null>(null);
  const simNodesRef = useRef<SimNode[]>([]);
  const [positions, setPositions] = useState<Map<string, THREE.Vector3>>(new Map());
  const [cameraFocus, setCameraFocus] = useState<THREE.Vector3 | null>(null);
  const tickBudgetRef = useRef(240);
  const prevNewNodeIdsRef = useRef<string[]>([]);
  const focusTimerRef = useRef<number | null>(null);

  const palette = evolutionPalette(mode);
  const birthParams = birthEffectParams(
    mode,
    visualQuality,
    renderConfig.burstParticles,
    renderConfig.particleScale,
  );
  const dustCount = dustParticleCount(mode, visualQuality);

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
      .force("charge", chargeForce.strength(calmMode ? -100 : -140))
      .force("center", forceCenter(0, 0, 0))
      .force(
        "collide",
        collideForce.radius((node) => nodeRadius(node.fitness) + 0.08),
      )
      .alpha(1)
      .alphaDecay(reducedMotion ? 0.06 : calmMode ? 0.025 : 0.02);

    simulationRef.current = simulation;
    simNodesRef.current = simNodes;
    tickBudgetRef.current = 240;

    return () => {
      simulation.stop();
      simulationRef.current = null;
    };
  }, [graph, reducedMotion, calmMode]);

  useEffect(() => {
    const simulation = simulationRef.current;
    if (!simulation) {
      return;
    }
    const added = newNodeIds.filter((id) => !prevNewNodeIdsRef.current.includes(id));
    if (added.length > 0) {
      simulation.alpha(Math.max(simulation.alpha(), calmMode ? 0.25 : 0.35));
      tickBudgetRef.current = Math.max(tickBudgetRef.current, 120);
    }
    prevNewNodeIdsRef.current = newNodeIds;
  }, [newNodeIds, calmMode]);

  useEffect(() => {
    if (newNodeIds.length === 0 || reducedMotion) {
      return;
    }
    const latestId = newNodeIds[newNodeIds.length - 1];
    const target = positions.get(latestId);
    const latestNode = graph.nodes.find((node) => node.id === latestId);
    const championBirth = latestNode?.status === "champion";
    if (!target) {
      return;
    }
    setCameraFocus(target.clone());
    if (focusTimerRef.current != null) {
      window.clearTimeout(focusTimerRef.current);
    }
    focusTimerRef.current = window.setTimeout(() => {
      setCameraFocus(null);
      focusTimerRef.current = null;
    }, championBirth ? 1500 : 900);
    return () => {
      if (focusTimerRef.current != null) {
        window.clearTimeout(focusTimerRef.current);
      }
    };
  }, [newNodeIds, positions, reducedMotion]);

  useFrame(() => {
    const simulation = simulationRef.current;
    const simNodes = simNodesRef.current;
    if (!simulation || simNodes.length === 0) {
      return;
    }

    if (simulation.alpha() > 0.02 && tickBudgetRef.current > 0) {
      for (let i = 0; i < renderConfig.forceTicksPerFrame; i += 1) {
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

  const birthTargets = useMemo(() => {
    return newNodeIds
      .map((nodeId) => {
        const target = positions.get(nodeId);
        const edge = graph.edges.find((e) => e.to === nodeId);
        const parentPos = edge ? positions.get(edge.from) : null;
        return {
          nodeId,
          origin: parentPos ?? target,
          target: target ?? parentPos,
        };
      })
      .filter((b) => b.origin && b.target) as Array<{
      nodeId: string;
      origin: THREE.Vector3;
      target: THREE.Vector3;
    }>;
  }, [newNodeIds, positions, graph.edges]);

  return (
    <>
      <ambientLight intensity={calmMode ? 0.4 : 0.45} />
      <pointLight position={[4, 5, 6]} intensity={calmMode ? 0.85 : 1.05} color={palette.secondary} />
      <pointLight position={[-5, -3, 4]} intensity={0.65} color={palette.primary} />

      <AmbientDust
        count={dustCount}
        palette={palette}
        reducedMotion={reducedMotion}
        mode={mode}
      />

      <EvolutionGraphEdges
        edges={graph.edges}
        positions={positions}
        calmMode={calmMode}
        reducedMotion={reducedMotion}
        mode={mode}
      />

      {graph.nodes.map((node) => {
        const position = positions.get(node.id);
        if (!position) {
          return null;
        }
        return (
          <group key={node.id} position={position}>
            <EvolutionGraphNode
              node={node}
              position={new THREE.Vector3(0, 0, 0)}
              isNew={newNodeIds.includes(node.id)}
              isHovered={false}
              reducedMotion={reducedMotion}
              calmMode={calmMode}
              mode={mode}
              birthParams={birthParams}
              onHover={() => undefined}
              onClick={onNodeClick}
            />
          </group>
        );
      })}

      {birthTargets.map(({ nodeId, origin, target }) => (
        <MutationBirthEffect
          key={nodeId}
          nodeId={nodeId}
          origin={origin}
          target={target}
          active
          reducedMotion={reducedMotion}
          params={birthParams}
          palette={palette}
        />
      ))}

      <ArenaCameraRig
        calmMode={calmMode}
        reducedMotion={reducedMotion}
        focusTarget={cameraFocus}
      />
      <CinematicBloom mode={mode} reducedMotion={reducedMotion} visualQuality={visualQuality} />
    </>
  );
}
