"""RED for spec fictional-platforms: P2 files name only fictional gig platforms, so the demo shows no real brands.

Mapping (product decision): real brand -> fictional display / platform id / doc-id code, e.g. the "dd" code becomes
"qd" and "D-0002-<old>-feb" becomes "D-0002-ridenow-feb". w2_employer is unchanged.
"""
from __future__ import annotations

import base64
import json
import re
import zlib
from decimal import Decimal
from pathlib import Path

import pytest

from proofkit.common.llm import FakeLLM
from proofkit.contracts import EarningsDocument
from proofkit.wallet import build_wallet, load_wallet_rules, parse_documents
from tests.acceptance.test_wallet_golden import replay_llm

ROOT = Path(__file__).resolve().parents[3]
THIS_FILE = Path(__file__).resolve()

# Stored reversed so this file never contains the words it bans. A brand matches when no letter comes right before
# it, so "<brand>_jan.txt" and "<brand>er" are caught but words like "prover" are not.
_REVERSED_BRANDS = ("hsadrood", "rehsad", "rebu", "tfyl", "tracatsni", "krowpu", "tibbarksat", "rrevif", "buhburg",
                    "xelf nozama", "revor")
# A space in a brand also matches "_" or nothing ("<a> <b>", "<a>_<b>", "<a><b>").
BRANDS = re.compile(r"(?<![a-z])(?:" + "|".join(w[::-1].replace(" ", "[ _]?") for w in _REVERSED_BRANDS) + ")",
                    re.I)

P2_GLOBS = ("config/wallet_rules.json", "fixtures/earnings_docs/*", "fixtures/earnings/*", "fixtures/wallet/*",
            "tests/unit/wallet/*.py", "tests/acceptance/test_wallet_*.py", "src/proofkit/wallet/*.py",
            "src/proofkit/wallet/HANDOFF.md")

FICTIONAL_IDS = ["quickdash", "ridenow", "liftlane", "cartcrew", "freelanceyard", "errandhive", "gigloft", "mealhop",
                 "parcelsprint", "petpacer", "w2_employer"]
OLD_DOC_CODES = ("-dd-", "-ic-", "-uber-", "-tr-", "-uw-")


def _p2_files() -> list[Path]:
    files = {p.resolve() for g in P2_GLOBS for p in ROOT.glob(g) if p.is_file()}
    return sorted(files - {THIS_FILE})


def _b64_texts(path: Path) -> list[str]:
    """Decoded text of every content_b64 in a JSON fixture, including inflated pdf streams."""
    if path.suffix != ".json":
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    out = []
    for obj in data if isinstance(data, list) else [data]:
        if isinstance(obj, dict) and isinstance(obj.get("content_b64"), str):
            raw = base64.b64decode(obj["content_b64"])
            out.append(raw.decode("latin-1"))
            for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
                try:
                    out.append(zlib.decompress(stream).decode("latin-1"))
                except zlib.error:
                    pass  # not compressed: already scanned as raw bytes
    return out


def test_no_real_platform_brands_in_p2_files():
    hits = []
    for path in _p2_files():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if BRANDS.search(line):
                hits.append(f"{rel}:{n}")
        for k, decoded in enumerate(_b64_texts(path)):
            for n, line in enumerate(decoded.splitlines(), 1):
                if BRANDS.search(line):
                    hits.append(f"{rel}:content_b64[{k}]:{n}")
    assert hits == [], "real platform brands found:\n" + "\n".join(hits)


def test_known_platforms_are_the_fictional_set():
    cfg = json.loads((ROOT / "config" / "wallet_rules.json").read_text(encoding="utf-8"))
    assert cfg["known_platforms"] == FICTIONAL_IDS


def _ids_to_check() -> list[str]:
    ids = []
    for folder in ("earnings_docs", "wallet"):
        for p in sorted((ROOT / "fixtures" / folder).glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and "doc_id" in d:
                ids += [f"{p.name}: doc_id={d['doc_id']}", f"{p.name}: filename={d.get('filename', '')}"]
    for p in sorted((ROOT / "fixtures" / "earnings").glob("*.json")):
        for r in json.loads(p.read_text(encoding="utf-8")):
            ids += [f"{p.name}: source_doc_id={r['source_doc_id']}", f"{p.name}: record_id={r['record_id']}"]
    return ids


def test_fixture_doc_ids_use_fictional_codes():
    ids = _ids_to_check()
    assert ids, "no fixture ids found"
    bad = [i for i in ids if any(code in i.split("=", 1)[1] for code in OLD_DOC_CODES)]
    assert bad == [], "old real-brand doc codes:\n" + "\n".join(bad)


@pytest.mark.parametrize("given, want", [
    ("QuickDash Courier", "quickdash"),
    ("RideNow Eats", "ridenow"),
    ("parcelsprint driver", "parcelsprint"),
    ("quickdasher", "quickdasher"),          # only whole words match: stays unknown
])
def test_brand_plus_product_maps_to_fictional_platform(wallet_rules_path, given, want):
    rules = load_wallet_rules(wallet_rules_path)
    text = f"platform,period_start,period_end,hours,gross_pay\n{given},2027-02-01,2027-02-28,30,410.00\n"
    doc = EarningsDocument(doc_id="c1", member_id="SYN-0001", filename="x.csv", doc_type="csv", content_text=text)
    (r,) = parse_documents([doc], "SYN-0001", FakeLLM({}), rules=rules)
    assert r.platform == want
    assert (r.confidence >= rules.min_record_confidence) is (want in rules.known_platforms)


def test_every_persona_wallet_still_matches_expected_months(members, earnings_docs_by_member, golden_records,
                                                            expected_wallet, wallet_rules_path, demo_today):
    """End-to-end guard for the rename: docs, golden records, rules and expected months must stay consistent."""
    rules = load_wallet_rules(wallet_rules_path)
    assert earnings_docs_by_member
    for member_id, docs in earnings_docs_by_member.items():
        w = build_wallet(members[member_id], docs, replay_llm(golden_records), rules, demo_today)
        months = {m.month: m for m in w.months}
        for month, exp in expected_wallet[member_id].items():
            m = months[month]
            got = (m.qualifies, m.total_hours, m.total_income)
            assert got == (exp["qualifies"], Decimal(exp["total_hours"]), Decimal(exp["total_income"])), \
                (member_id, month)
