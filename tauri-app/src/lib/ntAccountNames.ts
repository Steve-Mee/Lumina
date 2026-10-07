/** Client mirror of lumina_core/broker/ninjatrader/account_names.py. The server remains the gate. */

export const DEMO_HELP =
  "Open NinjaTrader. Ga naar Control Center, tab Accounts. " +
  "Kopieer de papieren rekening letter voor letter, inclusief de cijfers. " +
  "Een brokerage-demo begint met DEMO, bijvoorbeeld DEMO5042070. " +
  "Een lokale simulatie begint met Sim, bijvoorbeeld Sim101. Playback en Backtest horen hier ook. " +
  "Dit is de rekening waarop Lumina in SIM orders plaatst. " +
  "Lumina schrijft die naam in %APPDATA%\\LUMINA\\fabric.json als AccountName " +
  "en in config.yaml als broker.ninjatrader.account_name. " +
  "NinjaTrader leest AccountName bij het opstarten. Na een wijziging sluit je NinjaTrader " +
  "en start je hem opnieuw. Er hoeft niets gecompileerd te worden.";

export const REAL_HELP =
  "Kopieer uit dezelfde lijst, Control Center → Accounts, de live brokerage-rekening. " +
  "Neem de naam van die rij over, letter voor letter. " +
  "Het is een andere rij dan de demo. Een live naam begint met de code van je broker, " +
  "zoals een Apex- of brokerage-nummer, en is een andere naam dan DEMO5042070 of Sim101. " +
  "Lumina schrijft die naam alleen in fabric.json als RealAccountName. " +
  "De NinjaTrader-koppeling blijft AccountName, de demo-rekening. " +
  "Orders blijven op de demo-rekening. REAL blijft gesloten tot die fase is vrijgegeven. " +
  "Een lege real-naam wordt bewaard als leeg: Lumina vult geen rekening in.";

const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$/;

function label(name: string): string {
  return (name ?? "").trim();
}

export function isBrokerDemoName(name: string): boolean {
  return label(name).toLowerCase().startsWith("demo");
}

export function isLocalSimName(name: string): boolean {
  const lowered = label(name).toLowerCase();
  if (!lowered) return false;
  return (
    lowered.startsWith("sim") ||
    lowered.includes("sim101") ||
    lowered.includes("playback") ||
    lowered.includes("backtest")
  );
}

export function isPaperAccountName(name: string): boolean {
  return isLocalSimName(name) || isBrokerDemoName(name);
}

export function nameShapeOk(name: string): boolean {
  return NAME_RE.test(label(name));
}

export function validateAccountPair(
  demo: string,
  real: string,
): { ok: true; demo: string; real: string } | { ok: false; errors: string[] } {
  const demoName = label(demo);
  const realName = label(real);
  const errors: string[] = [];
  if (!demoName) {
    errors.push("Demo-account ontbreekt. " + DEMO_HELP);
  } else if (!nameShapeOk(demoName)) {
    errors.push(
      "Demo-account bevat tekens die niet in een NinjaTrader-accountnaam horen. " +
        "Gebruik de naam uit Control Center, letters en cijfers, zoals DEMO5042070 of Sim101.",
    );
  } else if (!isPaperAccountName(demoName)) {
    errors.push(
      "Demo-account moet een papieren rekening zijn: een naam die met DEMO begint, " +
        "of een lokale Sim-, Playback- of Backtest-rekening. " +
        DEMO_HELP,
    );
  }
  if (!realName) {
    errors.push("Real-account ontbreekt. " + REAL_HELP);
  } else if (!nameShapeOk(realName)) {
    errors.push(
      "Real-account bevat tekens die niet in een NinjaTrader-accountnaam horen. " +
        "Gebruik de live naam uit Control Center.",
    );
  } else if (isPaperAccountName(realName)) {
    errors.push(
      "Real-account is een demo- of Sim-naam. " +
        "Zet die naam in het demo-veld. Het real-veld krijgt de live brokerage-rekening. " +
        REAL_HELP,
    );
  }
  if (demoName && realName && demoName.toLocaleLowerCase() === realName.toLocaleLowerCase()) {
    errors.push(
      "Demo en real zijn dezelfde naam. " +
        "Control Center toont het als twee rekeningen. Kopieer elk veld uit zijn eigen rij.",
    );
  }
  if (errors.length > 0) return { ok: false, errors };
  return { ok: true, demo: demoName, real: realName };
}
