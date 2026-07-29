"""Run pytest with argv from a file to avoid PowerShell quoting issues."""
from __future__ import annotations

import sys

import pytest

if __name__ == "__main__":
    # Args after script name
    raise SystemExit(pytest.main(sys.argv[1:]))
