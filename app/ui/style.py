"""Static page CSS: white + teal nav bar, borderless buttons, status circle. No dynamic content in here."""

PAGE_CSS = """<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stHeader"]{display:none}
.block-container{padding-top:0!important;max-width:1180px}
/* nav bar */
.st-key-navbar{position:sticky;top:0;z-index:50;background:var(--pk-surface);padding:.55rem 1rem;margin:0 -1rem 1rem;
  border-bottom:1px solid var(--pk-border);box-shadow:0 2px 10px rgba(15,23,42,.06)}
.pk-brand{display:flex;align-items:center;gap:.45rem;font-size:1.3rem;font-weight:800;line-height:1;white-space:nowrap;
  color:var(--pk-text)}
.pk-brand svg{width:30px;height:34px}
/* section links: plain text, active = teal + underline */
.st-key-navbar div[role="radiogroup"]{gap:.15rem;flex-wrap:wrap}
.st-key-navbar div[role="radiogroup"] label{padding:.35rem .6rem;margin:0;border-radius:0;border:none;
  border-bottom:3px solid transparent;cursor:pointer}
.st-key-navbar div[role="radiogroup"] label > div:first-child{display:none}
.st-key-navbar div[role="radiogroup"] label p{color:var(--pk-muted);font-weight:600}
.st-key-navbar div[role="radiogroup"] label:hover p{color:var(--pk-text)}
.st-key-navbar div[role="radiogroup"] label:has(input:checked){border-bottom-color:var(--pk-accent)}
.st-key-navbar div[role="radiogroup"] label:has(input:checked) p{color:var(--pk-accent);font-weight:800}
.st-key-navbar div[role="radiogroup"] label:has(input:focus-visible){outline:3px solid var(--pk-focus)}
/* buttons: no borders; primary = teal */
.stButton button,.stDownloadButton button,[data-testid="stPopover"] button,[data-testid="stFormSubmitButton"] button{
  border:none!important;box-shadow:none!important;background:transparent;color:var(--pk-text)}
.stButton button:hover,[data-testid="stPopover"] button:hover{background:rgba(15,118,110,.08)}
button[kind="primary"],button[kind="primaryFormSubmit"]{background:var(--pk-accent)!important;
  color:var(--pk-accent-text)!important;font-weight:700}
button[kind="primary"] p,button[kind="primaryFormSubmit"] p{color:var(--pk-accent-text)!important}
/* demo cards on the sign-in page */
.st-key-demo_cards .stButton button{width:100%;text-align:left;justify-content:flex-start;padding:.6rem .8rem;
  background:var(--pk-bg);border-radius:12px}
/* status circle */
.pk-status-dot{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.8rem;font-weight:900;color:#fff}
.pk-dot-ok{background:#15803D}.pk-dot-risk{background:#B91C1C}
.pk-auth-title{text-align:center;margin:2rem 0 .25rem}
.pk-auth-sub{text-align:center;color:var(--pk-muted);margin-bottom:1rem}
</style>"""
