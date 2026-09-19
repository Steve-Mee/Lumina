/** Session override: operator left the Playground habitat for Phase Hub. */
let preferHub = false;

export function setPreferPlaygroundHub(value: boolean): void {
  preferHub = Boolean(value);
}

export function preferPlaygroundHub(): boolean {
  return preferHub;
}
