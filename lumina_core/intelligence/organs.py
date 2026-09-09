"""Two-organ SSOT: Lungs (training physics) vs Voice (language). Never conflate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lumina_core.intelligence.copy import OLLAMA_GLOSS, VLLM_BLOCKED_WINDOWS, VLLM_GLOSS, XAI_GLOSS
from lumina_core.intelligence.resolve import VoiceProviderId, VoiceWorkload, resolve_provider

LungsStatus = Literal["ready", "cpu_fallback", "missing_toolkit", "installing", "error"]
VoiceStatus = Literal[
    "off",
    "ollama_ready",
    "ollama_missing",
    "vllm_ready",
    "vllm_blocked",
    "remote_ready",
    "error",
]
VoiceProvider = VoiceProviderId

_BIRTH_PHASES = frozenset({"genesis", "birth", "awakening", ""})


class BlockedProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    reason_human: str = Field(min_length=1)


class OperatorChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    visible: bool
    enabled: bool
    default: bool
    label: str
    help: str
    consequence_if_yes: str
    consequence_if_no: str


class LungsTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LungsStatus
    cuda_available: bool
    device_name: str | None = None
    human_status: str = Field(min_length=1)
    next_action: str | None = None


class VoiceTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VoiceStatus
    selected_provider: VoiceProvider
    allowed_providers: list[str]
    blocked_providers: list[BlockedProvider]
    human_status: str = Field(min_length=1)
    next_action: str | None = None


class NewsTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workload: Literal["voice"] = "voice"
    provider_preference: list[str] = Field(default_factory=lambda: ["grok_remote", "ollama", "vllm"])
    can_run: bool
    order_path_coupled: Literal[False] = False
    human_status: str = Field(min_length=1)

    @model_validator(mode="after")
    def _lock_order_path(self) -> NewsTruth:
        if self.order_path_coupled is not False:
            raise ValueError("news.order_path_coupled is invariant false")
        object.__setattr__(self, "order_path_coupled", False)
        return self


class OrgansTruth(BaseModel):
    """organs_truth_v1 — the only JSON the Setup UI should render for stack choice."""

    model_config = ConfigDict(extra="forbid")

    dto: Literal["organs_truth_v1"] = "organs_truth_v1"
    lungs: LungsTruth
    voice: VoiceTruth
    news: NewsTruth
    operator_choices: list[OperatorChoice]
    conflation_warnings: list[str] = Field(default_factory=list)
    next_honest_steps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _laws(self) -> OrgansTruth:
        blocked_ids = {item.id for item in self.voice.blocked_providers}
        if "vllm" in self.voice.allowed_providers and "vllm" in blocked_ids:
            raise ValueError("L1: vllm cannot be both allowed and blocked")
        if self.news.order_path_coupled is not False:
            raise ValueError("L4: news.order_path_coupled must be false")
        return self


@dataclass(slots=True)
class OrgansProbe:
    """Injected facts so tests never need a live GPU or Ollama."""

    os_name: str
    vllm_supported: bool
    vllm_health_ok: bool
    vllm_importable: bool
    cuda_available: bool
    gpu_name: str | None
    torch_ok: bool
    sb3_ok: bool
    ollama_installed: bool
    grok_key_present: bool
    requested_provider: VoiceProvider
    intelligence_mode: str = "auto"
    profile_tier: str = "sweet"
    ladder_phase: str = "genesis"
    lungs_installing: bool = False


def is_windows(os_name: str) -> bool:
    lowered = str(os_name or "").strip().lower()
    return lowered.startswith("win") or lowered == "nt"


def default_provider_order(
    *,
    os_name: str,
    vllm_supported: bool,
    vllm_health_ok: bool,
) -> list[str]:
    """Windows or unsupported vLLM → ollama, grok_remote. Never vllm-first on Windows."""
    if is_windows(os_name) or not vllm_supported:
        return ["ollama", "grok_remote"]
    if vllm_health_ok:
        return ["vllm", "ollama", "grok_remote"]
    return ["ollama", "grok_remote"]


def default_strategy_provider_chain(*, os_name: str | None = None) -> str:
    import os as os_mod

    name = os_name if os_name is not None else os_mod.name
    return ",".join(default_provider_order(os_name=name, vllm_supported=False, vllm_health_ok=False))


def _lungs_from_probe(probe: OrgansProbe) -> LungsTruth:
    if probe.lungs_installing:
        return LungsTruth(
            status="installing",
            cuda_available=bool(probe.cuda_available),
            device_name=probe.gpu_name,
            human_status="Installing the training engine. This does not install the talking assistant.",
            next_action="Wait for python scripts/install_birth_physics_stack.py to finish.",
        )
    if not probe.torch_ok or not probe.sb3_ok:
        return LungsTruth(
            status="missing_toolkit",
            cuda_available=False,
            device_name=probe.gpu_name,
            human_status=(
                "The training engine is not installed yet. Run the physics installer. "
                "This does not install the talking assistant."
            ),
            next_action="python scripts/install_birth_physics_stack.py",
        )
    if probe.cuda_available:
        device = probe.gpu_name or "NVIDIA graphics card"
        return LungsTruth(
            status="ready",
            cuda_available=True,
            device_name=device,
            human_status=f"A graphics card is available ({device}). LUMINA will practise trades on it.",
            next_action=None,
        )
    return LungsTruth(
        status="cpu_fallback",
        cuda_available=False,
        device_name=probe.gpu_name,
        human_status="No compatible NVIDIA graphics card. LUMINA will still learn, just slower.",
        next_action=None,
    )


def _select_voice(probe: OrgansProbe, allowed: list[str]) -> VoiceProvider:
    requested = str(probe.requested_provider or "off").strip().lower()
    if requested == "vllm":
        if is_windows(probe.os_name) or not probe.vllm_supported or not probe.vllm_health_ok or probe.vllm_importable:
            if "ollama" in allowed and probe.ollama_installed:
                return "ollama"
            if "grok_remote" in allowed and probe.grok_key_present:
                return "grok_remote"
            if "ollama" in allowed:
                return "ollama"
            if "grok_remote" in allowed:
                return "grok_remote"
            return "off"
        return "vllm"
    if requested in allowed:
        return requested  # type: ignore[return-value]
    if requested == "off":
        return "off"
    if "ollama" in allowed:
        return "ollama"
    if "grok_remote" in allowed:
        return "grok_remote"
    return "off"


def _voice_status(selected: VoiceProvider, probe: OrgansProbe, windows: bool) -> VoiceStatus:
    if selected == "off":
        return "off"
    if selected == "ollama":
        return "ollama_ready" if probe.ollama_installed else "ollama_missing"
    if selected == "grok_remote":
        return "remote_ready" if probe.grok_key_present else "error"
    if selected == "vllm":
        if windows or not probe.vllm_supported:
            return "vllm_blocked"
        return "vllm_ready" if probe.vllm_health_ok else "vllm_blocked"
    return "error"


def _choices(probe: OrgansProbe, *, windows: bool, selected: VoiceProvider) -> list[OperatorChoice]:
    vllm_ok = (not windows) and probe.vllm_supported
    vllm_enabled = vllm_ok and probe.vllm_health_ok and not probe.vllm_importable
    return [
        OperatorChoice(
            id="ollama",
            visible=True,
            enabled=True,
            default=selected == "ollama",
            label="Local assistant (Ollama)",
            help=(
                f"{OLLAMA_GLOSS} Needed later for news headlines and questions. "
                "Not needed to start learning."
            ),
            consequence_if_yes="We install Ollama and a tested model that fits this PC.",
            consequence_if_no="You can use the cloud assistant or learn trades only.",
        ),
        OperatorChoice(
            id="grok_remote",
            visible=True,
            enabled=True,
            default=selected == "grok_remote",
            label="Cloud assistant (xAI)",
            help=f"{XAI_GLOSS} LUMINA asks a cloud brain when it must read the live web (news, X).",
            consequence_if_yes="LUMINA uses an xAI key. No local GPU memory for talking.",
            consequence_if_no="Stay on a local assistant or turn talking off.",
        ),
        OperatorChoice(
            id="off",
            visible=True,
            enabled=True,
            default=selected == "off",
            label="Off",
            help="Learn trades only. You can add an assistant later. News reading stays off.",
            consequence_if_yes="Learning to trade does not wait for the assistant.",
            consequence_if_no="Pick a local or cloud assistant when you want explanations or news.",
        ),
        OperatorChoice(
            id="vllm",
            visible=vllm_ok,
            enabled=vllm_enabled,
            default=selected == "vllm",
            label="Extra-fast local assistant (vLLM)",
            help=(
                f"{VLLM_GLOSS} A separate high-speed talk server. Only on Linux/WSL2. Own installation. "
                "Does not replace the learning engine. Do not install it into the same "
                "Python environment as training."
            ),
            consequence_if_yes="LUMINA talks HTTP to a separate vLLM server. Training stays on CUDA/PyTorch.",
            consequence_if_no="Use Ollama or the cloud instead.",
        ),
    ]


def build_organs_truth(probe: OrgansProbe) -> OrgansTruth:
    windows = is_windows(probe.os_name)
    blocked: list[BlockedProvider] = []
    allowed: list[str] = ["ollama", "grok_remote", "off"]
    if windows or not probe.vllm_supported:
        blocked.append(BlockedProvider(id="vllm", reason_human=VLLM_BLOCKED_WINDOWS if windows else VLLM_GLOSS))
    elif probe.vllm_health_ok and not probe.vllm_importable:
        allowed.append("vllm")
    else:
        blocked.append(
            BlockedProvider(
                id="vllm",
                reason_human=(
                    "The extra-fast local assistant is visible but not healthy. "
                    "Default snaps to Ollama. It does not replace the learning engine."
                ),
            )
        )
    if windows and "vllm" in allowed:
        raise ValueError("L1: Windows native must not allow vllm")
    mode = str(probe.intelligence_mode or "auto").strip().lower()
    requested = probe.requested_provider
    if windows and mode == "force_high" and requested == "vllm":
        requested = "ollama"
    probe_for_select = OrgansProbe(
        os_name=probe.os_name,
        vllm_supported=probe.vllm_supported,
        vllm_health_ok=probe.vllm_health_ok,
        vllm_importable=probe.vllm_importable,
        cuda_available=probe.cuda_available,
        gpu_name=probe.gpu_name,
        torch_ok=probe.torch_ok,
        sb3_ok=probe.sb3_ok,
        ollama_installed=probe.ollama_installed,
        grok_key_present=probe.grok_key_present,
        requested_provider=requested,
        intelligence_mode=probe.intelligence_mode,
        profile_tier=probe.profile_tier,
        ladder_phase=probe.ladder_phase,
        lungs_installing=probe.lungs_installing,
    )
    selected = _select_voice(probe_for_select, allowed)
    if selected == "vllm" and (windows or not probe.vllm_supported or not probe.vllm_health_ok or probe.vllm_importable):
        raise ValueError("L2: refused vllm selection")
    lungs = _lungs_from_probe(probe)
    voice_status = _voice_status(selected, probe, windows)
    voice_human, voice_next = _voice_copy(selected, voice_status, probe)
    news_provider = resolve_provider(
        VoiceWorkload.NEWS_INTERPRET,
        allowed_providers=[item for item in allowed if item != "off"],
        selected_provider=selected,
    )
    news_can = news_provider != "off"
    news = NewsTruth(
        can_run=news_can,
        human_status=(
            "News reading uses the thinking assistant (cloud first). It never places or sizes orders."
            if news_can
            else "News reading is off until a thinking assistant is available. It never places or sizes orders."
        ),
    )
    warnings: list[str] = []
    if windows and selected == "vllm":
        warnings.append("vLLM is not a training engine and is blocked on Windows.")
    phase = str(probe.ladder_phase or "genesis").strip().lower()
    if phase in _BIRTH_PHASES and voice_status in {"ollama_ready", "vllm_ready", "remote_ready"}:
        pass
    steps = [
        "Learning to trade does not wait for the assistant.",
        "Next: finish Setup, then Genesis / Birth. Voice can stay off.",
    ]
    if lungs.next_action:
        steps.insert(0, f"Training engine: {lungs.next_action}")
    if voice_next:
        steps.append(f"Thinking assistant: {voice_next}")
    return OrgansTruth(
        lungs=lungs,
        voice=VoiceTruth(
            status=voice_status,
            selected_provider=selected,
            allowed_providers=allowed,
            blocked_providers=blocked,
            human_status=voice_human,
            next_action=voice_next,
        ),
        news=news,
        operator_choices=_choices(probe, windows=windows, selected=selected),
        conflation_warnings=warnings,
        next_honest_steps=steps,
    )


def _voice_copy(
    selected: VoiceProvider,
    status: VoiceStatus,
    probe: OrgansProbe,
) -> tuple[str, str | None]:
    if selected == "off" or status == "off":
        return (
            "Thinking assistant is off. LUMINA can still learn trades. News reading stays off.",
            None,
        )
    if selected == "ollama":
        if probe.ollama_installed:
            return (f"Local assistant is ready. {OLLAMA_GLOSS}", None)
        return (
            f"Local assistant is not installed yet. {OLLAMA_GLOSS}",
            "Install Ollama and a tested model that fits this PC.",
        )
    if selected == "grok_remote":
        if probe.grok_key_present:
            return (f"Cloud assistant is ready. {XAI_GLOSS}", None)
        return (f"Cloud assistant needs an xAI key. {XAI_GLOSS}", "Add an xAI key in Credentials.")
    if selected == "vllm":
        if status == "vllm_ready":
            return (f"Extra-fast local assistant is healthy. {VLLM_GLOSS}", None)
        return (f"Extra-fast local assistant is blocked. {VLLM_GLOSS}", "Use Ollama or the cloud instead.")
    return ("Thinking assistant hit an error. Learning trades does not wait for it.", None)


def probe_lungs_runtime() -> tuple[bool, bool, bool, str | None]:
    """Return (torch_ok, sb3_ok, cuda_available, device_name). Never stubs SB3."""
    torch_ok = False
    sb3_ok = False
    cuda = False
    device: str | None = None
    try:
        import torch  # pyright: ignore[reportMissingImports]

        torch_ok = True
        cuda = bool(torch.cuda.is_available())
        if cuda:
            device = str(torch.cuda.get_device_name(0) or "").strip() or "NVIDIA GPU"
    except Exception:
        torch_ok = False
    try:
        import stable_baselines3  # noqa: F401  # pyright: ignore[reportMissingImports]

        sb3_ok = True
    except Exception:
        sb3_ok = False
    return torch_ok, sb3_ok, cuda, device


def vllm_importable_here() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("vllm") is not None
    except Exception:
        return False
