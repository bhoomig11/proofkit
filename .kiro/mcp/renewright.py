"""Cross-platform launcher for the RenewRight MCP server (stdio JSON-RPC).

Usage: python .kiro/mcp/renewright.py

Runs `python -m proofkit.integration.mcp_server` from the repo root with the
project's .venv interpreter when it exists, falling back to sys.executable.
stdin, stdout and stderr are inherited. subprocess.call is used because
os.exec* breaks stdio on Windows.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]


def find_python() -> str:
    """Return the venv interpreter for this platform, else sys.executable."""
    venv = REPO_ROOT / ".venv"
    candidate = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    return str(candidate) if candidate.is_file() else sys.executable


if __name__ == "__main__":
    sys.exit(subprocess.call([find_python(), "-m", "proofkit.integration.mcp_server"], cwd=REPO_ROOT))
