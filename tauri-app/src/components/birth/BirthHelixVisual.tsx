import { useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { CinematicBloom } from "@/components/cockpit/CinematicBloom";
import { LuminaLogo } from "@/components/cockpit/LuminaLogo";
import { VisibilityCanvas } from "@/components/cockpit/VisibilityCanvas";
import {
  coreSphereSegments,
  createStrandGradientMaterial,
  DoubleHelixStrands,
  helixTubeSegments,
  particleSphereSegments,
  useLerpedColor,
} from "@/components/three/helixPrimitives";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { getOrganismClock } from "@/lib/organismClockStore";
import {
  BIRTH_HELIX_HEIGHT,
  BIRTH_RUNG_COUNT,
  birthEmissiveFromTrades,
  birthParticleCount,
  buildHelixCurve,
  helixPoint,
} from "@/lib/birthHelixGeometry";
import {
  birthHelixAgitation,
  birthHelixPalette,
  type BirthHelixPalette,
} from "@/lib/birthHelixTheme";
import { cn } from "@/lib/utils";
import type { VisualQuality } from "@/lib/visualQualityPresets";
import {
  selectRenderConfig,
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

interface BirthHelixVisualProps {
  activating?: boolean;
  primed?: boolean;
  ceremonyMode?: boolean;
  trainingTrades?: number;
  className?: string;
}

interface SceneProps {
  activating: boolean;
  primed: boolean;
  ceremonyMode: boolean;
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

  useFrame(({ clock }, delta) => {
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

function CeremonyHelixScene({
  activating,
  primed,
  reducedMotion,
  particleCount,
  emissiveBoost,
  visualQuality,
  tubeSegments,
}: Omit<SceneProps, "ceremonyMode">) {
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
      const target = helixPoint(rungT, index % 2, radius, 0);
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

  useFrame(({ clock }, delta) => {
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

function BirthHelixScene({
  activating,
  primed,
  ceremonyMode,
  reducedMotion,
  particleCount,
  emissiveBoost,
  visualQuality,
  tubeSegments,
}: SceneProps) {
  if (ceremonyMode) {
    return (
      <CeremonyHelixScene
        activating={activating}
        primed={primed}
        reducedMotion={reducedMotion}
        particleCount={particleCount}
        emissiveBoost={emissiveBoost}
        visualQuality={visualQuality}
        tubeSegments={tubeSegments}
      />
    );
  }

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

export function BirthHelixVisual({
  activating = false,
  primed = false,
  ceremonyMode = false,
  trainingTrades,
  className,
}: BirthHelixVisualProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const renderConfig = useVisualSettingsStore(selectRenderConfig);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const tubeSegments = helixTubeSegments(visualQuality);
  const particleCount = birthParticleCount(
    renderConfig.particleScale,
    trainingTrades,
    visualQuality,
  );
  const emissiveBoost = birthEmissiveFromTrades(trainingTrades);
  const sceneParticleCount = ceremonyMode
    ? Math.max(24, Math.round(particleCount * 0.5))
    : particleCount;
  const ceremonyCssFallback = ceremonyMode && (prefersReducedMotion || visualQuality === "low");
  const legacyCssFallback = !ceremonyMode && (prefersReducedMotion || visualQuality === "low");

  const minHeightClass = ceremonyMode ? "min-h-0 h-full" : "min-h-[280px]";
  const ceremonyCamera = { position: [0, 0, 4.0] as [number, number, number], fov: 34 };

  if (ceremonyCssFallback) {
    return (
      <div
        className={cn(
          "relative flex h-full min-h-0 items-center justify-center",
          className,
        )}
      >
        <LuminaLogo className="pointer-events-none absolute size-56 opacity-40 md:size-64" />
        <BirthOrganismVisual
          awakening={activating}
          className="relative size-64 md:size-72"
        />
      </div>
    );
  }

  if (legacyCssFallback) {
    return (
      <div className={cn("flex h-full items-center justify-center", minHeightClass, className)}>
        <BirthOrganismVisual
          awakening={activating}
          className={cn(ceremonyMode ? "size-72 md:size-80" : "size-56 md:size-64")}
        />
      </div>
    );
  }

  return (
    <div className={cn("relative h-full w-full", minHeightClass, className)} aria-hidden>
      <Suspense
        fallback={
          <div className={cn("flex h-full items-center justify-center", minHeightClass)}>
            <BirthOrganismVisual className="size-48 opacity-70" />
          </div>
        }
      >
        <VisibilityCanvas
          panelName="Birth Helix"
          idleLabel="Birth helix paused — scroll into view"
          minHeight={minHeightClass}
          camera={ceremonyMode ? ceremonyCamera : { position: [0, 0.5, 5.5], fov: 42 }}
        >
          <BirthHelixScene
            activating={activating}
            primed={primed}
            ceremonyMode={ceremonyMode}
            reducedMotion={prefersReducedMotion}
            particleCount={sceneParticleCount}
            emissiveBoost={emissiveBoost}
            visualQuality={visualQuality}
            tubeSegments={tubeSegments}
          />
        </VisibilityCanvas>
      </Suspense>
    </div>
  );
}
