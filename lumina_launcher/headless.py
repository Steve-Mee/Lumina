"""Backward-compat headless entry. Prefer :mod:`lumina_launcher.runtime.headless`."""

from lumina_launcher.runtime.headless import repo_root, run_headless

__all__ = ["repo_root", "run_headless"]
