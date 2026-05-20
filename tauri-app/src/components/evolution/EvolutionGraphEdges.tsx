import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { edgeGlowColor, edgeGlowHaloOpacity, edgeGlowInnerOpacity } from "@/lib/evolutionArenaTheme";
import type { EvolutionEdge } from "@/lib/evolutionTreeTypes";
import type { TradingMode } from "@/store/coreStore";

interface EvolutionGraphEdgesProps {
  edges: EvolutionEdge[];
  positions: Map<string, THREE.Vector3>;
  calmMode: boolean;
  reducedMotion: boolean;
  mode: TradingMode;
}

function buildLineGeometry(
  edges: EvolutionEdge[],
  positions: Map<string, THREE.Vector3>,
): THREE.BufferGeometry | null {
  const points: number[] = [];
  for (const edge of edges) {
    const from = positions.get(edge.from);
    const to = positions.get(edge.to);
    if (!from || !to) {
      continue;
    }
    points.push(from.x, from.y, from.z, to.x, to.y, to.z);
  }
  if (points.length === 0) {
    return null;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  return geo;
}

export function EvolutionGraphEdges({
  edges,
  positions,
  calmMode,
  reducedMotion,
  mode,
}: EvolutionGraphEdgesProps) {
  const { core, halo } = edgeGlowColor(mode);
  const innerRef = useRef<THREE.LineSegments>(null);

  const geometry = useMemo(
    () => buildLineGeometry(edges, positions),
    [edges, positions],
  );

  useFrame(({ clock }) => {
    const inner = innerRef.current;
    if (!inner || reducedMotion) {
      return;
    }
    const mat = inner.material as THREE.LineBasicMaterial;
    const baseOpacity = edgeGlowInnerOpacity(mode, calmMode);
    const pulse = calmMode ? 0 : Math.sin(clock.getElapsedTime() * 0.8) * 0.06;
    mat.opacity = baseOpacity + pulse;
  });

  if (!geometry) {
    return null;
  }

  return (
    <group>
      <lineSegments geometry={geometry}>
        <lineBasicMaterial color={halo} transparent opacity={edgeGlowHaloOpacity(mode)} depthWrite={false} />
      </lineSegments>
      <lineSegments ref={innerRef} geometry={geometry}>
        <lineBasicMaterial
          color={core}
          transparent
          opacity={edgeGlowInnerOpacity(mode, calmMode)}
        />
      </lineSegments>
    </group>
  );
}
