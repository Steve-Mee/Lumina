import { useFrame, useThree } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

import { organismFitDistance } from "@/lib/organism/organismCameraFit";

const FALLBACK_DIST = 6.4;

function readColumnBox(
  gl: THREE.WebGLRenderer,
  fallbackWidth: number,
  fallbackHeight: number,
): { width: number; height: number } {
  const canvas = gl.domElement;
  const host = canvas.closest(".helix-column-host") as HTMLElement | null;
  const width = host?.clientWidth || canvas.clientWidth || fallbackWidth;
  const height = host?.clientHeight || canvas.clientHeight || fallbackHeight;
  return { width, height };
}

/** Frame the organism inside the live column; distance follows the column box. */
export function OrganismStageCamera({
  halfHeight,
  halfWidth,
  reducedMotion,
}: {
  halfHeight: number;
  halfWidth: number;
  reducedMotion: boolean;
}) {
  const { camera, gl, size } = useThree();
  const target = useRef(new THREE.Vector3(0, 0, FALLBACK_DIST));

  useFrame((_, delta) => {
    if (!(camera instanceof THREE.PerspectiveCamera)) {
      return;
    }
    const box = readColumnBox(gl, size.width, size.height);
    if (box.width < 16 || box.height < 16) {
      camera.position.set(0, 0, FALLBACK_DIST);
      camera.lookAt(0, 0, 0);
      return;
    }
    const dpr = gl.getPixelRatio();
    const needW = Math.max(1, Math.round(box.width * dpr));
    const needH = Math.max(1, Math.round(box.height * dpr));
    if (gl.domElement.width !== needW || gl.domElement.height !== needH) {
      gl.setSize(box.width, box.height, false);
    }
    const aspect = box.width / box.height;
    camera.aspect = aspect;
    const dist = organismFitDistance(halfHeight, halfWidth, aspect, camera.fov);
    target.current.set(0, 0, dist);
    if (reducedMotion) {
      camera.position.copy(target.current);
    } else {
      camera.position.lerp(target.current, Math.min(1, delta * 4));
    }
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  });

  return null;
}
