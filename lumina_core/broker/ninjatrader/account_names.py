"""Exact NinjaTrader account names for the operator setup.

The demo name is the only account the addon may bind. The real name is stored
beside it and is never the bind name. REAL orders stay closed.
"""

from __future__ import annotations

import re

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")
_EXPLICIT_PAPER_MODES = frozenset({"sim", "paper", "sim_real_guard"})

DEMO_HELP = (
    "Open NinjaTrader. Ga naar Control Center, tab Accounts. "
    "Kopieer de papieren rekening letter voor letter, inclusief de cijfers. "
    "Een brokerage-demo begint met DEMO, bijvoorbeeld DEMO5042070. "
    "Een lokale simulatie begint met Sim, bijvoorbeeld Sim101. Playback en Backtest horen hier ook. "
    "Dit is de rekening waarop Lumina in SIM orders plaatst. "
    "Lumina schrijft die naam in %APPDATA%\\LUMINA\\fabric.json als AccountName "
    "en in config.yaml als broker.ninjatrader.account_name. "
    "NinjaTrader leest AccountName bij het opstarten. Na een wijziging sluit je NinjaTrader "
    "en start je hem opnieuw. Er hoeft niets gecompileerd te worden."
)
REAL_HELP = (
    "Kopieer uit dezelfde lijst, Control Center → Accounts, de live brokerage-rekening. "
    "Neem de naam van die rij over, letter voor letter. "
    "Het is een andere rij dan de demo. Een live naam begint met de code van je broker, "
    "zoals een Apex- of brokerage-nummer, en is een andere naam dan DEMO5042070 of Sim101. "
    "Lumina schrijft die naam alleen in fabric.json als RealAccountName. "
    "De NinjaTrader-koppeling blijft AccountName, de demo-rekening. "
    "Orders blijven op de demo-rekening. REAL blijft gesloten tot die fase is vrijgegeven. "
    "Een lege real-naam wordt bewaard als leeg: Lumina vult geen rekening in."
)


def _label(name: str) -> str:
    return str(name or "").strip()


def is_broker_demo_name(name: str) -> bool:
    """Brokerage demo such as DEMO5042070."""
    return _label(name).lower().startswith("demo")


def is_local_sim_name(name: str) -> bool:
    """Local Sim, Playback, or Backtest account."""
    lowered = _label(name).lower()
    if not lowered:
        return False
    return lowered.startswith("sim") or "sim101" in lowered or "playback" in lowered or "backtest" in lowered


def is_paper_account_name(name: str) -> bool:
    return is_local_sim_name(name) or is_broker_demo_name(name)


def paper_orders_allowed(name: str, mode: str) -> bool:
    """Local Sim is paper. A DEMO name is paper only in an explicit non-real mode."""
    if is_local_sim_name(name):
        return True
    return str(mode or "").strip().lower() in _EXPLICIT_PAPER_MODES and is_broker_demo_name(name)


def name_shape_ok(name: str) -> bool:
    return bool(_NAME_RE.match(_label(name)))


class NtAccountRejected(ValueError):
    """The pair was refused. errors are safe to show to the operator."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        ValueError.__init__(self, " ".join(self.errors))


def validate_account_pair(demo: str, real: str) -> tuple[str, str]:
    """Return the trimmed pair, or raise NtAccountRejected."""
    demo_name = _label(demo)
    real_name = _label(real)
    errors: list[str] = []
    if not demo_name:
        errors.append("Demo-account ontbreekt. " + DEMO_HELP)
    elif not name_shape_ok(demo_name):
        errors.append(
            "Demo-account bevat tekens die niet in een NinjaTrader-accountnaam horen. "
            "Gebruik de naam uit Control Center, letters en cijfers, zoals DEMO5042070 of Sim101."
        )
    elif not is_paper_account_name(demo_name):
        errors.append(
            "Demo-account moet een papieren rekening zijn: een naam die met DEMO begint, "
            "of een lokale Sim-, Playback- of Backtest-rekening. " + DEMO_HELP
        )
    if not real_name:
        errors.append("Real-account ontbreekt. " + REAL_HELP)
    elif not name_shape_ok(real_name):
        errors.append(
            "Real-account bevat tekens die niet in een NinjaTrader-accountnaam horen. "
            "Gebruik de live naam uit Control Center."
        )
    elif is_paper_account_name(real_name):
        errors.append(
            "Real-account is een demo- of Sim-naam. "
            "Zet die naam in het demo-veld. Het real-veld krijgt de live brokerage-rekening. " + REAL_HELP
        )
    if demo_name and real_name and demo_name.casefold() == real_name.casefold():
        errors.append(
            "Demo en real zijn dezelfde naam. "
            "Control Center toont het als twee rekeningen. Kopieer elk veld uit zijn eigen rij."
        )
    if errors:
        raise NtAccountRejected(errors)
    return demo_name, real_name
