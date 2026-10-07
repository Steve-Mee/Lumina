import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { getOrganismClock } from "@/lib/organismClockStore";

const GLASS_VERTEX = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vWorld;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 world = modelMatrix * vec4(position, 1.0);
    vWorld = world.xyz;
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

const GLASS_FRAGMENT = /* glsl */ `
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  uniform float uOpacity;
  varying vec3 vNormal;
  varying vec3 vWorld;
  void main() {
    float fresnel = pow(1.0 - abs(dot(normalize(vNormal), vec3(0.0, 0.0, 1.0))), 2.4);
    float height = clamp((vWorld.y + 1.4) / 2.8, 0.0, 1.0);
    vec3 base = mix(uColorB, uColorA, height);
    float alpha = uOpacity * (0.07 + fresnel * 0.42);
    gl_FragColor = vec4(base, alpha);
  }
`;

function buildTeardropGeometry(): THREE.LatheGeometry {
  const points: THREE.Vector2[] = [
    new THREE.Vector2(0.04, 1.32),
    new THREE.Vector2(0.28, 1.18),
    new THREE.Vector2(0.46, 0.96),
    new THREE.Vector2(0.54, 0.62),
    new THREE.Vector2(0.5, 0.18),
    new THREE.Vector2(0.4, -0.28),
    new THREE.Vector2(0.26, -0.78),
    new THREE.Vector2(0.13, -1.18),
    new THREE.Vector2(0.03, -1.42),
  ];
  return new THREE.LatheGeometry(points, 48);
}

/** Glass teardrop hull — the adult Lumina silhouette. Visual only. */
export function OrganismGlass({ opacity }: { opacity: number }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const geometry = useMemo(() => buildTeardropGeometry(), []);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uColorA: { value: new THREE.Color("#67f7ff") },
          uColorB: { value: new THREE.Color("#a78bfa") },
          uOpacity: { value: 0.2 },
        },
        vertexShader: GLASS_VERTEX,
        fragmentShader: GLASS_FRAGMENT,
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    [],
  );

  useEffect(
    () => () => {
      geometry.dispose();
      material.dispose();
    },
    [geometry, material],
  );

  useFrame(() => {
    const { envelope } = getOrganismClock("SIM");
    material.uniforms.uOpacity.value = opacity * (0.85 + envelope * 0.2);
    if (meshRef.current) {
      const breathe = 1 + (envelope - 0.5) * 0.03;
      meshRef.current.scale.set(breathe, 1, breathe);
    }
  });

  if (opacity < 0.02) {
    return null;
  }

  return <mesh ref={meshRef} geometry={geometry} material={material} />;
}
