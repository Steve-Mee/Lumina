import { invoke, isTauri } from "@tauri-apps/api/core";

export interface NinjaTraderDetectResult {
  installed: boolean;
  exePath: string | null;
}

export interface NinjaTraderLaunchResult {
  launched: boolean;
  installed: boolean;
  exePath: string | null;
  error: string | null;
}

const BROWSER_DETECT: NinjaTraderDetectResult = {
  installed: false,
  exePath: null,
};

const BROWSER_LAUNCH: NinjaTraderLaunchResult = {
  launched: false,
  installed: false,
  exePath: null,
  error: null,
};

export async function detectNinjaTrader(): Promise<NinjaTraderDetectResult> {
  if (!isTauri()) {
    return BROWSER_DETECT;
  }

  return invoke<NinjaTraderDetectResult>("detect_ninjatrader");
}

export async function launchNinjaTrader(): Promise<NinjaTraderLaunchResult> {
  if (!isTauri()) {
    return BROWSER_LAUNCH;
  }

  return invoke<NinjaTraderLaunchResult>("launch_ninjatrader");
}

export const NINJATRADER_DOWNLOAD_URL = "https://ninjatrader.com/GetStarted";

export const NINJATRADER_DEFAULT_PATH =
  "C:\\Program Files\\NinjaTrader 8\\bin\\NinjaTrader.exe";

export const NINJATRADER_PATH_ENV = "NINJATRADER8_PATH";
