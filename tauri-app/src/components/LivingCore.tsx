import { OrbitControls } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import * as THREE from "three";

import { LuminaLogo } from "@/components/cockpit/LuminaLogo";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { VisibilityCanvas } from "@/components/cockpit/VisibilityCanvas";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {
  modePalette,
  riskAgitation,
  riskTint,
  type LivingCorePalette,
} from "@/lib/livingCoreTheme";
import { springSoft } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";
import {
  selectCurrentMode,
  selectRiskLevel,
  useCoreStore,
  type RiskLevel,
  type TradingMode,
} from "@/store/coreStore";
import {
  selectRenderConfig,
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

interface LivingCoreProps {
  className?: string;
}

interface SceneProps {
  mode: TradingMode;
  riskLevel: RiskLevel;
  reducedMotion: boolean;
  particleCount: number;
}

const HELIX_HEIGHT = 3.2;
const HELIX_TURNS = 2.5;
const RUNG_COUNT = 40;

export function particleCountForMode(
  mode: TradingMode,
  particleScale: number,
): number {
  const base = mode === "SIM" ? 420 : 120;
  return Math.max(20, Math.round(base * particleScale));
}

function helixPoint(
  t: number,
  strand: 0 | 1,
  radius: number,
  phase: number,
): THREE.Vector3 {
  const angle = t * Math.PI * 2 * HELIX_TURNS + strand * Math.PI + phase;
  const y = (t - 0.5) * HELIX_HEIGHT;
  return new THREE.Vector3(
    Math.cos(angle) * radius,
    y,
    Math.sin(angle) * radius,
  );
}

function buildHelixCurve(strand: 0 | 1, radius: number, phase: number): THREE.CatmullRomCurve3 {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= 64; i++) {
    points.push(helixPoint(i / 64, strand, radius, phase));
  }
  return new THREE.CatmullRomCurve3(points);
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
}: {
  palette: LivingCorePalette;
  agitation: number;
  pulseSpeed: number;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = useLerpedColor(palette.accent);

  useFrame(({ clock }) => {
    if (!meshRef.current) {
      return;
    }
    const t = clock.getElapsedTime();
    const pulse = reducedMotion
      ? 0.35
      : 0.25 + Math.sin(t * pulseSpeed * 2) * 0.15 + agitation * 0.1;
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = pulse;
    meshRef.current.scale.setScalar(0.55 + pulse * 0.25);
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.45, 24, 24]} />
      <meshBasicMaterial color={color} transparent opacity={0.35} depthWrite={false} />
    </mesh>
  );
}

function DnaHelix({
  palette,
  agitation,
  pulseSpeed,
  reducedMotion,
}: {
  palette: LivingCorePalette;
  agitation: number;
  pulseSpeed: number;
  reducedMotion: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const primaryColor = useLerpedColor(palette.primary);
  const secondaryColor = useLerpedColor(palette.secondary);

  const radius = 0.55;
  const curveA = useMemo(() => buildHelixCurve(0, radius, 0), []);
  const curveB = useMemo(() => buildHelixCurve(1, radius, 0), []);

  const rungs = useMemo(() => {
    return Array.from({ length: RUNG_COUNT }, (_, i) => i / (RUNG_COUNT - 1));
  }, []);

  useFrame(({ clock }, delta) => {
    if (!groupRef.current) {
      return;
    }
    const t = clock.getElapsedTime();
    groupRef.current.rotation.y += reducedMotion ? delta * 0.08 : delta * 0.25;

    const breathe = 1 + Math.sin(t * pulseSpeed) * 0.06 + agitation * 0.04;
    groupRef.current.scale.setScalar(breathe);
  });

  return (
    <group ref={groupRef}>
      <mesh>
        <tubeGeometry args={[curveA, 64, 0.045, 8, false]} />
        <meshStandardMaterial
          color={primaryColor}
          emissive={primaryColor}
          emissiveIntensity={0.35 + agitation * 0.45}
          roughness={0.35}
          metalness={0.6}
        />
      </mesh>
      <mesh>
        <tubeGeometry args={[curveB, 64, 0.045, 8, false]} />
        <meshStandardMaterial
          color={secondaryColor}
          emissive={secondaryColor}
          emissiveIntensity={0.3 + agitation * 0.4}
          roughness={0.35}
          metalness={0.6}
        />
      </mesh>

      {rungs.map((t, index) => {
        const a = helixPoint(t, 0, radius, 0);
        const b = helixPoint(t, 1, radius, 0);
        const midpoint = a.clone().add(b).multiplyScalar(0.5);
        const direction = b.clone().sub(a);
        const length = direction.length();
        const orientation = new THREE.Quaternion().setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          direction.normalize(),
        );
        return (
          <mesh key={index} position={midpoint} quaternion={orientation}>
            <cylinderGeometry args={[0.018, 0.018, length, 6]} />
            <meshStandardMaterial
              color={palette.accent}
              emissive={palette.accent}
              emissiveIntensity={0.2 + (index % 3) * 0.05}
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
  mode,
  riskLevel,
  palette,
  agitation,
  pulseSpeed,
  reducedMotion,
  particleCount,
}: {
  mode: TradingMode;
  riskLevel: RiskLevel;
  palette: LivingCorePalette;
  agitation: number;
  pulseSpeed: number;
  reducedMotion: boolean;
  particleCount: number;
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

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
      const theta = (i / particleCount) * Math.PI * 2 * 6;
      const radius = 1.1 + (i % 7) * 0.08;
      const y = ((i % 23) / 23 - 0.5) * HELIX_HEIGHT * 1.1;
      positions.push(
        new THREE.Vector3(
          Math.cos(theta) * radius,
          y,
          Math.sin(theta) * radius,
        ),
      );
    }
    return positions;
  }, [particleCount]);

  const primaryColor = useMemo(() => new THREE.Color(palette.primary), [palette.primary]);
  const tintColor = useMemo(() => new THREE.Color(riskTint(riskLevel)), [riskLevel]);
  const blendedColor = useMemo(() => {
    const c = primaryColor.clone();
    c.lerp(tintColor, 0.35 + agitation * 0.45);
    return c;
  }, [primaryColor, tintColor, agitation]);

  useFrame(({ clock }, delta) => {
    if (!meshRef.current) {
      return;
    }
    const t = clock.getElapsedTime();
    const orbitSpeed = reducedMotion ? 0.15 : 0.35 + agitation * 1.1;
    const turbulence = reducedMotion ? 0.02 : 0.05 + agitation * 0.18;
    const breathe = 1 + Math.sin(t * pulseSpeed + 0.8) * 0.04;

    for (let i = 0; i < particleCount; i++) {
      const base = basePositions[i];
      const orbitAngle = t * orbitSpeed + i * 0.15;
      const wobbleX = Math.sin(orbitAngle * 2.1 + i) * turbulence;
      const wobbleY = Math.cos(orbitAngle * 1.7 + i * 0.5) * turbulence * 0.6;
      const wobbleZ = Math.sin(orbitAngle * 1.9 + i * 0.3) * turbulence;

      dummy.position.set(
        base.x * breathe + wobbleX,
        base.y + wobbleY,
        base.z * breathe + wobbleZ,
      );

      const scale = 0.018 + (i % 5) * 0.003 + agitation * 0.008;
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
      meshRef.current.setColorAt(i, blendedColor);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }

    meshRef.current.rotation.y += delta * orbitSpeed * (mode === "SIM" ? 0.15 : 0.06);
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, particleCount]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial transparent opacity={0.75} toneMapped={false} />
    </instancedMesh>
  );
}

function LivingCoreScene({ mode, riskLevel, reducedMotion, particleCount }: SceneProps) {
  const palette = modePalette(mode);
  const agitation = riskAgitation(riskLevel);

  return (
    <>
      <ambientLight intensity={0.35} />
      <pointLight position={[3, 4, 5]} intensity={1.2} color={palette.primary} />
      <pointLight position={[-4, -2, 3]} intensity={0.6} color={palette.secondary} />

      <CoreGlow
        palette={palette}
        agitation={agitation}
        pulseSpeed={palette.pulseSpeed}
        reducedMotion={reducedMotion}
      />
      <DnaHelix
        palette={palette}
        agitation={agitation}
        pulseSpeed={palette.pulseSpeed}
        reducedMotion={reducedMotion}
      />
      <ParticleField
        key={particleCount}
        mode={mode}
        riskLevel={riskLevel}
        palette={palette}
        agitation={agitation}
        pulseSpeed={palette.pulseSpeed}
        reducedMotion={reducedMotion}
        particleCount={particleCount}
      />

      <OrbitControls
        enablePan={false}
        enableZoom
        minDistance={4}
        maxDistance={10}
        autoRotate={!reducedMotion}
        autoRotateSpeed={mode === "SIM" ? 0.8 : 0.35}
      />
    </>
  );
}

export function LivingCore({ className }: LivingCoreProps) {
  const mode = useCoreStore(selectCurrentMode);
  const riskLevel = useCoreStore(selectRiskLevel);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const renderConfig = useVisualSettingsStore(selectRenderConfig);
  const prefersReducedMotion = usePrefersReducedMotion();
  const reducedMotion =
    prefersReducedMotion || mode === "REAL" || visualQuality === "low";
  const particleCount = particleCountForMode(mode, renderConfig.particleScale);
  const [canvasReady, setCanvasReady] = useState(false);

  return (
    <div
      className={cn("living-core-shell relative min-h-[220px] w-full", className)}
      aria-label={`Living neural core — ${mode} mode, risk ${riskLevel}`}
      role="img"
    >
      <Suspense
        fallback={
          <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-3">
            <LuminaLogo />
            <PanelLoader label="Initializing neural core…" className="min-h-0" rows={2} />
          </div>
        }
      >
        <motion.div
          className="h-full min-h-[220px] w-full"
          initial={{ opacity: 0 }}
          animate={{ opacity: canvasReady ? 1 : 0.4 }}
          transition={springSoft}
        >
          <VisibilityCanvas
            panelName="Neural Core"
            idleLabel="Neural core paused — scroll into view"
            camera={{ position: [0, 0, 6], fov: 45 }}
            onCreated={() => setCanvasReady(true)}
          >
            <LivingCoreScene
              mode={mode}
              riskLevel={riskLevel}
              reducedMotion={reducedMotion}
              particleCount={particleCount}
            />
          </VisibilityCanvas>
        </motion.div>
      </Suspense>
    </div>
  );
}
