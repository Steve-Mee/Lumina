/** Session override: operator left the Awakening cinematic for Phase Hub. */
let preferHub = false;

export function setPreferAwakeningHub(value: boolean): void {
  preferHub = Boolean(value);
}

export function preferAwakeningHub(): boolean {
  return preferHub;
}
