/** Visual-only camera fit. Distance grows as the helix column gets taller/narrower. */

export const ORGANISM_FIT_PADDING = 1.38;
export const ORGANISM_FIT_MIN = 3.2;
export const ORGANISM_FIT_MAX = 14;
export const ORGANISM_FIT_FOV_DEG = 34;

export function organismFitDistance(
  halfHeight: number,
  halfWidth: number,
  aspect: number,
  fovDeg: number = ORGANISM_FIT_FOV_DEG,
  padding: number = ORGANISM_FIT_PADDING,
): number {
  const vFov = (Math.max(8, fovDeg) * Math.PI) / 180;
  const safeAspect = Math.max(0.08, aspect);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * safeAspect);
  const distHeight = halfHeight / Math.tan(vFov / 2);
  const distWidth = halfWidth / Math.max(1e-4, Math.tan(hFov / 2));
  const dist = Math.max(distHeight, distWidth) * padding;
  return Math.min(ORGANISM_FIT_MAX, Math.max(ORGANISM_FIT_MIN, dist));
}
