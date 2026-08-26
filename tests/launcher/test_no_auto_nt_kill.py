"""Code Red guard: only explicit Repair may request close_ninjatrader=true."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_only_repair_sets_close_ninjatrader_true() -> None:
    hits: list[tuple[str, int, str]] = []
    for path in (ROOT / "tauri-app" / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if "close_ninjatrader: true" in line or "close_ninjatrader:true" in line:
                hits.append((str(path.relative_to(ROOT)), i, line.strip()))
    assert hits, "expected at least one explicit close=true (Repair)"
    for rel, line_no, line in hits:
        # Must live in fabric actions Repair helper, not Credentials mount soft path
        assert "credentialsFabricActions" in rel.replace("\\", "/"), (
            f"close_ninjatrader:true only allowed in credentialsFabricActions.ts, found {rel}:{line_no} {line}"
        )
        assert "user-initiated" in Path(ROOT / rel).read_text(encoding="utf-8")


def test_heal_default_close_nt_is_false() -> None:
    import inspect

    from lumina_launcher.services import fabric_heal as heal

    sig = inspect.signature(heal.run_fabric_heal)
    assert sig.parameters["close_nt"].default is False


def test_api_heal_request_default_close_false() -> None:
    text = (ROOT / "lumina_os" / "backend" / "setup_endpoints_fabric.py").read_text(encoding="utf-8")
    assert "close_ninjatrader: bool = False" in text
