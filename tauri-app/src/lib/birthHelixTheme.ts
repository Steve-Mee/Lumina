import {
  MODE_SIM_ACCENT,
  MODE_SIM_ACCENT_SOFT,
  MODE_SIM_SECONDARY,
} from "@/lib/designTokens";

export interface BirthHelixPalette {
  primary: string;
  secondary: string;
  accent: string;
  pulseSpeed: number;
}

export function birthHelixPalette(activating = false, primed = false): BirthHelixPalette {
  if (activating) {
    return {
      primary: MODE_SIM_ACCENT,
      secondary: "#7c3aed",
      accent: MODE_SIM_ACCENT_SOFT,
      pulseSpeed: 3.2,
    };
  }
  if (primed) {
    return {
      primary: MODE_SIM_ACCENT,
      secondary: "#c084fc",
      accent: MODE_SIM_ACCENT_SOFT,
      pulseSpeed: 1.85,
    };
  }
  return {
    primary: MODE_SIM_ACCENT,
    secondary: MODE_SIM_SECONDARY,
    accent: MODE_SIM_ACCENT_SOFT,
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
