/** Mirrors lumina_core.first_boot_ui.exceeds_max_real_days_window */
export function exceeds_max_real_days_window(
  estimatedDays: number,
  maxRealDays: number,
): boolean {
  return estimatedDays > maxRealDays;
}
