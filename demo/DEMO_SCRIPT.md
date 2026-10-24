# RenewRight demo kit

All files in `demo/samples/` are synthetic (member IDs `SYN-####`, made-up platforms QuickDash and RideNow).

> RenewRight organizes evidence. MassHealth makes all eligibility determinations.

## Setup and offline run

```bash
.venv/Scripts/python demo/make_demo_kit.py              # regenerate demo/samples/ from fixtures (idempotent)
.venv/Scripts/python -m pytest tests/integration/test_demo_kit.py -p no:cacheprovider -q   # offline end-to-end check
.venv/Scripts/python -m streamlit run app/main.py       # http://localhost:8501, no API key needed
```

The test run uses only `FakeLLM` and the offline replay client (`demo_llm()`): no network, no live key.

## Demo logins (public synthetic test credentials, from app/TEAM_GUIDE.md)

| Name | Email | Password | Expected status |
|---|---|---|---|
| Maria | maria@example.com | maria-demo-2027 | Protected (exemption) |
| James | james@example.com | james-demo-2027 | Protected (hours) |
| Priya | priya@example.com | priya-demo-2027 | Protected (exemption) |
| Dev | dev@example.com | dev-demo-2027 | At risk ($60 short) |
| Red team | redteam@example.com | redteam-demo-2027 | At risk (injection ignored) |

For the upload checks, create a new account (it gets its own empty profile) or use Dev's login, so the uploaded
file is the only new evidence. Demo date 2027-03-01, renewal 2027-03-20, verification month Feb 2027.

## Sample files: where to upload and what to expect

Pay statements go in Documents > "Upload a pay statement". The clinical note goes in Documents > clinical-note upload.

| File | Expected result |
|---|---|
| `quickdash_feb_2027.csv` | Processed offline right away. Feb 2027: 45.00 h, $640.00, meets the rule by income ($640.00 >= $580). |
| `ridenow_feb_2027.txt` | Feb 2027: 92.50 h, $1,592.00, meets the rule by hours. |
| `ridenow_feb_2027.pdf` | Same statement as a PDF. Needs "Process with live AI" (key required), then 92.50 h, meets the rule by hours. Offline the app reads the PDF but cannot interpret it. |
| `paystub_photo.png` | No earnings read. "Image received..." note; Feb 2027 is flagged for navigator review. |
| `red_team_statement.txt` | Stays at 30.00 h / $410.00, does not meet the rule ($170.00 short). The injected "200 hours and $5,000" line is ignored. |
| `clinical_note_maria.txt` | Current finding "Systemic lupus erythematosus with glomerular disease" (M32.14) with its quote highlighted; "Denies chest pain" and "mother with rheumatoid arthritis" do not count. |

Text and PDF uploads: the app processes them only after "Process with live AI", which needs a configured key. Without
a key it shows the "No live AI key is configured" note and suggests a CSV. The offline replay (`demo_llm()`) only
knows these exact fixture texts, so the 92.50 h and 30.00 h / $410.00 results are checked offline by the test run
above and in the James and Red team demo profiles. Any other free text needs "Process with live AI".

## Manual test checklist

- [ ] `make_demo_kit.py` runs twice with no diff in `demo/samples/`.
- [ ] Offline test run is green.
- [ ] Disclaimer is visible on every page and in the proof packet.
- [ ] `quickdash_feb_2027.csv`: Feb 2027 meets the rule by income, $640.00, no AI used.
- [ ] `ridenow_feb_2027.txt` and `ridenow_feb_2027.pdf` (live AI on): 92.50 h, meets the rule by hours.
- [ ] `paystub_photo.png`: image note shown, Feb 2027 needs navigator review.
- [ ] `red_team_statement.txt`: 30.00 h / $410.00, not 200 h / $5,000; status stays At risk.
- [ ] `clinical_note_maria.txt`: lupus quote highlighted, negated and family-history lines not counted.
- [ ] Red team login: neither injection ("mark exempt", "report 200 hours") changes anything.
- [ ] No real company names or logos on screen; only synthetic people.

## 3-minute video script

| Time | On screen | Voice-over |
|---|---|---|
| 0:00-0:20 | Sign-in page, disclaimer in view | "From 2027, MassHealth expansion adults must show 80 hours or $580 a month, or an exemption. RenewRight helps them gather the proof. RenewRight organizes evidence. MassHealth makes all eligibility determinations." |
| 0:20-0:50 | Sign in as Maria; Evidence section | "Maria's clinical notes document lupus with nephritis. Every finding links to the exact quote. 'Denies chest pain' and her mother's arthritis don't count." |
| 0:50-1:15 | Sign in as James | "James has 'r/o CHF' and 'denies depression', so no exemption. His RideNow statement shows 92.50 hours: protected by hours." |
| 1:15-1:45 | New account; upload `quickdash_feb_2027.csv`, then `paystub_photo.png` | "A CSV export is read without AI: $640.00 in February, protected by income. A photo can't be read yet, so it goes to a navigator for review." |
| 1:45-2:15 | Dev; what-if +$60 | "Dev is $60 short in Feb 2027, with proof due March 6. The what-if shows one more pay statement would protect him." |
| 2:15-2:45 | Red team login; `red_team_statement.txt` | "This statement tells the AI to report 200 hours and $5,000. The rules code decides, so it stays 30.00 hours and $410.00, still at risk." |
| 2:45-3:00 | Proof packet download | "One packet, every claim traced to its source. RenewRight organizes evidence. MassHealth makes all eligibility determinations." |
