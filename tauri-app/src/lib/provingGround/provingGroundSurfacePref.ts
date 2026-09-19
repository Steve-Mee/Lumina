/** Session override: operator left the Proving Ground cinematic for Phase Hub. */
let preferHub = false;

export function setPreferProvingGroundHub(value: boolean): void {
  preferHub = Boolean(value);
}

export function preferProvingGroundHub(): boolean {
  return preferHub;
}
