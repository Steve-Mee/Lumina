from __future__ import annotations

import sys

from lumina_core.engine.runtime_entrypoint import run_with_mode


def main(argv: list[str] | None = None) -> int:
    # Legacy nightly command is preserved; startup logic now lives centrally.
    return run_with_mode("nightly", argv=argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
