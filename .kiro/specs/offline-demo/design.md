# Offline demo mode: design

## Overview
One new FINAL file, `src/proofkit/integration/demo.py`, provides a replaying `LLMClient` and a mode chooser. The
modules and `run_member` don't know which client they get. The demo client is a `proofkit.common.llm.FakeLLM` whose
three task responses are pure functions over immutable lookup tables built from the fixtures. Using `FakeLLM` gives
`.calls` recording, JSON round-tripping and `LLMError` for unknown tasks without new code.

    app/  ──choose_llm()──► (client, mode) ──► run_member / extract_findings / build_wallet / draft_statement
                                 │
               demo ◄────────────┴────────────► live
     demo_llm(fixtures_dir)               AnthropicClient(load_settings())
     FakeLLM({extract_findings: f,
              extract_earnings: g,
              draft_statement: {"summary": DEMO_SUMMARY}})

## Files
| Path | Change |
|---|---|
| `src/proofkit/integration/demo.py` | new |
| `src/proofkit/integration/__init__.py` | add exports `demo_llm`, `choose_llm`, `MODE_LABELS`, `DEMO_SUMMARY` (additive; `orchestrator.py` untouched) |
| `tests/integration/test_demo_mode.py` | new |
| `src/proofkit/integration/HANDOFF.md` | add an offline demo section |

Imports in `demo.py` are only `proofkit.contracts` and `proofkit.common` (`llm.FakeLLM`, `llm.AnthropicClient`,
`llm.LLMClient`, `config.load_settings`, `redact.get_logger`). It doesn't need extraction, reasoning or wallet.

## Interface
```python
DEMO_SUMMARY: str  # fixed clinical-summary text for task="draft_statement"
MODE_LABELS: Mapping[str, str]  # {"live": "Live LLM", "offline-demo": "Offline demo (recorded answers)"}
DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"

def demo_llm(fixtures_dir: Path | None = None) -> LLMClient:
    """Fixtures (ClinicalNote, EarningsDocument, FindingsBundle, EarningsRecord) -> a replaying FakeLLM.
    Raises ValueError naming the bad file."""

def choose_llm(*, demo: bool | None = None) -> tuple[LLMClient, str]:
    """-> (LLMClient, mode) with mode in {"live", "offline-demo"}. Raises LLMError for demo=False without a key."""
```

## Fixture loading
- Read `fixtures_dir/{notes,earnings_docs}/*.json` and `fixtures_dir/{findings,earnings}/*.golden.json`. Use
  non-recursive globs so `generated/` subfolders are excluded. Read with `encoding="utf-8"`, parse with `json.loads`,
  and validate with `ClinicalNote`, `EarningsDocument`, `FindingsBundle` and `EarningsRecord`.
- Wrap any `OSError`, `json.JSONDecodeError` or `ValidationError` as `ValueError(f"demo fixture {path.name} is invalid")`.
- Document text is `content_text`, or `base64.b64decode(content_b64, validate=True).decode("utf-8")`. Binary types
  (pdf, image) are skipped because they never reach `extract_earnings` as fixture text.
- Build immutable tables (tuples, or `MappingProxyType`) once, at construction:
  - `note_items: note_id -> tuple[finding_item, ...]` and `note_by_text: text -> note_id`
  - `doc_items: doc_id -> tuple[record_item, ...]` and `doc_by_text: text -> doc_id`

## Response shapes
Findings item (exact golden values, in the shape `EXTRACTION_INSTRUCTIONS` asks for):
`{"condition", "icd10", "status", "quote", "quote_start", "quote_end", "confidence"}`, in golden order.

Earnings item (the shape `LLM_INSTRUCTIONS` in wallet/parse.py asks for): `{"platform": platform.upper(),
"period_start": iso, "period_end": iso, "hours": str | None, "gross_income": str, "source_quote", "confidence"}`.
Golden records that share (`source_doc_id`, `source_quote`) are merged back into one statement item: summed
`hours` and `gross_income`, min start, max end. A pre-split item would otherwise fail P2's check that the numbers
appear in the quote. No current golden file needs a merge.

Statement: `{"summary": DEMO_SUMMARY}` with
`DEMO_SUMMARY = "The findings listed above are documented in the cited clinical notes. Each is shown with the exact
quote from the record for the reviewing clinician to confirm."`
This text has no ICD-10-like token, no condition term and no word matched by P1B's `ELIGIBILITY_CLAIM`. Test 3
proves P1B accepts it.

## Routing (pure; depends only on `untrusted_text`)
