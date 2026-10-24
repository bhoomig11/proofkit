"""Compute / check the sha256 lock of the frozen contract files.  usage: python scripts/contract_lock.py [--write]"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ["src/proofkit/contracts/models.py", "src/proofkit/contracts/__init__.py"]
LOCK = ROOT / "contracts" / "CONTRACT_LOCK"


def digest() -> str:
    h = hashlib.sha256()
    for rel in FROZEN:
        h.update(rel.encode())
        h.update((ROOT / rel).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


if __name__ == "__main__":
    if "--write" in sys.argv:
        LOCK.write_text(digest() + "\n")
        print("lock written:", digest())
    else:
        ok = LOCK.exists() and LOCK.read_text().strip() == digest()
        print("contract lock OK" if ok else "CONTRACT LOCK MISMATCH: contracts changed without the change protocol")
        sys.exit(0 if ok else 1)
