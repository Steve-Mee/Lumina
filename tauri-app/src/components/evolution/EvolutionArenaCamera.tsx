import { OrbitControls } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

export function arenaCameraDistance(nodeCount: number): number {
  if (nodeCount <= 3) return 2.6;
  if (nodeCount <= 8) return 3.6;
  if (nodeCount <= 20) return 4.8;
  return 6.4;
}

export function ArenaCameraRig({
  nodeCount,
  calmMode,
  reducedMotion,
  focusTarget,
}: {
  nodeCount: number;
  calmMode: boolean;
  reducedMotion: boolean;
  focusTarget: THREE.Vector3 | null;
}) {
  const { camera } = useThree();
  const orbitRef = useRef(0);
  const focusRef = useRef<THREE.Vector3 | null>(null);
  const distance = arenaCameraDistance(nodeCount);
  const basePosition = useMemo(() => new THREE.Vector3(0, 0, distance), [distance]);

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
        new THREE.Vector3(focus.x * 0.22, focus.y * 0.18 + 0.35, distance - 0.35),
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
      camera.position.set(sway, lift, distance);
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
      minDistance={distance}
      maxDistance={distance}
    />
  );
}
