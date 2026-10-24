"""
P1B owns this. Produces the accuracy numbers for the pitch slide.

Offline mode (default): golden findings -> decide_exemption -> compare to fixtures/decisions/expected.json
Live mode (--live):     real notes -> AnthropicClient -> extract_findings -> compare to golden findings,
                        then -> decide_exemption -> compare decisions.  Needs ANTHROPIC_API_KEY in .env.

TODO(P1B), test-first in tests/unit/reasoning/test_eval_metrics.py:
  - finding-level precision / recall / F1, matching on (note_id, icd10 3-char category, status)
  - status accuracy on matched findings (negation handling is the headline metric)
  - decision accuracy + confusion matrix (exempt / not_exempt / review)
  - injection resistance: % of adversarial notes with no injected finding
  - write eval/results/<timestamp>.json (gitignored) and print a markdown table for the slide
Add more hand-labelled notes to fixtures/notes + fixtures/findings (with P1A) to reach 15-20.
"""
import sys


def main() -> int:
    print("eval not implemented yet (P1B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
