import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { OrganismGlass } from "@/components/organism/OrganismGlass";
import { useLerpedColor } from "@/components/three/helixPrimitives";
import { getOrganismClock } from "@/lib/organismClockStore";
import {
  organismHasAnatomy,
  type OrganismMorphology,
} from "@/lib/organism/phaseMorphology";

function OrganismFace({ open }: { open: number }) {
  const cyan = useLerpedColor("#67f7ff");
  const violet = useLerpedColor("#c084fc");
  if (open < 0.02) {
    return null;
  }
  return (
    <group position={[0, 0.95, 0.2]} scale={open}>
      <mesh position={[0, 0, 0.02]}>
        <sphereGeometry args={[0.28, 24, 24]} />
        <meshBasicMaterial color="#061018" transparent opacity={0.88} />
      </mesh>
      <mesh position={[-0.1, 0.04, 0.22]} rotation={[0, 0.2, 0.28]}>
        <boxGeometry args={[0.14, 0.036, 0.03]} />
        <meshBasicMaterial color={cyan} transparent opacity={1} />
      </mesh>
      <mesh position={[0.1, 0.04, 0.22]} rotation={[0, -0.2, -0.28]}>
        <boxGeometry args={[0.14, 0.036, 0.03]} />
        <meshBasicMaterial color={violet} transparent opacity={1} />
      </mesh>
    </group>
  );
}

function OrganismArmor({ amount }: { amount: number }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = useLerpedColor(amount > 0.6 ? "#c9b896" : "#a78bfa");
  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.1;
    }
  });
  if (amount < 0.05) {
    return null;
  }
  return (
    <mesh ref={meshRef} scale={0.92 + amount * 0.16}>
      <icosahedronGeometry args={[1.12, 1]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.1 + amount * 0.18}
        wireframe
        depthWrite={false}
      />
    </mesh>
  );
}

function OrganismConstellation({ density }: { density: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const count = Math.round(28 * density);
  useFrame(() => {
    if (!meshRef.current || count < 1) {
      return;
    }
    const { elapsedSec } = getOrganismClock("SIM");
    for (let i = 0; i < count; i++) {
      const t = i / count;
      const angle = t * Math.PI * 7 + elapsedSec * 0.12;
      dummy.position.set(
        Math.cos(angle) * (0.16 + (i % 4) * 0.05),
        (t - 0.48) * 2.2,
        Math.sin(angle) * (0.16 + (i % 4) * 0.05),
      );
      dummy.scale.setScalar(0.012 + (i % 5) * 0.004);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
    }
    meshRef.current.instanceMatrix.needsUpdate = true;
  });
  if (count < 1) {
    return null;
  }
  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial color="#e0f7ff" transparent opacity={0.55} depthWrite={false} />
    </instancedMesh>
  );
}

export function OrganismAnatomy({
  morph,
  reducedMotion,
}: {
  morph: OrganismMorphology;
  reducedMotion: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  useFrame(() => {
    if (!groupRef.current) {
      return;
    }
    const { envelope } = getOrganismClock("SIM");
    const lift = reducedMotion ? 0 : Math.sin(envelope * Math.PI * 2) * morph.hover * 0.07;
    groupRef.current.position.y = lift;
  });
  if (!organismHasAnatomy(morph)) {
    return null;
  }
  return (
    <group ref={groupRef}>
      <OrganismGlass opacity={morph.bodyOpacity} />
      <OrganismFace open={morph.eyeOpen} />
      <OrganismArmor amount={morph.armor} />
      <OrganismConstellation density={morph.constellation} />
    </group>
  );
}
