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
  const particlesRef = useRef<BirthParticle[]>([]);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const count = params.particleCount;

  useEffect(() => {
    if (!active || reducedMotion) {
      particlesRef.current = [];
      return;
    }

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
        .multiplyScalar(0.4 + Math.random() * 0.9)
        .add(spread.multiplyScalar(0.35));
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
      particle.velocity.multiplyScalar(0.94);

      dummy.position.copy(particle.position);
      dummy.scale.setScalar(0.028 * particle.life);
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
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial
        color={palette.birthPrimary}
        transparent
        opacity={0.55}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </instancedMesh>
  );
}