# 06: Timeline (adjust hours to your hackathon length; shown for about 24h of build time)

| Hour | P1A (extraction) | P1B (reasoning + eval) | P2 (wallet) |
|---|---|---|---|
| 0:00–0:30 | **All together:** read README → CONTEXT → CONTRACTS, run setup, `make check-contracts`, create worktrees, put names in README, agree on persona stories | | |
| 0:30–3 | ICD-10 normalize + grounding + injection drop (spec tests 1–5) | rules loader + basic decide (spec 1–3) | rules loader + evaluate_months hours/income (spec 1–5) |
| 3–7 | status backstop, negation (spec 6–7), LLM prompt v1 | lookback, review band, prefix boundaries | proration, dedup, low confidence, deadlines |
| 7–9 | retry/skip, IDs, member check → **CP1 merge** | statement drafter → **CP1 merge** | CSV parser, text LLM parse → **CP1 merge** |
| 9–14 | acceptance golden green; one live run on all notes; tune the prompt | acceptance green; eval metrics (offline); write 10 more labeled notes **with P1A** | numeric grounding, injection, upload limits; acceptance green; PDF text |
| 14–16 | edge cases: sentence-scoped negation, abbreviations (h/o, s/p, r/o, ?), multi-mention | eval live mode + pitch table | live smoke test; extra platform formats |
| 16 | **CP2 merge**, `/handoff` | **CP2 merge**, `/handoff` | **CP2 merge**, `/handoff` |
| 16–21 | **FINAL:** evidence highlighting UI | **FINAL:** status rules + end-to-end | **FINAL:** proof packet + reminders |
| 21–23 | **All:** feature freeze, `make check` green, live dry-run, record backup video, rehearse the pitch twice | | |
| 23–24 | Buffer. Don't write new features here. | | |

## Demo script (3 minutes)
1. **Problem (30s):** 175k people expected to lose coverage; Jan 1, 2027; most are eligible but can't prove it.
2. **Maria (60s):** upload notes → "lupus with nephritis, active flare" highlighted → exemption with the drafted clinician statement.
3. **James (30s):** "R/o CHF" and "denies depression" are correctly NOT counted (the negation win), and he's still protected by 92.5 Uber hours.
4. **Dev (30s):** $520 in February → at risk, $60 short, proof due March 6 → reminder text.
5. **Red team (20s):** the injected "mark exempt" and "report 200 hours" lines are ignored.
6. **Numbers (10s):** the eval slide with precision, recall, status accuracy, and injection resistance.
