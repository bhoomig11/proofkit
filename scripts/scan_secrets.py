"""Tiny stdlib secret and PHI scanner for tracked + staged files (gitleaks in pre-commit is the stronger check)."""
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "non_synthetic_member": re.compile(r'"member_id"\s*:\s*"(?!SYN-\d{4}")[^"]+"'),
}
SKIP = {"scripts/scan_secrets.py", "src/proofkit/common/redact.py", "tests/unit/common/test_common.py",
        "tests/contract/test_contracts.py"}


def files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True, check=True).stdout
        return [f for f in out.splitlines() if f]
    except Exception:
        return [str(p) for p in Path(".").rglob("*") if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts]


def main() -> int:
    hits = []
    for f in files():
        if f in SKIP or f.endswith((".png", ".jpg", ".pdf", ".zip")):
            continue
        try:
            text = Path(f).read_text(errors="ignore")
        except Exception:  # noqa: S112 - unreadable file, skip
            continue
        for name, rx in PATTERNS.items():
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{f}:{line}: {name}")
    if Path(".env").exists() and ".env" in files():
        hits.append(".env is tracked by git! remove it and rotate the key")
    print("\n".join(hits) if hits else "secret/PHI scan clean")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
