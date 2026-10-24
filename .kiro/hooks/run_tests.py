"""Cross-platform pytest launcher for Kiro hooks.

Usage: python .kiro/hooks/run_tests.py <pytest args...>

Runs pytest from the repo root with the project's .venv interpreter when it
exists, falling back to sys.executable. Exit code 5 (no tests collected) is
mapped to 0 so an empty selection doesn't fail the hook.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
NO_TESTS_COLLECTED: int = 5


def find_python() -> str:
    """Return the venv interpreter for this platform, else sys.executable."""
    win = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    posix = REPO_ROOT / ".venv" / "bin" / "python"
    for candidate in ((win, posix) if os.name == "nt" else (posix, win)):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def main(argv: list[str]) -> int:
    """Run pytest with argv from the repo root and return its exit code."""
    cmd: list[str] = [find_python(), "-m", "pytest", *argv]
    code: int = subprocess.run(cmd, cwd=REPO_ROOT, check=False).returncode
    return 0 if code == NO_TESTS_COLLECTED else code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
