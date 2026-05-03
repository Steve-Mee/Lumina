from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Iterable


def _collect_lumina_engine_members(engine_file: Path) -> set[str]:
    tree = ast.parse(engine_file.read_text(encoding="utf-8"))
    members: set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "LuminaEngine":
            continue
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                members.add(child.name)
                for decorator in child.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "property":
                        members.add(child.name)
                    if (
                        isinstance(decorator, ast.Attribute)
                        and isinstance(decorator.value, ast.Name)
                        and decorator.attr == "setter"
                    ):
                        members.add(decorator.value.id)
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                members.add(child.target.id)
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        members.add(target.id)
        break

    # Class uses helper delegation; explicit "app" is allowed.
    members.add("app")
    return members


def _iter_python_files(root: Path, scan_dirs: list[str]) -> Iterable[Path]:
    excluded = {
        ".venv",
        ".venv_py313_backup_20260406_104715",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
    }
    for rel in scan_dirs:
        base = (root / rel).resolve()
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in excluded for part in path.parts):
                continue
            yield path


def _find_engine_attr_uses(path: Path, known_members: set[str]) -> list[dict[str, object]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    findings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.value, ast.Name) or node.value.id != "engine":
            continue
        attr = node.attr
        if attr in known_members:
            continue
        findings.append(
            {
                "path": str(path).replace("\\", "/"),
                "line": node.lineno,
                "column": node.col_offset,
                "attr": attr,
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit shim-only engine attribute usage.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument(
        "--engine-file",
        default="lumina_core/engine/lumina_engine.py",
        help="Path to lumina_engine.py relative to repo root.",
    )
    parser.add_argument(
        "--output",
        default="state/engine_shim_audit.json",
        help="Output JSON file path relative to repo root.",
    )
    parser.add_argument(
        "--scan-dirs",
        nargs="+",
        default=["lumina_core", "tests", "lumina_os", "scripts"],
        help="Relative directories to include in the audit scan.",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    engine_file = (root / args.engine_file).resolve()
    output_file = (root / args.output).resolve()

    known_members = _collect_lumina_engine_members(engine_file)
    findings: list[dict[str, object]] = []
    for py_file in _iter_python_files(root, args.scan_dirs):
        findings.extend(_find_engine_attr_uses(py_file, known_members))

    def _sort_key(item: dict[str, object]) -> tuple[str, int]:
        path = str(item.get("path", ""))
        line_value = item.get("line", 0)
        line = int(line_value) if isinstance(line_value, int | str | float) else 0
        return path, line

    findings.sort(key=_sort_key)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(findings, indent=2, ensure_ascii=True), encoding="utf-8")

    print(f"Shim audit complete: {len(findings)} potential shim accesses.")
    print(f"Output: {output_file}")
    if findings:
        top = findings[:20]
        print("Top findings:")
        for item in top:
            print(f"- {item['path']}:{item['line']} -> engine.{item['attr']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
