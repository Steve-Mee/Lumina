import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { CinematicBloom } from "@/components/cockpit/CinematicBloom";
import {
  createStrandGradientMaterial,
  useLerpedColor,
} from "@/components/three/helixPrimitives";
import { getOrganismClock } from "@/lib/organismClockStore";
import {
  BIRTH_HELIX_HEIGHT,
  BIRTH_RUNG_COUNT,
  buildHelixCurve,
  helixPoint,
} from "@/lib/birthHelixGeometry";
import {
  birthHelixAgitation,
  birthHelixPalette,
  type BirthHelixPalette,
} from "@/lib/birthHelixTheme";
import type { VisualQuality } from "@/lib/visualQualityPresets";

export interface LegacyHelixSceneProps {
  activating: boolean;
  primed: boolean;
  reducedMotion: boolean;
  particleCount: number;
  emissiveBoost: number;
  visualQuality: VisualQuality;
  tubeSegments: number;
}

function CoreGlow({
  palette,
  agitation,
  pulseSpeed,
  reducedMotion,
  activating,
}: {
  palette: BirthHelixPalette;
  agitation: number;
  pulseSpeed: number;
  reducedMotion: boolean;
  activating: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = useLerpedColor(palette.accent);

  useFrame(() => {
    if (!meshRef.current) {
      return;
    }
    const { elapsedSec: t, envelope } = getOrganismClock("SIM");
    const pulse = reducedMotion
      ? 0.35
      : 0.2 +
        envelope * 0.22 +
        Math.sin(t * pulseSpeed * 2) * 0.12 +
        agitation * 0.18 +
        (activating ? 0.12 : 0);
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = pulse;
    meshRef.current.scale.setScalar(0.48 + pulse * 0.35);
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.5, 24, 24]} />
      <meshBasicMaterial color={color} transparent opacity={0.35} depthWrite={false} />
    </mesh>
  );
}

function DnaHelix({
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
  const rungRefs = useRef<(THREE.Mesh | null)[]>([]);
  const primaryColor = useLerpedColor(palette.primary);
  const secondaryColor = useLerpedColor(palette.secondary);
  const accentColor = useLerpedColor(palette.accent);
  const radius = 0.55;
  const curveA = useMemo(() => buildHelixCurve(0, radius, 0), []);
  const curveB = useMemo(() => buildHelixCurve(1, radius, 0), []);

  const rungs = useMemo(
    () => Array.from({ length: BIRTH_RUNG_COUNT }, (_, i) => i / (BIRTH_RUNG_COUNT - 1)),
    [],
  );

  const tubeEmissive = (0.4 + agitation * 0.5) * emissiveBoost;
  const primaryMat = useMemo(
    () =>
      createStrandGradientMaterial({
        color: palette.primary,
        secondaryColor: palette.secondary,
        emissiveIntensity: tubeEmissive,
      }),
    [palette.primary, palette.secondary, tubeEmissive],
  );
  const secondaryMat = useMemo(
    () =>
      createStrandGradientMaterial({
        color: palette.secondary,
        secondaryColor: palette.primary,
        emissiveIntensity: tubeEmissive * 0.9,
      }),
    [palette.secondary, palette.primary, tubeEmissive],
  );

  const rungMaterials = useMemo(
    () =>
      rungs.map((_, index) =>
        createStrandGradientMaterial({
          color: palette.accent,
          secondaryColor: palette.primary,
          emissiveIntensity: (0.25 + (index % 3) * 0.05) * emissiveBoost,
          transparent: true,
          opacity: 0.85,
        }),
      ),
    [rungs, palette.accent, palette.primary, emissiveBoost],
  );

  useFrame((_, delta) => {
    if (!groupRef.current) {
      return;
    }
    primaryMat.uniforms.uColorA.value.copy(primaryColor);
    primaryMat.uniforms.uColorB.value.copy(secondaryColor);
    primaryMat.uniforms.uEmissiveIntensity.value = tubeEmissive;
    secondaryMat.uniforms.uColorA.value.copy(secondaryColor);
    secondaryMat.uniforms.uColorB.value.copy(primaryColor);
    secondaryMat.uniforms.uEmissiveIntensity.value = tubeEmissive * 0.9;

    const rotSpeed = reducedMotion ? 0.06 : activating ? 0.52 : primed ? 0.28 : 0.18;
    groupRef.current.rotation.y += delta * rotSpeed;

    const { envelope } = getOrganismClock("SIM");
    const breathe = 1 + (envelope - 0.5) * 0.12 + agitation * 0.08;
    groupRef.current.scale.setScalar(breathe);

    const reveal = activating
      ? 0.28 + envelope * 0.72
      : primed
        ? 0.28 + envelope * 0.45
        : 0.28;
    rungs.forEach((_, index) => {
      const mesh = rungRefs.current[index];
      const mat = rungMaterials[index];
      if (!mesh || !mat) {
        return;
      }
      mat.uniforms.uColorA.value.copy(accentColor);
      mat.uniforms.uColorB.value.copy(primaryColor);
      const threshold = index / (BIRTH_RUNG_COUNT - 1);
      mat.uniforms.uOpacity.value = threshold <= reveal ? 0.85 : 0.04;
    });
  });

  return (
    <group ref={groupRef}>
      <mesh material={primaryMat}>
        <tubeGeometry args={[curveA, tubeSegments, 0.04, 8, false]} />
      </mesh>
      <mesh material={secondaryMat}>
        <tubeGeometry args={[curveB, tubeSegments, 0.04, 8, false]} />
      </mesh>

      {rungs.map((rungT, index) => {
        const a = helixPoint(rungT, 0, radius, 0);
        const b = helixPoint(rungT, 1, radius, 0);
        const midpoint = a.clone().add(b).multiplyScalar(0.5);
        const direction = b.clone().sub(a);
        const length = direction.length();
        const orientation = new THREE.Quaternion().setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          direction.normalize(),
        );
        return (
          <mesh
            key={index}
            ref={(node) => {
              rungRefs.current[index] = node;
            }}
            position={midpoint}
            quaternion={orientation}
            material={rungMaterials[index]}
          >
            <cylinderGeometry args={[0.016, 0.016, length, 6]} />
          </mesh>
        );
      })}
    </group>
  );
}

function SynapseAccents({
  activating,
  visualQuality,
}: {
  activating: boolean;
  visualQuality: VisualQuality;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const radius = 0.55;
  const synapseCount = 5;

  const lines = useMemo(() => {
    if (!activating || visualQuality === "low") {
      return [];
    }
    return Array.from({ length: synapseCount }, (_, index) => {
      const rungT = (index + 1) / (synapseCount + 1);
      const target = helixPoint(rungT, (index % 2) as 0 | 1, radius, 0);
      const geometry = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0, 0),
        target,
      ]);
      const material = new THREE.LineBasicMaterial({
        color: "#67f7ff",
        transparent: true,
        opacity: 0.14,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      return new THREE.Line(geometry, material);
    });
  }, [activating, visualQuality]);

  useFrame(({ clock }) => {
    if (!groupRef.current) {
      return;
    }
    const pulse = 0.1 + Math.sin(clock.elapsedTime * 2.4) * 0.04;
    groupRef.current.children.forEach((child) => {
      const mat = (child as THREE.Line).material as THREE.LineBasicMaterial;
      mat.opacity = pulse;
    });
  });

  if (lines.length === 0) {
    return null;
  }

  return (
    <group ref={groupRef}>
      {lines.map((line, index) => (
        <primitive key={index} object={line} />
      ))}
    </group>
  );
}

function LegacyParticleField({
  palette,
  agitation,
  reducedMotion,
  particleCount,
  activating,
  primed,
}: {
  palette: BirthHelixPalette;
  agitation: number;
  reducedMotion: boolean;
  particleCount: number;
  activating: boolean;
  primed: boolean;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const frameCounter = useRef(0);

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
      const theta = (i / particleCount) * Math.PI * 2 * 5;
      const radius = activating || primed ? 0.75 + (i % 7) * 0.04 : 1.05 + (i % 7) * 0.07;
      const y = ((i % 19) / 19 - 0.5) * BIRTH_HELIX_HEIGHT * 1.05;
      positions.push(
        new THREE.Vector3(Math.cos(theta) * radius, y, Math.sin(theta) * radius),
      );
    }
    return positions;
  }, [particleCount, activating, primed]);

  const particleColor = useMemo(() => new THREE.Color(palette.primary), [palette.primary]);

  useFrame((_state, delta) => {
    if (!meshRef.current) {
      return;
    }
    frameCounter.current += 1;
    const skipFrame = particleCount > 100 && frameCounter.current % 2 !== 0;
    if (skipFrame) {
      meshRef.current.rotation.y += delta * (reducedMotion ? 0.05 : 0.15);
      return;
    }

    const { elapsedSec: t, envelope } = getOrganismClock("SIM");
    const orbitSpeed = reducedMotion ? 0.1 : 0.22 + agitation * 0.75;
    const turbulence = reducedMotion ? 0.02 : 0.04 + agitation * 0.14;
    const breathe = 1 + (envelope - 0.5) * 0.08;
    const corePull = activating ? 0.35 : primed ? 0.18 : 0;

    for (let i = 0; i < particleCount; i++) {
      const base = basePositions[i];
      const orbitAngle = t * orbitSpeed + i * 0.15;
      const wobbleX = Math.sin(orbitAngle * 2.1 + i) * turbulence;
      const wobbleY = Math.cos(orbitAngle * 1.7 + i * 0.5) * turbulence * 0.6;
      const wobbleZ = Math.sin(orbitAngle * 1.9 + i * 0.3) * turbulence;

      const pull = 1 - corePull;
      dummy.position.set(
        base.x * breathe * pull + wobbleX,
        base.y + wobbleY,
        base.z * breathe * pull + wobbleZ,
      );

      const scale = 0.016 + (i % 5) * 0.003 + agitation * 0.008;
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
      meshRef.current.setColorAt(i, particleColor);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }

    meshRef.current.rotation.y += delta * orbitSpeed * 0.12;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, particleCount]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial transparent opacity={0.45} toneMapped={false} />
    </instancedMesh>
  );
}

export function LegacyHelixScene({
  activating,
  primed,
  reducedMotion,
  particleCount,
  emissiveBoost,
  visualQuality,
  tubeSegments,
}: LegacyHelixSceneProps) {
  const palette = birthHelixPalette(activating, primed);
  const agitation = birthHelixAgitation(activating, primed);

  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[3, 4, 5]} intensity={1.1} color={palette.primary} />
      <pointLight position={[-4, -2, 3]} intensity={0.5} color={palette.secondary} />

      <CoreGlow
        palette={palette}
        agitation={agitation}
        pulseSpeed={palette.pulseSpeed}
        reducedMotion={reducedMotion}
        activating={activating}
      />
      <DnaHelix
        palette={palette}
        agitation={agitation}
        reducedMotion={reducedMotion}
        activating={activating}
        primed={primed}
        emissiveBoost={emissiveBoost}
        tubeSegments={tubeSegments}
      />
      <SynapseAccents activating={activating} visualQuality={visualQuality} />
      <LegacyParticleField
        key={particleCount}
        palette={palette}
        agitation={agitation}
        reducedMotion={reducedMotion}
        particleCount={particleCount}
        activating={activating}
        primed={primed}
      />
      <CinematicBloom mode="SIM" reducedMotion={reducedMotion} visualQuality={visualQuality} />
    </>
  );
}
