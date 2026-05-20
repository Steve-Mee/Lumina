export interface BirthHelixPalette {
  primary: string;
  secondary: string;
  accent: string;
  pulseSpeed: number;
}

export function birthHelixPalette(activating = false, primed = false): BirthHelixPalette {
  if (activating) {
    return {
      primary: "#ffb347",
      secondary: "#ff6b6b",
      accent: "#ffd93d",
      pulseSpeed: 3.2,
    };
  }
  if (primed) {
    return {
      primary: "#00f0ff",
      secondary: "#c084fc",
      accent: "#a5f3fc",
      pulseSpeed: 1.85,
    };
  }
  return {
    primary: "#00f0ff",
    secondary: "#a78bfa",
    accent: "#67f7ff",
    pulseSpeed: 1.1,
  };
}

export function birthHelixAgitation(activating: boolean, primed = false): number {
  if (activating) {
    return 0.85;
  }
  if (primed) {
    return 0.38;
  }
  return 0.08;
}
