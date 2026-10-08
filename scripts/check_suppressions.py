"""Ban gate suppressions in the core and hold line-level ones to a budget elsewhere.

Rules:

1. Banned everywhere: file-level directives (``# ruff: noqa``, ``# flake8: noqa``,
   ``# mypy: ...``, ``# pyright: ...``, ``# isort: skip_file``, a ``# type: ignore``
   before the first statement) and coverage pragmas (inert: ``exclude_lines`` replaces
   coverage's default regex). A whole-file exemption is a reviewed pyproject.toml entry.
2. No line-level suppression (``noqa``, ``type: ignore``, ``fmt: off|skip``,
   ``isort: skip|off``) under the core paths (domain, app, ports).
3. Every other one carries a reason: ``# noqa: S603  # why: static argv``.
4. Their total equals ``suppression_budget`` in pyproject.toml, so adding one is a
   reviewed config change and removing one lowers the budget.

Skip and xfail markers are not counted here: CI fails on any skipped or xfailed test.
"""

import io
import re
import tokenize
import tomllib
from pathlib import Path

ROOTS = ("src", "tests", "scripts")
CORE = (
    "src/scenewise/domain/",
    "src/scenewise/app/",
    "src/scenewise/ports.py",
    "src/scenewise/ports/",
)
FILE_LEVEL = re.compile(
    r"#\s*(?:(?:ruff|flake8)\s*:\s*noqa|mypy\s*:|pyright\s*:|isort\s*:\s*skip_file)"
    r"|pragma[:\s]?\s*no\s*(?:cover|branch)",  # coverage's default regex, any case
    re.IGNORECASE,
)
LINE_LEVEL = re.compile(
    r"\bnoqa\b|type\s*:\s*ignore|fmt\s*:\s*(?:off|skip)|isort\s*:\s*(?:skip|off)",
    re.IGNORECASE,
)
TYPE_IGNORE = re.compile(r"#\s*type\s*:\s*ignore", re.IGNORECASE)
REASON = re.compile(r"#\s*why:\s*\S")
NON_CODE = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.ENCODING}


def comments(path: Path) -> list[tuple[int, str, bool]]:
    """Return ``(line, text, before_first_statement)`` for every comment token."""
    found: list[tuple[int, str, bool]] = []
    seen_code = False
    source = io.StringIO(path.read_text(encoding="utf-8"))
    for tok in tokenize.generate_tokens(source.readline):
        if tok.type == tokenize.COMMENT:
            found.append((tok.start[0], tok.string, not seen_code))
        elif tok.type not in NON_CODE:
            seen_code = True
    return found


def check(path: Path) -> tuple[list[str], int]:
    """Return the errors in ``path`` and its count of budgeted suppressions."""
    in_core = path.as_posix().startswith(CORE)
    errors: list[str] = []
    counted = 0
    for line, text, at_top in comments(path):
        where = f"{path}:{line}: {text}"
        if FILE_LEVEL.search(text) or (at_top and TYPE_IGNORE.search(text)):
            errors.append(f"{where}  [file-level directive or coverage pragma: banned]")
        elif not LINE_LEVEL.search(text):
            continue
        elif in_core:
            errors.append(f"{where}  [suppressions are banned in domain/app/ports]")
        else:
            counted += 1
            if not REASON.search(text):
                errors.append(f"{where}  [add a reason: '  # why: ...']")
    return errors, counted


def budget() -> int:
    """Read ``[tool.scenewise.gates] suppression_budget`` from pyproject.toml."""
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return int(config["tool"]["scenewise"]["gates"]["suppression_budget"])


def main() -> int:
    """Print violations and return 1 if any rule is broken."""
    errors: list[str] = []
    counted = 0
    for path in sorted(p for root in ROOTS for p in Path(root).rglob("*.py")):
        file_errors, file_count = check(path)
        errors += file_errors
        counted += file_count
    allowed = budget()
    if counted != allowed:
        errors.append(
            f"{counted} suppressions outside the core, budget is {allowed}; "
            "a change needs review"
        )
    print("\n".join(errors) or f"suppressions: {counted} (budget {allowed})")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
