"""
P1B owns this. Produces the accuracy numbers for the pitch slide.

  python eval/run_eval.py                       # offline: golden findings (regression check, should be 100%)
  python eval/run_eval.py --predictions DIR     # score FindingsBundle JSON files (e.g. real LLM extraction output)
  python eval/run_eval.py --live                # explains how to produce DIR (P1B may not import extraction)

Prints a markdown table and writes eval/results/<timestamp>.json (gitignored).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):          # run as a script: make `eval` and `proofkit` importable
    sys.path.insert(0, str(ROOT))

from eval import metrics as m  # noqa: E402
from proofkit.contracts import ClinicalNote, FindingsBundle, Member  # noqa: E402
from proofkit.reasoning import decide_exemption, load_frailty_rules  # noqa: E402

FIXTURES = ROOT / "fixtures"
RULES_PATH = ROOT / "config" / "frailty_rules.json"
SWEEP_MONTHS = (6, 12, 24)
LIVE_HELP = ("--live needs findings from P1A's extract_findings, which P1B code must not import.\n"
             "Run the extractor with the real LLM (P1A's live run or FINAL's run_member), save one FindingsBundle\n"
             "JSON per member into a folder, then run:  python eval/run_eval.py --predictions <folder>")


def _load(path: Path):
    return json.loads(path.read_text())


def load_fixtures():
    members = {d["member_id"]: Member.model_validate(d) for d in _load(FIXTURES / "members" / "members.json")["members"]}
    notes = [ClinicalNote.model_validate(_load(p)) for p in sorted((FIXTURES / "notes").glob("*.json"))]
    golden = {}
    for p in sorted((FIXTURES / "findings").glob("*.golden.json")):
        b = FindingsBundle.model_validate(_load(p))
        golden[b.member_id] = b
    expected = _load(FIXTURES / "decisions" / "expected.json")
    return members, notes, golden, expected


def load_predictions(folder: Path) -> dict[str, FindingsBundle]:
    out = {}
    for p in sorted(folder.glob("*.json")):
        b = FindingsBundle.model_validate(_load(p))
        out[b.member_id] = b
    return out


def build_report(mode: str, members, notes, golden, predicted, expected) -> dict:
    rules = load_frailty_rules(RULES_PATH)
    as_of = date.fromisoformat(expected["as_of"])
    g_all = [f for b in golden.values() for f in b.findings]
    p_all = [f for mid, b in predicted.items() if mid in golden for f in b.findings]
    prf = m.finding_prf(g_all, p_all)
    status = m.status_accuracy(g_all, p_all)
    got = {mid: decide_exemption(b, members[mid], rules, as_of).outcome.value
           for mid, b in predicted.items() if mid in members}
    dec = m.decision_accuracy({mid: e["outcome"] for mid, e in expected["expected"].items()}, got)
    inj = m.injection_resistance(notes, p_all)
    sweep = m.lookback_sweep({mid: b for mid, b in predicted.items() if mid in members}, members, rules, as_of,
                             SWEEP_MONTHS)
    pair = lambda c: {f"{a}->{b}": n for (a, b), n in sorted(c.items())}  # noqa: E731
    return {
        "mode": mode, "as_of": as_of.isoformat(), "rules_version": rules.rules_version,
        "lookback_months": rules.lookback_months.value,
        "findings": {"tp": prf.tp, "fp": prf.fp, "fn": prf.fn, "precision": prf.precision, "recall": prf.recall,
                     "f1": prf.f1},
        "status": {"accuracy": status.accuracy, "correct": status.correct, "matched": status.matched,
                   "confusion": pair(status.confusion)},
        "decisions": {"accuracy": dec.accuracy, "correct": dec.correct, "total": dec.total,
                      "confusion": pair(dec.confusion), "predicted": got},
        "injection": {"rate": inj.rate, "resisted": inj.resisted, "total": inj.total, "failed_notes": inj.failed_notes},
        "lookback_sweep": {str(k): v for k, v in sweep.items()},
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def to_markdown(r: dict) -> str:
    f, s, d, i = r["findings"], r["status"], r["decisions"], r["injection"]
    lines = [
        f"### ProofKit eval ({r['mode']}, as of {r['as_of']}, rules {r['rules_version']})", "",
        "| Metric | Value | Detail |", "|---|---|---|",
        f"| Status accuracy | {_pct(s['accuracy'])} | {s['correct']}/{s['matched']} matched findings |",
        f"| Finding precision | {_pct(f['precision'])} | tp {f['tp']}, fp {f['fp']} |",
        f"| Finding recall | {_pct(f['recall'])} | tp {f['tp']}, fn {f['fn']} |",
        f"| Finding F1 | {_pct(f['f1'])} | matched on (note, ICD-10 category, status) |",
        f"| Decision accuracy | {_pct(d['accuracy'])} | {d['correct']}/{d['total']} members |",
        f"| Injection resistance | {_pct(i['rate'])} | {i['resisted']}/{i['total']} adversarial notes |",
        "", "**Decision confusion (expected -> predicted)**", "",
        "| Expected | Predicted | Count |", "|---|---|---|",
        *[f"| {k.split('->')[0]} | {k.split('->')[1]} | {n} |" for k, n in d["confusion"].items()],
        "", f"**Lookback sweep (config: {r['lookback_months']} months)**", "",
        "| Member | " + " | ".join(f"{k} mo" for k in r["lookback_sweep"]) + " |",
        "|---|" + "---|" * len(r["lookback_sweep"]),
    ]
    members = sorted(next(iter(r["lookback_sweep"].values()), {}))
    for mid in members:
        lines.append(f"| {mid} | " + " | ".join(r["lookback_sweep"][k][mid] for k in r["lookback_sweep"]) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="explain how to evaluate real LLM extraction")
    ap.add_argument("--predictions", type=Path, help="folder of FindingsBundle JSON files to score")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results", help="where to write the JSON report")
    args = ap.parse_args(argv)
    if args.live:
        print(LIVE_HELP, file=sys.stderr)
        return 2

    members, notes, golden, expected = load_fixtures()
    predicted = load_predictions(args.predictions) if args.predictions else golden
    report = build_report("predictions" if args.predictions else "offline", members, notes, golden, predicted, expected)
    print(to_markdown(report))
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nreport written to {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
