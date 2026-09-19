/** Session override: operator left the Apprenticeship cinematic for Phase Hub. */
let preferHub = false;

export function setPreferApprenticeshipHub(value: boolean): void {
  preferHub = Boolean(value);
}

export function preferApprenticeshipHub(): boolean {
  return preferHub;
}
