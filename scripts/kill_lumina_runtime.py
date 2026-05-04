"""Kill Python processes running lumina runtime_entrypoint.py or lumina_runtime.py (standalone helper)."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import psutil
    except ImportError:
        print("psutil not installed", file=sys.stderr)
        return 1

    hits: list[int] = []

    def is_runtime(proc: psutil.Process) -> bool:
        try:
            cmd = " ".join(proc.cmdline() or []).lower().replace("\\", "/")
            return (
                "runtime_entrypoint" in cmd
                or "lumina_runtime.py" in cmd
                or "lumina_core/engine/runtime_entrypoint.py" in cmd
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    for p in psutil.process_iter(["pid"]):
        pid = int(p.info["pid"] or 0)
        if pid <= 0:
            continue
        try:
            proc = psutil.Process(pid)
            if is_runtime(proc):
                hits.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not hits:
        print("No Lumina runtime processes found (runtime_entrypoint / lumina_runtime).")
        return 0

    print(f"Stopping Lumina runtime PIDs: {hits}")
    for pid in hits:
        try:
            parent = psutil.Process(pid)
            kids = parent.children(recursive=True) + [parent]
            for proc in kids:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
                except Exception as exc:
                    print(f"  kill failed pid={proc.pid}: {exc}")
            alive = psutil.wait_procs(kids, timeout=8)[1]
            for proc in alive:
                try:
                    proc.kill()
                except Exception:
                    pass
            print(f"  stopped tree root pid={pid}")
        except psutil.NoSuchProcess:
            print(f"  pid {pid} already gone")
        except Exception as exc:
            print(f"  error root pid={pid}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
