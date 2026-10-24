# app/ (FINAL, last 4-5 hours)
Thin Streamlit (or Gradio) front end. Calls ONLY `proofkit.integration.run_member`.
Screens: pick a persona → upload notes and earnings docs → status card (Protected / At risk / Needs review) → evidence with highlighted quotes → download proof packet (HTML/PDF) → reminder text preview.
Security: synthetic personas only, an upload size cap, never render uploaded text as HTML (escape it), and show the disclaimer on every screen.
