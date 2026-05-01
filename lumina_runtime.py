from __future__ import annotations

import sys
import threading
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

try:
    import tkinter as tk
except Exception:
    tk = None

from lumina_core.bootstrap import bootstrap_runtime, create_public_api
from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.engine.runtime_entrypoint import run_with_mode


@lru_cache(maxsize=1)
def get_container() -> ApplicationContainer:
    # Lazy container creation keeps import-time compatibility for validators.
    return create_application_container()


def get_public_api() -> Mapping[str, object]:
    return create_public_api(get_container())


def __getattr__(name: str):
    # Module introspection (for example by coverage/pytest/importlib) can probe
    # dunder attributes that are not explicitly defined. Those lookups must not
    # bootstrap the full runtime container.
    if name.startswith("__"):
        raise AttributeError(f"module 'lumina_runtime' has no attribute '{name}'")

    if name == "tk" and tk is not None:
        return tk

    container = get_container()

    _compat_fn_map = {
        "detect_market_regime": container.engine.detect_market_regime,
    }
    if name in _compat_fn_map:
        return _compat_fn_map[name]

    attr_map = {
        "CONFIG": "config",
        "ENGINE": "engine",
        "ANALYSIS_SERVICE": "analysis_service",
        "engine": "engine",
        "RUNTIME_CONTEXT": "runtime_context",
        "runtime_context": "runtime_context",
        "logger": "logger",
        "SWARM_SYMBOLS": "swarm_symbols",
        "INSTRUMENT": "primary_instrument",
    }
    if name in attr_map:
        return getattr(container, attr_map[name])

    api = get_public_api()
    if name in api:
        return api[name]

    raise AttributeError(f"module 'lumina_runtime' has no attribute '{name}'")


def _run_evolution_startup_prompt() -> None:
    """Eerste start: parallel realities + Fase-3 stress-keuzes (OHLC / PPO), met uitleg."""
    import os

    from lumina_core.evolution.bot_stress_choices import (
        BOT_STRESS_CHOICES_FILE,
        TOOLTIP_NEURO_OHLC_NL,
        TOOLTIP_OHLC_DNA_NL,
        resolve_neuro_ohlc_stress_rollouts,
        resolve_ohlc_reality_stress_enabled,
        save_bot_stress_choices,
    )
    from lumina_core.evolution.parallel_reality_config import (
        ENV_PARALLEL_REALITIES,
        PARALLEL_REALITIES_MAX,
        PARALLEL_REALITIES_MIN,
        SESSION_FILE,
        TOOLTIP_SHORT_NL,
        clamp_parallel,
        format_tooltip_nl,
        recommend_parallel_realities,
        resolve_parallel_realities,
        save_parallel_realities_session,
    )

    if os.getenv("LUMINA_SKIP_STARTUP_DIALOG", "").lower() in ("1", "true", "yes", "on"):
        return
    force = os.getenv("LUMINA_FORCE_EVOLUTION_STARTUP_DIALOG", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    ) or os.getenv("LUMINA_FORCE_PARALLEL_REALITIES_DIALOG", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if os.getenv(ENV_PARALLEL_REALITIES) and not force:
        return
    if SESSION_FILE.is_file() and BOT_STRESS_CHOICES_FILE.is_file() and not force:
        return

    rec = int(recommend_parallel_realities())
    default_v = int(resolve_parallel_realities())
    if SESSION_FILE.is_file() and force:
        try:
            from lumina_core.evolution.parallel_reality_config import load_session_parallel_realities

            s = load_session_parallel_realities()
            if s is not None:
                default_v = int(s)
        except Exception:
            pass

    ohlc_default = bool(resolve_ohlc_reality_stress_enabled())
    neuro_default = bool(resolve_neuro_ohlc_stress_rollouts())
    help_text = format_tooltip_nl()

    if tk is not None:
        root = tk.Tk()
        root.title("Lumina — evolutie & stress (opstarten)")
        root.attributes("-topmost", True)
        root.resizable(True, True)
        f = tk.Frame(root, padx=14, pady=12, bg="#121212")
        f.pack(fill="both", expand=True)
        tk.Label(
            f,
            text="Evolutie: parallelle universa + OHLC / PPO-stress (Fase 3)",
            font=("Segoe UI", 12, "bold"),
            fg="#e0e0e0",
            bg="#121212",
        ).pack(anchor="w")
        tip = tk.Text(f, width=78, height=7, wrap="word", bg="#1e1e1e", fg="#c8c8c8", font=("Segoe UI", 9))
        tip.insert("1.0", f"{TOOLTIP_SHORT_NL}\n\n{help_text}\n\nAanbevolen parallel op dit systeem: {rec}")
        tip.config(state="disabled")
        tip.pack(fill="x", pady=(6, 2))

        stress_tip = tk.Text(f, width=78, height=6, wrap="word", bg="#1a1f24", fg="#a8b8c8", font=("Segoe UI", 9))
        stress_tip.insert("1.0", f"• OHLC (DNA): {TOOLTIP_OHLC_DNA_NL}\n\n• PPO (neuro): {TOOLTIP_NEURO_OHLC_NL}")
        stress_tip.config(state="disabled")
        stress_tip.pack(fill="x", pady=(0, 6))

        row = tk.Frame(f, bg="#121212")
        row.pack(anchor="w", pady=4)
        tk.Label(row, text="Parallel realities (1–50):", fg="#e0e0e0", bg="#121212").pack(side="left", padx=(0, 8))
        var = tk.StringVar(value=str(default_v))
        sp = tk.Spinbox(
            row,
            from_=1,
            to=50,
            textvariable=var,
            width=6,
            font=("Consolas", 11),
        )
        sp.pack(side="left")
        tk.Label(row, text=f"  (advise: {rec} op basis van je CPU)", fg="#7fbf7f", bg="#121212").pack(side="left", padx=8)

        var_ohlc = tk.IntVar(value=1 if ohlc_default else 0)
        var_neuro = tk.IntVar(value=1 if neuro_default else 0)
        cfrm = tk.Frame(f, bg="#121212")
        cfrm.pack(anchor="w", pady=(6, 2))
        tk.Checkbutton(
            cfrm,
            text="OHLC-stress op historische data (DNA-evolutie, als echte ticks geladen zijn)",
            variable=var_ohlc,
            bg="#121212",
            fg="#e8e8e8",
            selectcolor="#2a2a2a",
            activebackground="#121212",
            activeforeground="#e8e8e8",
        ).pack(anchor="w")
        tk.Checkbutton(
            cfrm,
            text="PPO: meerdere OHLC-rollouts per kandidaat (ZWAAR; alleen met meerdere stress-universa)",
            variable=var_neuro,
            bg="#121212",
            fg="#e8e8e8",
            selectcolor="#2a2a2a",
            activebackground="#121212",
            activeforeground="#e8e8e8",
        ).pack(anchor="w")

        def on_ok() -> None:
            try:
                n = clamp_parallel(int(str(var.get()).strip()))
            except (TypeError, ValueError):
                n = 1
            save_parallel_realities_session(n)
            save_bot_stress_choices(
                ohlc_reality_stress_enabled=bool(var_ohlc.get()),
                use_ohlc_stress_rollouts=bool(var_neuro.get()),
            )
            root.destroy()

        def on_cancel() -> None:
            try:
                n = clamp_parallel(int(str(var.get()).strip()))
            except (TypeError, ValueError):
                n = max(1, default_v)
            save_parallel_realities_session(n)
            save_bot_stress_choices(
                ohlc_reality_stress_enabled=bool(var_ohlc.get()),
                use_ohlc_stress_rollouts=bool(var_neuro.get()),
            )
            root.destroy()

        btns = tk.Frame(f, bg="#121212")
        btns.pack(anchor="e", pady=(8, 0))
        tk.Button(btns, text="OK (opslaan & starten)", command=on_ok, padx=10, pady=4).pack(side="right", padx=4)
        tk.Button(btns, text="Annuleer (sla huidige vakjes op)", command=on_cancel, padx=10, pady=4).pack(side="right")
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        sw = root.winfo_screenwidth()
        shh = int(root.winfo_screenheight())
        root.geometry(f"+{(sw - w) // 2}+{(shh - h) // 2}")
        root.mainloop()
        return

    # Console fallback
    try:
        line = input(
            f"Parallel realities [{PARALLEL_REALITIES_MIN}-{PARALLEL_REALITIES_MAX}], "
            f"aanbevolen {rec} [enter={default_v}]: "
        )
    except EOFError:
        line = ""
    if not str(line).strip():
        n = default_v
    else:
        try:
            n = clamp_parallel(int(str(line).strip(), 10))
        except (TypeError, ValueError):
            n = default_v
    save_parallel_realities_session(n)
    try:
        o = input(f"OHLC-stress DNA aan? [j/N] (aanbevolen: {'J' if ohlc_default else 'N'}): ").strip().lower()
    except EOFError:
        o = ""
    ohlc_on = ohlc_default if not o else o in ("j", "y", "1", "ja")
    try:
        p = input(f"PPO meerdere OHLC-rollouts? [j/N] (aanbevolen: {'J' if neuro_default else 'N'}): ").strip().lower()
    except EOFError:
        p = ""
    neuro_on = neuro_default if not p else p in ("j", "y", "1", "ja")
    save_bot_stress_choices(ohlc_reality_stress_enabled=ohlc_on, use_ohlc_stress_rollouts=neuro_on)


def main(argv: list[str] | None = None) -> int:
    runtime_argv = argv if argv is not None else sys.argv[1:]
    if runtime_argv:
        return run_with_mode("real", argv=runtime_argv)

    load_dotenv(Path(__file__).resolve().parent / ".env")
    _run_evolution_startup_prompt()

    container = get_container()
    runtime_module = sys.modules.get("__main__")
    if runtime_module is not None:
        container.bind_runtime_module(runtime_module)

    # Wire back-reference so RuntimeContext.__getattr__ can delegate to services
    container.runtime_context.container = container

    bootstrap_runtime(container)

    if bool(getattr(container.config, "use_human_main_loop", False)):
        threading.Thread(target=container.analysis_service.run_main_loop, daemon=True).start()

    container.operations_service.run_forever_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
