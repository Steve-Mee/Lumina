"""``python -m lumina_launcher``: CLI dispatch for loop, headless, and birth status."""

from __future__ import annotations

import sys

from lumina_launcher.cli.dispatch import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
