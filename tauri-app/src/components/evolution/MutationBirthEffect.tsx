import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import type { BirthEffectParams, EvolutionPalette } from "@/lib/evolutionArenaTheme";

interface BirthParticle {
  id: number;
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  life: number;
}

interface MutationBirthEffectProps {
  nodeId: string;
  origin: THREE.Vector3;
  target: THREE.Vector3;
  active: boolean;
  reducedMotion: boolean;
  params: BirthEffectParams;
  palette: EvolutionPalette;
}

export function MutationBirthEffect({
  nodeId,
  origin,
  target,
  active,
  reducedMotion,
  params,
  palette,
}: MutationBirthEffectProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const burstRef = useRef<THREE.Mesh>(null);
  const particlesRef = useRef<BirthParticle[]>([]);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const burstLifeRef = useRef(1);
  const count = params.particleCount;

  useEffect(() => {
    if (!active || reducedMotion) {
      particlesRef.current = [];
      burstLifeRef.current = 0;
      return;
    }

    burstLifeRef.current = 1;

    const direction = new THREE.Vector3().subVectors(target, origin);
    if (direction.lengthSq() < 0.001) {
      direction.set(0, 1, 0);
    } else {
      direction.normalize();
    }

    particlesRef.current = Array.from({ length: count }, (_, i) => {
      const spread = new THREE.Vector3(
        (Math.random() - 0.5) * params.spread,
        (Math.random() - 0.5) * params.spread,
        (Math.random() - 0.5) * params.spread,
      );
      const velocity = direction
        .clone()
        .multiplyScalar(0.55 + Math.random() * 1.1)
        .add(spread.multiplyScalar(0.45));
      const t = Math.random();
      const position = origin.clone().lerp(target, t * 0.35);
      return {
        id: i,
        position,
        velocity,
        life: 0.85 + Math.random() * 0.15,
      };
    });
  }, [active, count, origin, target, reducedMotion, params.spread, nodeId]);

  useFrame((_, delta) => {
    const mesh = meshRef.current;
    const burst = burstRef.current;
    if (burst && burstLifeRef.current > 0) {
      burstLifeRef.current -= delta / (params.durationS * 0.85);
      const life = Math.max(0, burstLifeRef.current);
      burst.scale.setScalar(0.35 + (1 - life) * 1.6);
      const material = burst.material as THREE.MeshBasicMaterial;
      material.opacity = life * 0.75;
    }

    if (!mesh || particlesRef.current.length === 0) {
      return;
    }

    let alive = 0;
    for (const particle of particlesRef.current) {
      particle.life -= delta / params.durationS;
      if (particle.life <= 0) {
        continue;
      }
      alive += 1;
      particle.position.addScaledVector(particle.velocity, delta);
      particle.velocity.multiplyScalar(0.92);

      dummy.position.copy(particle.position);
      dummy.scale.setScalar(0.034 * particle.life);
      dummy.updateMatrix();
      mesh.setMatrixAt(particle.id, dummy.matrix);
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (alive === 0) {
      particlesRef.current = [];
    }
  });

  if (!active || reducedMotion) {
    return null;
  }

  return (
    <group position={target}>
      <mesh ref={burstRef}>
        <sphereGeometry args={[0.2, 16, 16]} />
        <meshBasicMaterial
          color={palette.birthPrimary}
          transparent
          opacity={0.75}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
        <sphereGeometry args={[1, 6, 6]} />
        <meshBasicMaterial
          color={palette.birthPrimary}
          transparent
          opacity={0.65}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </instancedMesh>
    </group>
  );
}
