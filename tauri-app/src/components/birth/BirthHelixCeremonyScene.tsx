import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { CinematicBloom } from "@/components/cockpit/CinematicBloom";
import {
  coreSphereSegments,
  DoubleHelixStrands,
  particleSphereSegments,
  useLerpedColor,
} from "@/components/three/helixPrimitives";
import { getOrganismClock } from "@/lib/organismClockStore";
import { BIRTH_HELIX_HEIGHT } from "@/lib/birthHelixGeometry";
import {
  birthHelixAgitation,
  birthHelixPalette,
  type BirthHelixPalette,
} from "@/lib/birthHelixTheme";
import type { VisualQuality } from "@/lib/visualQualityPresets";

export interface CeremonyHelixSceneProps {
  activating: boolean;
  primed: boolean;
  reducedMotion: boolean;
  particleCount: number;
  emissiveBoost: number;
  visualQuality: VisualQuality;
  tubeSegments: number;
}

function clampPulse(value: number): number {
  return Math.min(1, Math.max(0.28, value));
}

function CeremonyHeartCore({
  palette,
  agitation,
  pulseSpeed,
  reducedMotion,
  activating,
  visualQuality,
}: {
  palette: BirthHelixPalette;
  agitation: number;
  pulseSpeed: number;
  reducedMotion: boolean;
  activating: boolean;
  visualQuality: VisualQuality;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = useLerpedColor(palette.accent);
  const [width, height] = coreSphereSegments(visualQuality);

  useFrame(() => {
    if (!meshRef.current) {
      return;
    }
    const { elapsedSec: t, envelope } = getOrganismClock("SIM");
    const pulse = reducedMotion
      ? 0.32 + agitation * 0.12
      : 0.22 +
        envelope * 0.24 +
        Math.sin(t * pulseSpeed * 2) * 0.1 +
        agitation * 0.14 +
        (activating ? 0.1 : 0);
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = clampPulse(pulse) * 0.85;
    meshRef.current.scale.setScalar(0.4 + clampPulse(pulse) * 0.22);
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.38, width, height]} />
      <meshBasicMaterial color={color} transparent opacity={0.35} depthWrite={false} />
    </mesh>
  );
}

function CeremonyAuraHalo({
  palette,
  reducedMotion,
  visualQuality,
}: {
  palette: BirthHelixPalette;
  reducedMotion: boolean;
  visualQuality: VisualQuality;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = useLerpedColor(palette.primary, 0.05);
  const [width, height] = coreSphereSegments(visualQuality);

  useFrame(() => {
    if (!meshRef.current) {
      return;
    }
    const { envelope } = getOrganismClock("SIM");
    const breathe = reducedMotion ? 1 : 1 + (envelope - 0.5) * 0.08;
    meshRef.current.scale.setScalar(0.88 * breathe);
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = 0.14 + envelope * 0.1;
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.72, width, height]} />
      <meshBasicMaterial color={color} transparent opacity={0.12} depthWrite={false} />
    </mesh>
  );
}

function CeremonyOrbitalRings({ reducedMotion }: { reducedMotion: boolean }) {
  const outerRef = useRef<THREE.Mesh>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const dashRef = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (reducedMotion) {
      return;
    }
    if (outerRef.current) {
      outerRef.current.rotation.z += delta * 0.14;
    }
    if (innerRef.current) {
      innerRef.current.rotation.x += delta * 0.1;
      innerRef.current.rotation.y -= delta * 0.06;
    }
    if (dashRef.current) {
      dashRef.current.rotation.y += delta * 0.18;
    }
  });

  return (
    <group>
      <mesh ref={outerRef} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.92, 0.98, 64]} />
        <meshBasicMaterial
          color="#00f0ff"
          transparent
          opacity={0.2}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
      <mesh ref={dashRef} rotation={[0.55, 0.35, 0]}>
        <ringGeometry args={[0.72, 0.76, 48]} />
        <meshBasicMaterial
          color="#a78bfa"
          transparent
          opacity={0.16}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
      <mesh ref={innerRef} rotation={[Math.PI / 2.4, 0.2, 0]}>
        <ringGeometry args={[0.58, 0.62, 40]} />
        <meshBasicMaterial
          color="#67f7ff"
          transparent
          opacity={0.12}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

function CeremonyHelixStrands({
  palette,
  agitation,
  reducedMotion,
  activating,
  primed,
  emissiveBoost,
  tubeSegments,
}: {
  palette: BirthHelixPalette;
  agitation: number;
  reducedMotion: boolean;
  activating: boolean;
  primed: boolean;
  emissiveBoost: number;
  tubeSegments: number;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const emissive = (0.32 + agitation * 0.42) * emissiveBoost;

  useFrame((_, delta) => {
    if (!groupRef.current) {
      return;
    }
    const rotSpeed = reducedMotion ? 0.06 : activating ? 0.42 : primed ? 0.24 : 0.16;
    groupRef.current.rotation.y += delta * rotSpeed;
    const { envelope } = getOrganismClock("SIM");
    const breathe = 0.92 * (1 + (envelope - 0.5) * 0.08 + agitation * 0.05);
    groupRef.current.scale.setScalar(breathe);
  });

  return (
    <DoubleHelixStrands
      groupRef={groupRef}
      primaryHex={palette.primary}
      secondaryHex={palette.secondary}
      emissiveIntensity={emissive}
      radius={0.56}
      tubeRadius={0.052}
      segments={tubeSegments}
    />
  );
}

function CeremonyParticleField({
  palette,
  agitation,
  reducedMotion,
  particleCount,
  activating,
  primed,
  visualQuality,
}: {
  palette: BirthHelixPalette;
  agitation: number;
  reducedMotion: boolean;
  particleCount: number;
  activating: boolean;
  primed: boolean;
  visualQuality: VisualQuality;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const [particleWidth, particleHeight] = particleSphereSegments(visualQuality);

  const primaryColor = useMemo(() => new THREE.Color(palette.primary), [palette.primary]);
  const accentColor = useMemo(() => new THREE.Color(palette.accent), [palette.accent]);
  const secondaryColor = useMemo(() => new THREE.Color(palette.secondary), [palette.secondary]);
  const blendedColor = useMemo(() => {
    const c = primaryColor.clone();
    c.lerp(accentColor, 0.25);
    c.lerp(secondaryColor, 0.15);
    return c;
  }, [primaryColor, accentColor, secondaryColor]);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) {
      return;
    }
    mesh.instanceColor = new THREE.InstancedBufferAttribute(
      new Float32Array(particleCount * 3),
      3,
    );
  }, [particleCount]);

  const basePositions = useMemo(() => {
    const positions: THREE.Vector3[] = [];
    for (let i = 0; i < particleCount; i++) {
      const theta = (i / particleCount) * Math.PI * 2 * 4;
      const radius =
        activating || primed ? 0.7 + (i % 5) * 0.03 : 0.88 + (i % 5) * 0.04;
      const y = ((i % 17) / 17 - 0.5) * BIRTH_HELIX_HEIGHT * 0.95;
      positions.push(
        new THREE.Vector3(Math.cos(theta) * radius, y, Math.sin(theta) * radius),
      );
    }
    return positions;
  }, [particleCount, activating, primed]);

  useFrame((_state, delta) => {
    if (!meshRef.current) {
      return;
    }
    const { elapsedSec: t, envelope } = getOrganismClock("SIM");
    const orbitSpeed = reducedMotion ? 0.1 : 0.18 + agitation * 0.55;
    const turbulence = reducedMotion ? 0.02 : 0.035 + agitation * 0.1;
    const breathe = 1 + (envelope - 0.5) * 0.06;
    const corePull = activating ? 0.28 : primed ? 0.14 : 0;

    for (let i = 0; i < particleCount; i++) {
      const base = basePositions[i];
      const orbitAngle = t * orbitSpeed + i * 0.15;
      const pull = 1 - corePull;
      dummy.position.set(
        base.x * breathe * pull + Math.sin(orbitAngle * 2.1 + i) * turbulence,
        base.y + Math.cos(orbitAngle * 1.7 + i * 0.5) * turbulence * 0.5,
        base.z * breathe * pull + Math.sin(orbitAngle * 1.9 + i * 0.3) * turbulence,
      );
      dummy.scale.setScalar(0.011 + (i % 4) * 0.0025 + agitation * 0.006);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
      const tint = blendedColor.clone();
      if (i % 3 === 0) {
        tint.lerp(accentColor, 0.35);
      } else if (i % 3 === 1) {
        tint.lerp(secondaryColor, 0.25);
      }
      meshRef.current.setColorAt(i, tint);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }
    meshRef.current.rotation.y += delta * orbitSpeed * 0.1;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, particleCount]}>
      <sphereGeometry args={[1, particleWidth, particleHeight]} />
      <meshBasicMaterial transparent opacity={0.32} toneMapped={false} />
    </instancedMesh>
  );
}

export function CeremonyHelixScene({
  activating,
  primed,
  reducedMotion,
  particleCount,
  emissiveBoost,
  visualQuality,
  tubeSegments,
}: CeremonyHelixSceneProps) {
  const palette = birthHelixPalette(activating, primed);
  const agitation = birthHelixAgitation(activating, primed);
  const lightIntensity = 0.65 + agitation * 0.55;

  return (
    <>
      <ambientLight intensity={0.24 + agitation * 0.12} />
      <pointLight position={[3, 4, 5]} intensity={lightIntensity} color={palette.primary} />
      <pointLight position={[-4, -2, 3]} intensity={lightIntensity * 0.5} color={palette.secondary} />

      <CeremonyOrbitalRings reducedMotion={reducedMotion} />
      <CeremonyAuraHalo
        palette={palette}
        reducedMotion={reducedMotion}
        visualQuality={visualQuality}
      />
      <CeremonyHeartCore
        palette={palette}
        agitation={agitation}
        pulseSpeed={palette.pulseSpeed}
        reducedMotion={reducedMotion}
        activating={activating}
        visualQuality={visualQuality}
      />
      <CeremonyHelixStrands
        palette={palette}
        agitation={agitation}
        reducedMotion={reducedMotion}
        activating={activating}
        primed={primed}
        emissiveBoost={emissiveBoost}
        tubeSegments={tubeSegments}
      />
      <CeremonyParticleField
        key={particleCount}
        palette={palette}
        agitation={agitation}
        reducedMotion={reducedMotion}
        particleCount={particleCount}
        activating={activating}
        primed={primed}
        visualQuality={visualQuality}
      />
      <CinematicBloom
        mode="SIM"
        reducedMotion={reducedMotion}
        visualQuality={visualQuality}
        intensity={0.28}
        disableChromaticAberration
      />
    </>
  );
}
