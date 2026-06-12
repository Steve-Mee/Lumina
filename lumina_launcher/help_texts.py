"""Central help text registry for operator UI tooltips."""

from __future__ import annotations

HELP_TEXTS: dict[str, str] = {
    "trading_mode": (
        "Paper = simulatie, SIM = demo account, SIM_REAL_GUARD = SIM met extra "
        "promotie-gates, REAL = live geld met strengere limieten."
    ),
    "risk_profile": "Conservative beperkt agressie, Balanced is standaard, Aggressive maximaliseert leerdruk.",
    "instrument": "Primair instrument waarop runtime/training zich focust.",
    "voice_enabled": "Schakelt voice input/TTS features in de launcher/runtime in.",
    "screen_share_enabled": "Activeert live chart screen share hooks.",
    "dashboard_enabled": "Toont dashboard-georiënteerde feedbackpaden in de UI.",
    "runtime_trace": "Schrijft extra runtime trace events voor diagnose in de logs.",
    "runtime_trace_interval": "Throttle voor repetitieve runtime trace regels (in seconden).",
    "latency_sla": "SLA-drempel (ms) voor fast-path beslissingen bij hoge latency.",
    "training_trades": (
        "Aantal trades voor eerste trainingsronde; hoger = langer maar robuustere start "
        "(richtwaarde: ~450 trades per echte handelsdag; hoge targets vereisen vaak meer historical cycling "
        "en kunnen synthetic top-up vragen als het real window beperkt is)."
    ),
    "prefer_real_data_only": "Gebruik bij voorkeur alleen echte historische data tijdens first boot.",
    "max_real_days": "Maximum aantal historische dagen dat first-boot mag gebruiken.",
    "allow_minimal_synthetic_fallback": "Laat minimale synthetische aanvulling toe als echte data te schaars is.",
    "require_real_simulator_data": "Fail-closed flag: geen neurale/sim dataflow zonder echte marktdataset.",
}


def help_for(key: str, default: str = "") -> str:
    return HELP_TEXTS.get(key, default)
