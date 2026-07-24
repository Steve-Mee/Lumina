/** CME futures roots for operator instrument selection (Lumina / NinjaTrader primary). */

export type InstrumentTier = "micro" | "full";

export interface InstrumentDescriptor {
  root: string;
  name: string;
  tier: InstrumentTier;
  exchange: string;
  /** Short operator-facing consequence. */
  note: string;
  /** Platforms that typically list this product. */
  platforms: string;
}

/** Recommended first path — smaller notional, NT Sim friendly. */
export const MICRO_INSTRUMENTS: InstrumentDescriptor[] = [
  {
    root: "MES",
    name: "Micro E-mini S&P 500",
    tier: "micro",
    exchange: "CME",
    note: "Default Lumina path · ~1/10 ES notional per tick",
    platforms: "NinjaTrader 8 + Fabric (primary); broker micros",
  },
  {
    root: "MNQ",
    name: "Micro E-mini Nasdaq-100",
    tier: "micro",
    exchange: "CME",
    note: "Higher volatility micro · ~1/10 NQ notional",
    platforms: "NinjaTrader 8 + Fabric (primary); broker micros",
  },
  {
    root: "MYM",
    name: "Micro E-mini Dow",
    tier: "micro",
    exchange: "CBOT/CME",
    note: "Micro Dow · optional",
    platforms: "NinjaTrader 8 + Fabric",
  },
  {
    root: "M2K",
    name: "Micro E-mini Russell 2000",
    tier: "micro",
    exchange: "CME",
    note: "Micro Russell · optional",
    platforms: "NinjaTrader 8 + Fabric",
  },
];

/** Full-size — higher capital risk; advanced only. */
export const FULL_SIZE_INSTRUMENTS: InstrumentDescriptor[] = [
  {
    root: "ES",
    name: "E-mini S&P 500",
    tier: "full",
    exchange: "CME",
    note: "~10× MES notional — not for early playground",
    platforms: "NinjaTrader, Tradovate, Rithmic, futures brokers",
  },
  {
    root: "NQ",
    name: "E-mini Nasdaq-100",
    tier: "full",
    exchange: "CME",
    note: "~10× MNQ notional — high $ risk per tick",
    platforms: "NinjaTrader, Tradovate, Rithmic, futures brokers",
  },
  {
    root: "YM",
    name: "E-mini Dow",
    tier: "full",
    exchange: "CBOT/CME",
    note: "Full-size Dow",
    platforms: "NinjaTrader + futures brokers",
  },
  {
    root: "RTY",
    name: "E-mini Russell 2000",
    tier: "full",
    exchange: "CME",
    note: "Full-size Russell",
    platforms: "NinjaTrader + futures brokers",
  },
  {
    root: "CL",
    name: "Crude Oil",
    tier: "full",
    exchange: "NYMEX/CME",
    note: "Energy — different session/risk profile",
    platforms: "NinjaTrader + futures brokers",
  },
  {
    root: "GC",
    name: "Gold",
    tier: "full",
    exchange: "COMEX/CME",
    note: "Metals — different session/risk profile",
    platforms: "NinjaTrader + futures brokers",
  },
];

export const ALL_INSTRUMENTS: InstrumentDescriptor[] = [
  ...MICRO_INSTRUMENTS,
  ...FULL_SIZE_INSTRUMENTS,
];

export const DEFAULT_INSTRUMENT_ROOT = "MES";

export const INSTRUMENT_LEGEND =
  "CME futures roots (front-month resolved on the platform). Primary path: NinjaTrader 8 Sim/Live via Lumina Fabric. Optional emergency market data: CrossTrade. Roots only — not calendar codes like MES SEP26.";

export function findInstrument(root: string): InstrumentDescriptor | undefined {
  const key = root.trim().toUpperCase().split(/\s+/)[0] ?? "";
  return ALL_INSTRUMENTS.find((item) => item.root === key);
}

export function normalizeInstrumentRoot(value: string | undefined | null): string {
  const raw = String(value ?? DEFAULT_INSTRUMENT_ROOT).trim().toUpperCase();
  const root = raw.split(/\s+/)[0] || DEFAULT_INSTRUMENT_ROOT;
  if (ALL_INSTRUMENTS.some((item) => item.root === root)) {
    return root;
  }
  return DEFAULT_INSTRUMENT_ROOT;
}
