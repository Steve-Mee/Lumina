import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { getOrganismClock } from "@/lib/organismClockStore";
import type { OrganismMorphology } from "@/lib/organism/phaseMorphology";

const VANE_VERTEX = /* glsl */ `
  uniform float uTime;
  uniform float uWave;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    vec3 p = position;
    float along = uv.y;
    float outw = uv.x;
    p.z += sin(along * 5.2 + uTime * 1.35 + outw * 2.0) * uWave * (0.25 + outw);
    p.x += sin(along * 3.1 + uTime * 0.8) * uWave * 0.18;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }
`;

const VANE_FRAGMENT = /* glsl */ `
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  uniform vec3 uColorC;
  uniform float uOpacity;
  uniform float uTime;
  varying vec2 vUv;
  void main() {
    float aurora = 0.5 + 0.5 * sin(vUv.y * 7.0 + uTime * 0.7 + vUv.x * 3.0);
    vec3 color = mix(uColorA, uColorB, vUv.x);
    color = mix(color, uColorC, vUv.y * 0.65 + aurora * 0.2);
    float fade = smoothstep(0.0, 0.1, vUv.x) * (1.0 - smoothstep(0.78, 1.0, vUv.x));
    fade *= smoothstep(0.0, 0.08, vUv.y) * (1.0 - smoothstep(0.86, 1.0, vUv.y));
    gl_FragColor = vec4(color, uOpacity * fade);
  }
`;

function CloakVane({
  index,
  count,
  span,
  reducedMotion,
}: {
  index: number;
  count: number;
  span: number;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uWave: { value: 0.16 },
          uColorA: { value: new THREE.Color("#00f0ff") },
          uColorB: { value: new THREE.Color("#34d399") },
          uColorC: { value: new THREE.Color("#c084fc") },
          uOpacity: { value: 0.28 },
        },
        vertexShader: VANE_VERTEX,
        fragmentShader: VANE_FRAGMENT,
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    [],
  );

  useEffect(() => () => material.dispose(), [material]);

  useFrame(() => {
    const { elapsedSec, envelope } = getOrganismClock("SIM");
    material.uniforms.uTime.value = reducedMotion ? 0 : elapsedSec;
    material.uniforms.uWave.value = reducedMotion ? 0.05 : 0.12 + span * 0.22;
    material.uniforms.uOpacity.value = 0.16 + span * 0.22 + envelope * 0.08;
    if (!meshRef.current) {
      return;
    }
    const yaw = (index / Math.max(1, count)) * Math.PI * 2 + Math.PI / count;
    const drape = 0.95 + Math.sin(elapsedSec * 0.45 + index) * 0.05 * span;
    meshRef.current.position.set(Math.cos(yaw) * 0.12, 0.42, Math.sin(yaw) * 0.1);
    meshRef.current.rotation.set(drape, yaw, 0.05);
    meshRef.current.scale.set(0.7 + span * 0.85, 0.9 + span * 0.7, 1);
  });

  return (
    <mesh ref={meshRef} material={material}>
      <planeGeometry args={[1.7, 2.35, 12, 16]} />
    </mesh>
  );
}

export function OrganismVanes({
  morph,
  reducedMotion,
}: {
  morph: OrganismMorphology;
  reducedMotion: boolean;
}) {
  if (morph.vaneSpan < 0.02 || morph.vaneCount < 1) {
    return null;
  }
  return (
    <group>
      {Array.from({ length: morph.vaneCount }, (_, index) => (
        <CloakVane
          key={index}
          index={index}
          count={morph.vaneCount}
          span={morph.vaneSpan}
          reducedMotion={reducedMotion}
        />
      ))}
    </group>
  );
}
