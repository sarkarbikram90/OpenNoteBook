"""OpenNotebook — static first-party import checker.

Scans a Python source tree and reports imports of first-party modules whose target
file/package does not exist on disk. This catches broken internal imports (which
crash the app at startup) without needing the application's third-party
dependencies installed.

Usage:
    python scripts/check_imports.py [root] [top-level-package]

Defaults: root=backend, top-level-package=app

Exit code: 0 if clean, 1 if any broken first-party import is found.
"""

from __future__ import annotations

import ast
import pathlib
import sys


def _module_exists(root: pathlib.Path, module: str) -> bool:
    rel = module.replace(".", "/")
    return (root / f"{rel}.py").exists() or (root / rel / "__init__.py").exists()


def check(root: pathlib.Path, package: str) -> list[str]:
    problems: list[str] = []
    base = root / package
    if not base.exists():
        return [f"source package not found: {base}"]

    for py in base.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            problems.append(f"{py}: SYNTAX ERROR: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(package):
                if not _module_exists(root, node.module):
                    problems.append(f"{py}:{node.lineno}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(package) and not _module_exists(root, alias.name):
                        problems.append(f"{py}:{node.lineno}: import {alias.name}")
    return problems


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1]) if len(argv) > 1 else pathlib.Path("backend")
    package = argv[2] if len(argv) > 2 else "app"
    problems = check(root, package)

    if problems:
        print("BROKEN FIRST-PARTY IMPORTS:")
        for p in problems:
            print(f"  {p}")
        print(f"total={len(problems)}")
        return 1

    print(f"OK: no broken first-party imports in {root / package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
