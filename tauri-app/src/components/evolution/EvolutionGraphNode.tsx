import { useFrame } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";

import { createEmissiveStrandMaterial } from "@/components/three/helixPrimitives";
import {
  birthScaleFactor,
  evolutionPalette,
  championRingOpacity,
  fitnessGlow,
  nodeRadius,
  type BirthEffectParams,
} from "@/lib/evolutionArenaTheme";
import { getOrganismClock } from "@/lib/organismClockStore";
import type { EvolutionNode } from "@/lib/evolutionTreeTypes";
import type { TradingMode } from "@/store/coreStore";

interface EvolutionGraphNodeProps {
  node: EvolutionNode;
  position: THREE.Vector3;
  isNew: boolean;
  isHovered: boolean;
  reducedMotion: boolean;
  calmMode: boolean;
  mode: TradingMode;
  birthParams: BirthEffectParams;
  onHover: (node: EvolutionNode | null) => void;
  onClick: (node: EvolutionNode) => void;
}

function applyStrandIntensity(
  material: THREE.Material,
  intensity: number,
  primary?: THREE.Color,
  secondary?: THREE.Color,
) {
  if (!(material instanceof THREE.ShaderMaterial)) {
    return;
  }
  material.uniforms.uEmissiveIntensity.value = intensity;
  if (primary) {
    material.uniforms.uColorA.value.copy(primary);
  }
  if (secondary) {
    material.uniforms.uColorB.value.copy(secondary);
  }
}

export function EvolutionGraphNode({
  node,
  position,
  isNew,
  isHovered,
  reducedMotion,
  calmMode,
  mode,
  birthParams,
  onHover,
  onClick,
}: EvolutionGraphNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const haloRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const birthStartRef = useRef<number | null>(null);

  const radius = nodeRadius(node.fitness);
  const glow = fitnessGlow(node.fitness, mode);
  const palette = evolutionPalette(mode);
  const isChampion = node.status === "champion";
  const isProposed = node.status === "proposed";
  const strandMaterial = useRef(
    createEmissiveStrandMaterial({
      color: glow.core,
      secondaryColor: glow.emissive,
      emissiveIntensity: glow.emissiveIntensity,
    }),
  ).current;

  useEffect(() => {
    if (isNew) {
      birthStartRef.current = null;
    }
  }, [isNew, node.id]);

  useFrame(({ clock }) => {
    if (isNew && birthStartRef.current === null) {
      birthStartRef.current = clock.getElapsedTime();
    }

    const elapsed =
      birthStartRef.current === null ? 0 : clock.getElapsedTime() - birthStartRef.current;
    let birthScale = birthScaleFactor(isNew, reducedMotion, elapsed, birthParams.nodeBirthDurationS);
    if (isChampion && isNew && !reducedMotion) {
      const championPop = Math.max(0, 1 - elapsed / (birthParams.nodeBirthDurationS * 1.2));
      birthScale *= 1 + championPop * 0.35;
    }
    const hoverScale = isHovered ? 1.08 : 1;
    const groupScale = birthScale * hoverScale;

    if (meshRef.current) {
      meshRef.current.scale.setScalar(groupScale);
      const mat = meshRef.current.material;
      if (isChampion) {
        const championMat = mat as THREE.MeshPhysicalMaterial;
        let intensity = glow.emissiveIntensity + 0.35;
        if (isNew && !reducedMotion) {
          const bloom = Math.max(0, 1 - elapsed / birthParams.nodeBirthDurationS);
          intensity += bloom * 0.65;
        }
        championMat.emissiveIntensity = intensity;
      } else if (mat instanceof THREE.ShaderMaterial) {
        let intensity = glow.emissiveIntensity;
        const accent = new THREE.Color(palette.accent);
        const emissive = new THREE.Color(glow.emissive);
        if (isProposed && !reducedMotion) {
          const { envelope } = getOrganismClock(mode);
          const amp = calmMode ? 0.12 : 0.22;
          intensity += envelope * amp;
          applyStrandIntensity(mat, intensity, accent, emissive);
        } else {
          applyStrandIntensity(mat, intensity, emissive, accent);
        }
        if (isNew && !reducedMotion) {
          const bloom = Math.max(0, 1 - elapsed / birthParams.nodeBirthDurationS);
          applyStrandIntensity(mat, intensity + bloom * 0.5, emissive, accent);
        }
      }
    }

    if (haloRef.current) {
      const championBoost = isChampion && isNew ? 0.18 : 0;
      const haloOpacity = isHovered ? 0.28 : isNew ? 0.22 + championBoost : isChampion ? 0.2 : 0.14;
      const mat = haloRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = haloOpacity;
      haloRef.current.scale.setScalar(groupScale * (isChampion ? 1.65 : 1.45));
    }

    if (ringRef.current && isChampion && !reducedMotion) {
      const speed = calmMode ? 0.006 : isNew ? 0.018 : 0.01;
      ringRef.current.rotation.x += speed;
      ringRef.current.rotation.y += speed * 1.2;
      if (isNew) {
        const ringMat = ringRef.current.material as THREE.MeshBasicMaterial;
        const pulse = 0.55 + Math.sin(clock.getElapsedTime() * 6) * 0.2;
        ringMat.opacity = championRingOpacity(mode) * pulse;
        ringRef.current.scale.setScalar(1 + Math.max(0, 1 - elapsed / birthParams.nodeBirthDurationS) * 0.25);
      }
    }
  });

  return (
    <group position={position}>
      <mesh ref={haloRef}>
        <sphereGeometry args={[radius, 16, 16]} />
        <meshBasicMaterial
          color={isChampion ? palette.championRing : glow.emissive}
          transparent
          opacity={0.14}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {isChampion ? (
        <mesh ref={ringRef}>
          <torusGeometry args={[radius + 0.07, 0.008, 8, 24]} />
          <meshBasicMaterial
            color={palette.championRing}
            transparent
            opacity={championRingOpacity(mode)}
          />
        </mesh>
      ) : null}

      <mesh
        ref={meshRef}
        onPointerOver={(event) => {
          event.stopPropagation();
          onHover(node);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={(event) => {
          event.stopPropagation();
          onHover(null);
          document.body.style.cursor = "auto";
        }}
        onClick={(event) => {
          event.stopPropagation();
          onClick(node);
        }}
      >
        <sphereGeometry args={[radius, isChampion ? 24 : 20, isChampion ? 24 : 20]} />
        {isChampion ? (
          <meshPhysicalMaterial
            color={palette.championRing}
            emissive={palette.championRing}
            emissiveIntensity={glow.emissiveIntensity + 0.35}
            roughness={0.18}
            metalness={0.82}
            clearcoat={1}
            clearcoatRoughness={0.12}
            reflectivity={0.9}
          />
        ) : (
          <primitive object={strandMaterial} attach="material" />
        )}
      </mesh>
    </group>
  );
}
