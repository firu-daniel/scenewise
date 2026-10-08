"""Fail if any tool configuration exists outside /pyproject.toml.

Every gate reads /pyproject.toml explicitly, but some tools still merge or prefer other
files (uv.toml beats [tool.uv]; typos merges discovered files), so none may exist.
The whole tree is walked, git-ignored files included, because tools read those too;
only tool-owned directories are skipped.
"""

import re
import sys
from pathlib import Path

STRAY = re.compile(
    r"^(uv\.toml|\.?ruff\.toml|\.?mypy\.ini|setup\.cfg|tox\.ini|\.?pytest\.ini"
    r"|\.coveragerc|\.importlinter|_?\.?typos\.toml|pyproject\.toml)$"
)
SKIP = {".git", ".venv", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".hypothesis"}


def stray(root: Path) -> list[Path]:
    """Every configuration file below ``root`` except ``root/pyproject.toml``."""
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if SKIP.intersection(relative.parts) or not path.is_file():
            continue
        if STRAY.match(path.name) and relative != Path("pyproject.toml"):
            found.append(relative)
    return found


def main(root: str) -> int:
    """Print every stray configuration file; return 1 if there is any."""
    found = stray(Path(root))
    for path in found:
        print(f"{path}: tool config must live in /pyproject.toml; remove it")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
