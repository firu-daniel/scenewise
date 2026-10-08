"""Fail if any Python module exceeds the line budget (physical lines, as ``wc -l``)."""

import sys
import tomllib
from pathlib import Path


def max_lines() -> int:
    """Read ``[tool.scenewise.gates] max_module_lines`` from pyproject.toml."""
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return int(config["tool"]["scenewise"]["gates"]["max_module_lines"])


def main(roots: list[str]) -> int:
    """Return 1 if any module under ``roots`` exceeds the budget."""
    limit = max_lines()
    offenders = [
        (path, n)
        for root in roots
        for path in sorted(Path(root).rglob("*.py"))
        if (n := len(path.read_text(encoding="utf-8").splitlines())) > limit
    ]
    for path, n in offenders:
        print(f"{path}: {n} lines > {limit}; split the module")
    return 1 if offenders else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["src", "tests", "scripts"]))
