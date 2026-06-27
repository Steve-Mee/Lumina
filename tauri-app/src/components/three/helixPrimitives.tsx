import type { RefObject } from "react";
import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { buildHelixCurve } from "@/lib/birthHelixGeometry";
import type { VisualQuality } from "@/lib/visualQualityPresets";

/** Shared low-level helix primitive — scenes must not import each other's scene components. */
export function useLerpedColor(targetHex: string, speed = 0.08): THREE.Color {
  const colorRef = useRef(new THREE.Color(targetHex));

  useEffect(() => {
    colorRef.current.set(targetHex);
  }, [targetHex]);

  useFrame(() => {
    colorRef.current.lerp(new THREE.Color(targetHex), speed);
  });

  return colorRef.current;
}

export function helixTubeSegments(quality: VisualQuality): number {
  switch (quality) {
    case "high":
      return 96;
    case "balanced":
      return 64;
    default:
      return 32;
  }
}

export function coreSphereSegments(quality: VisualQuality): [number, number] {
  switch (quality) {
    case "high":
      return [48, 48];
    case "balanced":
      return [32, 32];
    default:
      return [24, 24];
  }
}

export function particleSphereSegments(quality: VisualQuality): [number, number] {
  switch (quality) {
    case "high":
      return [10, 10];
    case "balanced":
      return [8, 8];
    default:
      return [6, 6];
  }
}

export interface EmissiveStrandMaterialOptions {
  color: THREE.Color | string;
  secondaryColor?: THREE.Color | string;
  emissiveIntensity?: number;
  roughness?: number;
  metalness?: number;
  transparent?: boolean;
  opacity?: number;
}

const STRAND_GRADIENT_VERTEX = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormal;
  void main() {
    vUv = uv;
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const STRAND_GRADIENT_FRAGMENT = /* glsl */ `
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  uniform float uEmissiveIntensity;
  uniform float uOpacity;
  varying vec2 vUv;
  varying vec3 vNormal;
  void main() {
    float t = clamp(vUv.y, 0.0, 1.0);
    vec3 base = mix(uColorA, uColorB, t);
    float fresnel = pow(1.0 - abs(dot(normalize(vNormal), vec3(0.0, 0.0, 1.0))), 2.0);
    vec3 emissive = base * (uEmissiveIntensity + fresnel * 0.22);
    gl_FragColor = vec4(base + emissive * 0.42, uOpacity);
  }
`;

/** Gradient strand shader — replaces flat emissive MeshStandardMaterial hack. */
export function createStrandGradientMaterial(
  options: EmissiveStrandMaterialOptions,
): THREE.ShaderMaterial {
  const colorA =
    options.color instanceof THREE.Color ? options.color.clone() : new THREE.Color(options.color);
  const colorB =
    options.secondaryColor instanceof THREE.Color
      ? options.secondaryColor.clone()
      : options.secondaryColor
        ? new THREE.Color(options.secondaryColor)
        : colorA.clone().offsetHSL(0.04, 0.05, -0.08);

  return new THREE.ShaderMaterial({
    uniforms: {
      uColorA: { value: colorA },
      uColorB: { value: colorB },
      uEmissiveIntensity: { value: options.emissiveIntensity ?? 0.45 },
      uOpacity: { value: options.opacity ?? 1 },
    },
    vertexShader: STRAND_GRADIENT_VERTEX,
    fragmentShader: STRAND_GRADIENT_FRAGMENT,
    transparent: options.transparent ?? false,
    depthWrite: !(options.transparent ?? false),
  });
}

/** Shared emissive gradient strand material for helix / core / arena nodes. */
export function createEmissiveStrandMaterial(
  options: EmissiveStrandMaterialOptions,
): THREE.ShaderMaterial {
  return createStrandGradientMaterial(options);
}

export function useEmissiveStrandMaterial(
  hex: string,
  emissiveIntensity: number,
  secondaryHex?: string,
  options?: Pick<EmissiveStrandMaterialOptions, "roughness" | "metalness" | "transparent" | "opacity">,
): THREE.ShaderMaterial {
  const color = useLerpedColor(hex);
  const secondary = useLerpedColor(secondaryHex ?? hex, 0.08);
  const material = useMemo(
    () =>
      createStrandGradientMaterial({
        color: hex,
        secondaryColor: secondaryHex ?? hex,
        emissiveIntensity,
        ...options,
      }),
    [hex, secondaryHex, emissiveIntensity, options?.roughness, options?.metalness, options?.transparent, options?.opacity],
  );

  useFrame(() => {
    material.uniforms.uColorA.value.copy(color);
    material.uniforms.uColorB.value.copy(secondary);
    material.uniforms.uEmissiveIntensity.value = emissiveIntensity;
  });

  return material;
}

export interface DoubleHelixStrandsProps {
  primaryHex: string;
  secondaryHex: string;
  emissiveIntensity: number;
  radius?: number;
  tubeRadius?: number;
  segments?: number;
  phase?: number;
  groupRef?: RefObject<THREE.Group | null>;
}

/** Double-helix tube pair shared by Living Core and birth-adjacent scenes. */
export function DoubleHelixStrands({
  primaryHex,
  secondaryHex,
  emissiveIntensity,
  radius = 0.55,
  tubeRadius = 0.045,
  segments = 64,
  phase = 0,
  groupRef,
}: DoubleHelixStrandsProps) {
  const curveA = useMemo(() => buildHelixCurve(0, radius, phase), [radius, phase]);
  const curveB = useMemo(() => buildHelixCurve(1, radius, phase), [radius, phase]);
  const primaryMat = useEmissiveStrandMaterial(primaryHex, emissiveIntensity, secondaryHex);
  const secondaryMat = useEmissiveStrandMaterial(secondaryHex, emissiveIntensity * 0.92, primaryHex);

  return (
    <group ref={groupRef}>
      <mesh material={primaryMat}>
        <tubeGeometry args={[curveA, segments, tubeRadius, 8, false]} />
      </mesh>
      <mesh material={secondaryMat}>
        <tubeGeometry args={[curveB, segments, tubeRadius, 8, false]} />
      </mesh>
    </group>
  );
}
