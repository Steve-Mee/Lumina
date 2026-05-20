import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { CinematicBloom } from "@/components/cockpit/CinematicBloom";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { getOrganismClock } from "@/lib/organismClockStore";
import { getOrganismBreatheCycleSec } from "@/lib/breatheCurve";
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
  trainingTrades?: number;
  className?: string;
}

interface SceneProps {
  activating: boolean;
  primed: boolean;
  reducedMotion: boolean;
  particleCount: number;
  emissiveBoost: number;
  visualQuality: VisualQuality;
}

function useLerpedColor(targetHex: string, speed = 0.08): THREE.Color {
  const colorRef = useRef(new THREE.Color(targetHex));

  useEffect(() => {
    colorRef.current.set(targetHex);
  }, [targetHex]);

  useFrame(() => {
    colorRef.current.lerp(new THREE.Color(targetHex), speed);
  });

  return colorRef.current;
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
  pulseSpeed,
  reducedMotion,
  activating,
  emissiveBoost,
}: {
  palette: BirthHelixPalette;
  agitation: number;
  pulseSpeed: number;
  reducedMotion: boolean;
  activating: boolean;
  emissiveBoost: number;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const primaryColor = useLerpedColor(palette.primary);
  const secondaryColor = useLerpedColor(palette.secondary);

  const radius = 0.55;
  const curveA = useMemo(() => buildHelixCurve(0, radius, 0), []);
  const curveB = useMemo(() => buildHelixCurve(1, radius, 0), []);

  const rungs = useMemo(
    () => Array.from({ length: BIRTH_RUNG_COUNT }, (_, i) => i / (BIRTH_RUNG_COUNT - 1)),
    [],
  );

  useFrame(({ clock }, delta) => {
    if (!groupRef.current) {
      return;
    }
    const t = clock.getElapsedTime();
    const rotSpeed = reducedMotion ? 0.06 : activating ? 0.52 : 0.18;
    groupRef.current.rotation.y += delta * rotSpeed;

    const { envelope } = getOrganismClock("SIM");
    const breathe = 1 + (envelope - 0.5) * 0.12 + agitation * 0.08;
    groupRef.current.scale.setScalar(breathe);
  });

  const tubeEmissive = (0.4 + agitation * 0.5) * emissiveBoost;

  return (
    <group ref={groupRef}>
      <mesh>
        <tubeGeometry args={[curveA, 64, 0.04, 8, false]} />
        <meshStandardMaterial
          color={primaryColor}
          emissive={primaryColor}
          emissiveIntensity={tubeEmissive}
          roughness={0.3}
          metalness={0.65}
        />
      </mesh>
      <mesh>
        <tubeGeometry args={[curveB, 64, 0.04, 8, false]} />
        <meshStandardMaterial
          color={secondaryColor}
          emissive={secondaryColor}
          emissiveIntensity={tubeEmissive * 0.9}
          roughness={0.3}
          metalness={0.65}
        />
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
          <mesh key={index} position={midpoint} quaternion={orientation}>
            <cylinderGeometry args={[0.016, 0.016, length, 6]} />
            <meshStandardMaterial
              color={palette.accent}
              emissive={palette.accent}
              emissiveIntensity={(0.25 + (index % 3) * 0.05) * emissiveBoost}
              transparent
              opacity={0.85}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function ParticleField({
  palette,
  agitation,
  pulseSpeed,
  reducedMotion,
  particleCount,
  activating,
}: {
  palette: BirthHelixPalette;
  agitation: number;
  pulseSpeed: number;
  reducedMotion: boolean;
  particleCount: number;
  activating: boolean;
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
      const radius = activating ? 0.75 + (i % 7) * 0.04 : 1.05 + (i % 7) * 0.07;
      const y = ((i % 19) / 19 - 0.5) * BIRTH_HELIX_HEIGHT * 1.05;
      positions.push(
        new THREE.Vector3(
          Math.cos(theta) * radius,
          y,
          Math.sin(theta) * radius,
        ),
      );
    }
    return positions;
  }, [particleCount, activating]);

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
    const corePull = activating ? 0.35 : 0;

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
      <meshBasicMaterial transparent opacity={0.7} toneMapped={false} />
    </instancedMesh>
  );
}

function BirthHelixScene({
  activating,
  primed,
  reducedMotion,
  particleCount,
  emissiveBoost,
  visualQuality,
}: SceneProps) {
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
        pulseSpeed={palette.pulseSpeed}
        reducedMotion={reducedMotion}
        activating={activating}
        emissiveBoost={emissiveBoost}
      />
      <ParticleField
        key={particleCount}
        palette={palette}
        agitation={agitation}
        pulseSpeed={palette.pulseSpeed}
        reducedMotion={reducedMotion}
        particleCount={particleCount}
        activating={activating}
      />
      <CinematicBloom mode="SIM" reducedMotion={reducedMotion} visualQuality={visualQuality} />
    </>
  );
}

export function BirthHelixVisual({
  activating = false,
  primed = false,
  trainingTrades,
  className,
}: BirthHelixVisualProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const renderConfig = useVisualSettingsStore(selectRenderConfig);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const particleCount = birthParticleCount(renderConfig.particleScale, trainingTrades);
  const emissiveBoost = birthEmissiveFromTrades(trainingTrades);

  if (prefersReducedMotion) {
    return (
      <div className={cn("flex h-full min-h-[280px] items-center justify-center", className)}>
        <BirthOrganismVisual awakening={activating} className="size-56 md:size-64" />
      </div>
    );
  }

  return (
    <div
      className={cn("relative h-full min-h-[280px] w-full", className)}
      aria-hidden
    >
      <Suspense
        fallback={
          <div className="flex h-full min-h-[280px] items-center justify-center">
            <BirthOrganismVisual className="size-48 opacity-70" />
          </div>
        }
      >
        <Canvas
          className="h-full min-h-[280px] w-full touch-none"
          frameloop="always"
          dpr={[1, 1.25]}
          camera={{ position: [0, 0.5, 5.5], fov: 42 }}
          gl={{ antialias: true, alpha: true }}
        >
          <BirthHelixScene
            activating={activating}
            primed={primed}
            reducedMotion={false}
            particleCount={particleCount}
            emissiveBoost={emissiveBoost}
            visualQuality={visualQuality}
          />
        </Canvas>
      </Suspense>
    </div>
  );
}
