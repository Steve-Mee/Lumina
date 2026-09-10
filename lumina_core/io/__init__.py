"""I/O helpers (watchdog import shims, atomic filesystem replace)."""

from lumina_core.io.atomic_fs import atomic_write_text, atomic_write_text_many

__all__ = ["atomic_write_text", "atomic_write_text_many"]
