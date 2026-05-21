import { useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import * as THREE from "three";

import { CinematicBloom } from "@/components/cockpit/CinematicBloom";
import { LuminaLogo } from "@/components/cockpit/LuminaLogo";
import {
  coreSphereSegments,
  DoubleHelixStrands,
  helixTubeSegments,
  particleSphereSegments,
  useLerpedColor,
} from "@/components/three/helixPrimitives";
import { DECK_LOADING_COPY } from "@/lib/deckLoadingCopy";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { VisibilityCanvas } from "@/components/cockpit/VisibilityCanvas";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { resolveIntelligenceHealth } from "@/lib/adaptiveIntelligenceTypes";
import { getOrganismClock } from "@/lib/organismClockStore";
import { vigilantHeartbeatPulse } from "@/lib/breatheCurve";
import {
  BIRTH_HELIX_HEIGHT,
  helixPoint,
} from "@/lib/birthHelixGeometry";
import {
  buildLivingCoreVisualParams,
  riskTint,
  type LivingCoreVisualParams,
} from "@/lib/livingCoreTheme";
import { vitalityBucket } from "@/lib/livingCoreLiveModel";
import { livingCoreHaloAnimationClass } from "@/lib/pulseLanguage";
import { transitionOrNone } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";
import {
  selectAdaptiveIntelligenceStatus,
  selectAdaptiveTransitionSummary,
  selectConnectionStatus,
  selectCurrentMode,
  selectFallbackMode,
  selectLiveMetrics,
  selectRiskLevel,
  useCoreStore,
  type RiskLevel,
  type TradingMode,
} from "@/store/coreStore";
import type { VisualQuality } from "@/lib/visualQualityPresets";
import {
  selectRenderConfig,
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

interface LivingCoreProps {
  className?: string;
}

interface SceneProps {
  visualParams: LivingCoreVisualParams;
  riskLevel: RiskLevel;
  mode: TradingMode;
  reducedMotion: boolean;
  particleCount: number;
  synapseBoost: number;
  visualQuality: VisualQuality;
}

export function particleCountForMode(
  mode: TradingMode,
  particleScale: number,
  vitality = 1,
  visualQuality: VisualQuality = "medium",
): number {
  const base = mode === "SIM" ? 504 : 120;
  const raw = Math.max(20, Math.round(base * particleScale * (0.45 + vitality * 0.55)));
  const ceilings: Record<VisualQuality, number> = {
    low: 120,
    medium: 280,
    high: 504,
  };
  return Math.min(raw, ceilings[visualQuality] ?? ceilings.medium);
}

function clampPulse(value: number): number {
  return Math.min(1, Math.max(0.28, value));
}

function HeartCore({
  visualParams,
  reducedMotion,
  mode,
  synapseBoost,
  visualQuality,
}: {
  visualParams: LivingCoreVisualParams;
  reducedMotion: boolean;
  mode: TradingMode;
  synapseBoost: number;
  visualQuality: VisualQuality;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = useLerpedColor(visualParams.palette.accent);
  const [width, height] = coreSphereSegments(visualQuality);

  useFrame(() => {
    if (!meshRef.current) {
      return;
    }
    const { elapsedSec: t, envelope } = getOrganismClock(mode);
    const breathDrive = mode === "SIM" ? envelope : envelope * 0.42;
    const realVigil = mode === "REAL" ? vigilantHeartbeatPulse(t, 6) * 0.18 : 0;
    const pulse = reducedMotion
      ? 0.32 + visualParams.vitality * 0.14
      : 0.22 +
        breathDrive * 0.24 +
        realVigil +
        visualParams.agitation * 0.08 * visualParams.vitality +
        synapseBoost * 0.15;
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = clampPulse(pulse) * (0.68 + visualParams.vitality * 0.32);
    meshRef.current.scale.setScalar(0.42 + clampPulse(pulse) * 0.24 * visualParams.vitality);
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.38, width, height]} />
      <meshBasicMaterial color={color} transparent opacity={0.35} depthWrite={false} />
    </mesh>
  );
}

function AuraHalo({
  visualParams,
  reducedMotion,
  mode,
  visualQuality,
}: {
  visualParams: LivingCoreVisualParams;
  reducedMotion: boolean;
  mode: TradingMode;
  visualQuality: VisualQuality;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = useLerpedColor(visualParams.palette.primary, 0.05);
  const [width, height] = coreSphereSegments(visualQuality);

  useFrame(() => {
    if (!meshRef.current) {
      return;
    }
    const { elapsedSec: t, envelope } = getOrganismClock(mode);
    const breathe = reducedMotion ? 1 : 1 + (envelope - 0.5) * 0.1;
    const scale = (0.85 + visualParams.vitality * 0.35) * breathe;
    meshRef.current.scale.setScalar(scale);
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;
    mat.opacity = 0.12 + visualParams.vitality * 0.14;
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.72, width, height]} />
      <meshBasicMaterial color={color} transparent opacity={0.12} depthWrite={false} />
    </mesh>
  );
}

function DnaHelix({
  visualParams,
  reducedMotion,
  synapseBoost,
  mode,
  visualQuality,
}: {
  visualParams: LivingCoreVisualParams;
  reducedMotion: boolean;
  synapseBoost: number;
  mode: TradingMode;
  visualQuality: VisualQuality;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const phase = visualParams.regimePhase;
  const emissive =
    (0.28 + visualParams.agitation * 0.4) *
    visualParams.emissiveBoost *
    visualParams.vitality *
    (1 + synapseBoost * 0.5);
  const segments = helixTubeSegments(visualQuality);

  useFrame((_, delta) => {
    if (!groupRef.current) {
      return;
    }
    groupRef.current.rotation.y += reducedMotion
      ? delta * 0.04
      : delta * visualParams.helixDrift;

    const { envelope } = getOrganismClock(mode);
    const breathe = 1 + (envelope - 0.5) * 0.09 + visualParams.agitation * 0.03;
    groupRef.current.scale.setScalar(breathe);
  });

  return (
    <DoubleHelixStrands
      groupRef={groupRef}
      primaryHex={visualParams.palette.primary}
      secondaryHex={visualParams.palette.secondary}
      emissiveIntensity={emissive}
      phase={phase}
      segments={segments}
    />
  );
}

function ParticleField({
  mode,
  riskLevel,
  visualParams,
  reducedMotion,
  particleCount,
  visualQuality,
}: {
  mode: TradingMode;
  riskLevel: RiskLevel;
  visualParams: LivingCoreVisualParams;
  reducedMotion: boolean;
  particleCount: number;
  visualQuality: VisualQuality;
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
      const y = ((i % 23) / 23 - 0.5) * BIRTH_HELIX_HEIGHT * 1.1;
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

  const primaryColor = useMemo(
    () => new THREE.Color(visualParams.palette.primary),
    [visualParams.palette.primary],
  );
  const tintColor = useMemo(() => new THREE.Color(riskTint(riskLevel)), [riskLevel]);
  const accentColor = useMemo(
    () => new THREE.Color(visualParams.palette.accent),
    [visualParams.palette.accent],
  );
  const blendedColor = useMemo(() => {
    const c = primaryColor.clone();
    c.lerp(accentColor, 0.2);
    c.lerp(tintColor, 0.25 + visualParams.agitation * 0.35);
    return c;
  }, [primaryColor, accentColor, tintColor, visualParams.agitation]);

  const frameCounter = useRef(0);
  const [particleWidth, particleHeight] = particleSphereSegments(visualQuality);

  useFrame(({ clock }, delta) => {
    if (!meshRef.current) {
      return;
    }
    frameCounter.current += 1;
    const skipFrame =
      particleCount > 200 &&
      frameCounter.current % 2 !== 0 &&
      visualParams.agitation < 0.55;
    if (skipFrame) {
      meshRef.current.rotation.y += delta * 0.06;
      return;
    }

    const { elapsedSec: t, envelope } = getOrganismClock(mode);
    const orbitSpeed = reducedMotion
      ? 0.08
      : 0.18 + visualParams.agitation * 0.65;
    const turbulence = reducedMotion
      ? 0.015
      : 0.03 + visualParams.agitation * 0.12;
    const breathe = 1 + (envelope - 0.5) * 0.07;

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

      const scale =
        0.014 + (i % 5) * 0.0025 + visualParams.agitation * 0.006 * visualParams.vitality;
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
      meshRef.current.setColorAt(i, blendedColor);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }

    meshRef.current.rotation.y += delta * orbitSpeed * (mode === "SIM" ? 0.1 : 0.04);
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, particleCount]}>
      <sphereGeometry args={[1, particleWidth, particleHeight]} />
      <meshBasicMaterial
        transparent
        opacity={visualParams.particleOpacity}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

function LivingCoreScene({
  visualParams,
  riskLevel,
  mode,
  reducedMotion,
  particleCount,
  synapseBoost,
  visualQuality,
}: SceneProps) {
  const palette = visualParams.palette;
  const lightIntensity = 0.55 + visualParams.vitality * 0.75;
  const fillColor = mode === "REAL" ? palette.accent : palette.secondary;

  return (
    <>
      <ambientLight intensity={0.22 + visualParams.vitality * 0.18} />
      <pointLight
        position={[3, 4, 5]}
        intensity={lightIntensity}
        color={palette.primary}
      />
      <pointLight position={[-4, -2, 3]} intensity={lightIntensity * 0.5} color={fillColor} />

      <HeartCore
        visualParams={visualParams}
        reducedMotion={reducedMotion}
        mode={mode}
        synapseBoost={synapseBoost}
        visualQuality={visualQuality}
      />
      <AuraHalo
        visualParams={visualParams}
        reducedMotion={reducedMotion}
        mode={mode}
        visualQuality={visualQuality}
      />
      <DnaHelix
        visualParams={visualParams}
        reducedMotion={reducedMotion}
        synapseBoost={synapseBoost}
        mode={mode}
        visualQuality={visualQuality}
      />
      <ParticleField
        key={particleCount}
        mode={mode}
        riskLevel={riskLevel}
        visualParams={visualParams}
        reducedMotion={reducedMotion}
        particleCount={particleCount}
        visualQuality={visualQuality}
      />
      <CinematicBloom mode={mode} reducedMotion={reducedMotion} visualQuality={visualQuality} />
    </>
  );
}

export function LivingCore({ className }: LivingCoreProps) {
  const mode = useCoreStore(selectCurrentMode);
  const riskLevel = useCoreStore(selectRiskLevel);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const adaptiveStatus = useCoreStore(selectAdaptiveIntelligenceStatus);
  const adaptiveTransition = useCoreStore(selectAdaptiveTransitionSummary);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const renderConfig = useVisualSettingsStore(selectRenderConfig);
  const prefersReducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const reducedMotion = prefersReducedMotion || visualQuality === "low";

  const intelligenceHealth = resolveIntelligenceHealth({
    status: adaptiveStatus,
    loading: false,
    error: null,
    transition: adaptiveTransition,
  });

  const visualParams = buildLivingCoreVisualParams({
    mode,
    riskLevel,
    regime: liveMetrics.regime,
    regimeConfidence: liveMetrics.regimeConfidence,
    connectionStatus,
    fallbackMode,
    intelligenceHealth,
  });

  const particleCount = particleCountForMode(
    mode,
    renderConfig.particleScale,
    visualParams.vitality,
    visualQuality,
  );
  const [canvasReady, setCanvasReady] = useState(false);
  const [synapseBoost, setSynapseBoost] = useState(0);
  const prevConnection = useRef(connectionStatus);
  const vitalityLevel = vitalityBucket(visualParams.vitality);

  useEffect(() => {
    if (prevConnection.current === connectionStatus) {
      return;
    }
    prevConnection.current = connectionStatus;
    setSynapseBoost(1);
    const timer = setTimeout(() => setSynapseBoost(0), 400);
    return () => clearTimeout(timer);
  }, [connectionStatus]);

  return (
    <div
      className={cn(
        "living-core-shell living-core-shell--immersive relative min-h-[220px] w-full",
        livingCoreHaloAnimationClass(mode),
        className,
      )}
      data-mode={mode}
      data-regime={visualParams.regimeKey}
      data-vitality={vitalityLevel}
      aria-label={`Living neural core — ${mode} mode, ${liveMetrics.regime} regime, ${connectionStatus}, risk ${riskLevel}`}
      role="img"
    >
      <Suspense
        fallback={
          <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-3">
            <LuminaLogo />
            <PanelLoader label={DECK_LOADING_COPY.neuralCore} className="min-h-0" rows={2} />
          </div>
        }
      >
        <motion.div
          className="h-full min-h-[220px] w-full"
          initial={{ opacity: 0 }}
          animate={{ opacity: canvasReady ? 1 : 0.4 }}
          transition={transitionOrNone(reducedMotion, modeMotion)}
        >
          <VisibilityCanvas
            panelName="Neural Core"
            idleLabel="Neural core paused — scroll into view"
            camera={{ position: [0, 0.2, 5.8], fov: 42 }}
            onCreated={() => setCanvasReady(true)}
          >
            <LivingCoreScene
              visualParams={visualParams}
              riskLevel={riskLevel}
              mode={mode}
              reducedMotion={reducedMotion}
              particleCount={particleCount}
              synapseBoost={synapseBoost}
              visualQuality={visualQuality}
            />
          </VisibilityCanvas>
        </motion.div>
      </Suspense>
    </div>
  );
}
