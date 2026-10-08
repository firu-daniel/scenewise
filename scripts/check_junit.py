"""Fail if a JUnit report contains a skipped or xfailed test.

CI runs every selected test: a skip or an xfail, whatever spelling produced it, fails
the job (q8b §4.2 layer 7). pytest writes both as a ``<skipped`` element; the check is
a text search, as in q8b, so it needs no XML parser.
"""

import re
import sys
from pathlib import Path

SKIPPED_CASE = re.compile(
    r'<testcase classname="([^"]*)" name="([^"]*)"[^>]*>\s*<skipped', re.MULTILINE
)


def skipped(report: Path) -> list[str]:
    """Return ``classname::name`` of every skipped test case, or the bare marker."""
    text = report.read_text(encoding="utf-8")
    names = [f"{c}::{n}" for c, n in SKIPPED_CASE.findall(text)]
    if not names and "<skipped" in text:
        names = [f"{report}: <skipped> element"]
    return names


def main(reports: list[str]) -> int:
    """Return 1 if any report has a skipped or xfailed test."""
    found = [name for report in reports for name in skipped(Path(report))]
    for name in found:
        print(f"skipped or xfailed in CI: {name}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["pytest.xml"]))
