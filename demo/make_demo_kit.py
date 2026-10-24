"""Regenerate the RenewRight demo kit (demo/samples/) from the synthetic fixtures.

Standard library only, deterministic and idempotent: every run writes the same bytes. It reads only files under
fixtures/ and writes only into the output directory (default demo/samples).

Usage:
    .venv/Scripts/python demo/make_demo_kit.py [OUTPUT_DIR]
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
DEFAULT_OUT = ROOT / "demo" / "samples"

# Synthetic CSV export: 45 h / $640.00 in Feb 2027 -> qualifies by income (>= $580), not by hours (< 80).
QUICKDASH_CSV = (b"platform,period_start,period_end,hours,gross_pay\n"
                 b"quickdash,2027-02-01,2027-02-28,45.00,640.00\n")
PNG_SIZE = 8
PNG_RGB = (0x0F, 0x76, 0x6E)  # solid teal


def _fixture(*parts: str) -> dict:
    return json.loads((FIXTURES.joinpath(*parts)).read_text(encoding="utf-8"))


def _text(*parts: str, key: str = "content_text") -> bytes:
    """Fixture JSON -> one text field as UTF-8 bytes, exactly as stored."""
    return _fixture(*parts)[key].encode("utf-8")


def _pdf() -> bytes:
    return base64.b64decode(_fixture("wallet", "D-0002-ridenow-feb-pdf.json")["content_b64"], validate=True)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _png() -> bytes:
    """-> a valid 8x8 solid-colour RGB PNG (no text inside, so it can only be flagged for review)."""
    ihdr = struct.pack(">IIBBBBB", PNG_SIZE, PNG_SIZE, 8, 2, 0, 0, 0)  # 8-bit RGB, no interlace
    row = b"\x00" + bytes(PNG_RGB) * PNG_SIZE  # filter byte 0 + pixels
    idat = zlib.compress(row * PNG_SIZE, 9)
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat)
            + _png_chunk(b"IEND", b""))


SAMPLES: dict[str, Callable[[], bytes]] = {
    "quickdash_feb_2027.csv": lambda: QUICKDASH_CSV,
    "ridenow_feb_2027.txt": lambda: _text("earnings_docs", "D-0002-ridenow-feb.json"),
    "ridenow_feb_2027.pdf": _pdf,
    "paystub_photo.png": _png,
    "red_team_statement.txt": lambda: _text("earnings_docs", "D-0005-qd-feb.json"),
    "clinical_note_maria.txt": lambda: _text("notes", "N-0001-a.json", key="text"),
}


def build_samples() -> dict[str, bytes]:
    """-> {filename: bytes} for every demo sample, built from fixtures only."""
    return {name: make() for name, make in SAMPLES.items()}


def write_samples(out_dir: Path) -> list[Path]:
    """Write every sample into out_dir (created if needed); unchanged files are left untouched."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data in build_samples().items():
        path = out_dir / name
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: [OUTPUT_DIR] (default demo/samples). Returns 0."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        print("usage: make_demo_kit.py [OUTPUT_DIR]", file=sys.stderr)
        return 2
    out_dir = Path(args[0]) if args else DEFAULT_OUT
    for path in write_samples(out_dir):
        print(f"{path.name}  {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
