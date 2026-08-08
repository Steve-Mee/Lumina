/**
 * Lumina-wide condition tones for requirement cards.
 *
 * - ok (green): condition met
 * - warn (orange): not met yet, but progressing / not critically far
 * - danger (red): not met and critically off-target or worsening
 * - default: no scored condition (informational only)
 */

export type ConditionTone = "default" | "ok" | "warn" | "danger" | "accent";

export type ConditionDirection = "higher" | "lower" | "band";

export interface ConditionEvalInput {
  /** Current metric value (null = unknown → default). */
  value: number | null | undefined;
  /** Higher-is-better: min to pass. Lower-is-better: max to pass. */
  target?: number | null;
  /** Band mode: inclusive [min, max]. */
  min?: number | null;
  max?: number | null;
  direction: ConditionDirection;
  /**
   * Optional slope / delta: positive means "moving toward better" for the
   * given direction (caller normalizes so + = improving).
   */
  improving?: boolean | null;
  /** Gap beyond which "not met" becomes danger even without slope. */
  criticalGap?: number;
}

/**
 * Resolve green / orange / red for a gated metric.
 *
 * Improving without a hard meet → orange.
 * Not met + worsening or critically far → red.
 * Met → green.
 */
export function resolveConditionTone(input: ConditionEvalInput): ConditionTone {
  const { value, direction } = input;
  if (value == null || !Number.isFinite(Number(value))) {
    return "default";
  }
  const v = Number(value);
  const improving = input.improving === true;
  const worsening = input.improving === false;
  const criticalGap = input.criticalGap ?? 0.15;

  if (direction === "higher") {
    const target = input.target;
    if (target == null || !Number.isFinite(Number(target))) {
      return "default";
    }
    const t = Number(target);
    if (v >= t) return "ok";
    const gap = t - v;
    if (improving || gap <= criticalGap) return "warn";
    if (worsening || gap > criticalGap) return "danger";
    return "warn";
  }

  if (direction === "lower") {
    const max = input.max ?? input.target;
    if (max == null || !Number.isFinite(Number(max))) {
      return "default";
    }
    const m = Number(max);
    if (v <= m) return "ok";
    const gap = v - m;
    if (improving || gap <= criticalGap) return "warn";
    if (worsening || gap > criticalGap) return "danger";
    return "warn";
  }

  // band
  const min = input.min;
  const max = input.max;
  if (
    min == null ||
    max == null ||
    !Number.isFinite(Number(min)) ||
    !Number.isFinite(Number(max))
  ) {
    return "default";
  }
  const lo = Number(min);
  const hi = Number(max);
  if (v >= lo && v <= hi) return "ok";
  const dist = v < lo ? lo - v : v - hi;
  if (improving || dist <= criticalGap) return "warn";
  return "danger";
}

/** Boolean gate: true → ok, false → danger (or warn if improving). */
export function resolveBooleanConditionTone(
  met: boolean | null | undefined,
  options?: { improving?: boolean | null },
): ConditionTone {
  if (met == null) return "default";
  if (met) return "ok";
  if (options?.improving === true) return "warn";
  return "danger";
}

/** Map condition tone onto value text colors (shared with field cards). */
export const CONDITION_VALUE_TEXT_CLASS: Record<ConditionTone, string> = {
  default: "text-cyan-100",
  ok: "text-emerald-300",
  warn: "text-amber-300",
  /** Skill-later / diagnostic — not a fail gate (violet, never rose). */
  accent: "text-violet-200",
  danger: "text-rose-200",
};
