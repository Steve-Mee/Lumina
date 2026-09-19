"""Operator copy for Lungs vs Voice. English Setup; Dutch Telegram."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lumina_core.intelligence.organs import LungsTruth, OrgansTruth, VoiceTruth

CUDA_GLOSS = (
    "CUDA is the way an NVIDIA graphics card does heavy math. LUMINA uses it to practise trades."
)
VLLM_GLOSS = "vLLM is an optional extra-fast talking server. It is not the thing that learns to trade."
OLLAMA_GLOSS = "Ollama is a small local talking program. Safe to run next to learning."
XAI_GLOSS = "Cloud brain. Best for reading live news. Needs a key. Does not learn trades by itself."

CUDA_GLOSS_NL = (
    "CUDA is de manier waarop een NVIDIA-videokaart zware sommen doet. "
    "LUMINA gebruikt het om trades te oefenen."
)
VLLM_GLOSS_NL = (
    "vLLM is een optionele extra-snelle praatserver. Het is niet het ding dat leert traden."
)
OLLAMA_GLOSS_NL = "Ollama is een klein lokaal praatprogramma. Veilig naast het leren."
XAI_GLOSS_NL = (
    "Cloud-brein. Beste om live nieuws te lezen. Heeft een sleutel nodig. Leert zelf geen trades."
)

VLLM_BLOCKED_WINDOWS = (
    "This extra-fast local assistant only runs on Linux or WSL2. "
    "On this Windows PC we use Ollama or the cloud instead."
)


def lungs_nl(lungs: LungsTruth) -> str:
    if lungs.status == "ready":
        name = lungs.device_name or "NVIDIA-videokaart"
        return f"Videokaart beschikbaar ({name}). LUMINA oefent trades daarop. {CUDA_GLOSS_NL}"
    if lungs.status == "cpu_fallback":
        return "Geen geschikte NVIDIA-videokaart. LUMINA leert nog steeds, alleen langzamer."
    if lungs.status == "missing_toolkit":
        return "Leermotor ontbreekt. Run de physics-installer. Dit installeert de denk-assistent niet."
    if lungs.status == "installing":
        return "Leermotor wordt gezet. Denk-assistent is apart."
    return "Leermotor-fout. Birth start niet op theater."


def voice_nl(voice: VoiceTruth) -> str:
    if voice.selected_provider == "off" or voice.status == "off":
        return "Uit. Leren van trades wacht niet. Nieuwslezen blijft uit."
    if voice.selected_provider == "ollama":
        return f"Lokaal (Ollama). {OLLAMA_GLOSS_NL}"
    if voice.selected_provider == "grok_remote":
        return f"Cloud (xAI). {XAI_GLOSS_NL}"
    if voice.selected_provider == "vllm":
        return f"Extra-snel lokaal. {VLLM_GLOSS_NL}"
    return "Denk-assistent-fout. Leren gaat door."


def format_setup_telegram(truth: OrgansTruth) -> str:
    next_step = "Genesis / Birth kan starten zonder denk-assistent."
    if truth.next_honest_steps:
        next_step = truth.next_honest_steps[0]
    news_nl = (
        "Nieuwslezen gebruikt de denk-assistent (eerst cloud). Het plaatst nooit orders."
        if truth.news.can_run
        else "Nieuwslezen staat uit tot er een denk-assistent is. Het plaatst nooit orders."
    )
    return (
        f"Leermotor: {lungs_nl(truth.lungs)}\n"
        f"Denk-assistent: {voice_nl(truth.voice)}\n"
        f"Nieuwslezen: {news_nl}\n"
        f"Volgende stap: {next_step}"
    )
