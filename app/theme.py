"""Coverage Copilot design tokens, static CSS, and Pip mascot."""
from __future__ import annotations

TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#F7F7FC", "surface": "#FFFFFF", "text": "#1D1B2E", "muted": "#55546A",
        "accent": "#5032C8", "accent_text": "#FFFFFF", "ok": "#176B4D", "warn": "#754500",
        "risk": "#9C2639", "focus": "#006C75", "border": "#777389", "mark": "#FFF0A8",
    },
    "dark": {
        "bg": "#12111A", "surface": "#211E2F", "text": "#F7F5FF", "muted": "#C5C0D4",
        "accent": "#C1B4FF", "accent_text": "#171225", "ok": "#74DCB2", "warn": "#FFD07A",
        "risk": "#FF9BAC", "focus": "#75E5EC", "border": "#9A94AB", "mark": "#655515",
    },
}

CONTRAST_PAIRS: tuple[tuple[str, str], ...] = (
    ("text", "bg"), ("text", "surface"), ("muted", "bg"), ("muted", "surface"),
    ("accent", "bg"), ("accent", "surface"), ("accent_text", "accent"),
    ("ok", "bg"), ("ok", "surface"), ("warn", "bg"), ("warn", "surface"),
    ("risk", "bg"), ("risk", "surface"), ("focus", "bg"), ("focus", "surface"),
)


def _variables(tokens: dict[str, str]) -> str:
    return ";".join(f"--pk-{name}:{value}" for name, value in tokens.items())


def build_css(theme: str, *, large_text: bool, comfortable: bool, reduce_motion: bool) -> str:
    """Build static CSS from trusted design tokens and accessibility settings."""
    if theme not in {"system", *TOKENS}:
        raise ValueError("theme must be system, light, or dark")
    selected = TOKENS["light" if theme == "system" else theme]
    dark_media = _variables(TOKENS["dark"])
    motion = "*,*::before,*::after{animation: none !important;transition: none !important;}" if reduce_motion else ""
    size = "html{font-size: 125%;}" if large_text else ""
    spacing = ".stMainBlockContainer{line-height:1.75}.pk-card{padding:1.4rem!important}" if comfortable else ""
    return f"""
<style>
:root{{{_variables(selected)}}}
@media (prefers-color-scheme: dark){{:root{{{dark_media}}}}}
.stApp{{background:var(--pk-bg);color:var(--pk-text)}}
[data-testid="stSidebar"],.pk-card{{background:var(--pk-surface);color:var(--pk-text)}}
.pk-card{{border:1px solid var(--pk-border);border-radius:18px;padding:1rem;margin:.5rem 0}}
.pk-chip{{display:inline-block;border:1px solid var(--pk-border);border-radius:999px;padding:.35rem .75rem;font-weight:700}}
.pk-status-protected{{color:var(--pk-ok)}}.pk-status-needs_review{{color:var(--pk-warn)}}
.pk-status-at_risk{{color:var(--pk-risk)}}
mark{{background:var(--pk-mark);color:var(--pk-text);font-weight:750;text-decoration:underline 2px}}
button,a,input,select,textarea,[role="button"]{{min-height:44px;min-width:44px}}
*:focus-visible{{outline:3px solid var(--pk-focus)!important;outline-offset:3px!important}}
.pk-note{{white-space:pre-wrap;overflow-wrap:anywhere;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
.pk-not-counted{{text-decoration:line-through;text-decoration-thickness:2px}}
.pk-layout{{display:grid;grid-template-columns:minmax(0,2fr) minmax(290px,1fr);gap:1rem}}
@media (max-width:760px){{.pk-layout{{grid-template-columns:1fr}}.block-container{{padding-left:.75rem!important;padding-right:.75rem!important}}}}
@media (prefers-reduced-motion: reduce){{*,*::before,*::after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
{size}{spacing}{motion}
</style>
""".strip()


def pip_svg(status: str) -> str:
    """Return Pip, our original paperwork-shield mascot, in a status-specific pose."""
    faces = {
        "protected": ('M31 43 Q40 51 49 43', 'M18 29 L10 18 M62 29 L70 18', '★'),
        "needs_review": ('M32 47 Q40 43 48 47', 'M18 31 L10 31 M62 31 L70 31', '?'),
        "at_risk": ('M31 47 Q40 41 49 47', 'M18 29 L8 39 M62 29 L72 39', '!'),
    }
    if status not in faces:
        raise ValueError("unknown Pip status")
    mouth, arms, badge = faces[status]
    return f'''<svg aria-hidden="true" viewBox="0 0 80 86" width="104" height="112" role="img">
<path d="M16 12h48v35c0 16-10 25-24 31C26 72 16 63 16 47z" fill="var(--pk-surface)" stroke="var(--pk-accent)" stroke-width="4"/>
<path d="M25 20h30M25 27h22" stroke="var(--pk-muted)" stroke-width="3" stroke-linecap="round"/>
<circle cx="31" cy="37" r="3" fill="var(--pk-text)"/><circle cx="49" cy="37" r="3" fill="var(--pk-text)"/>
<path d="{mouth}" fill="none" stroke="var(--pk-text)" stroke-width="3" stroke-linecap="round"/>
<path d="{arms}" fill="none" stroke="var(--pk-accent)" stroke-width="4" stroke-linecap="round"/>
<circle cx="59" cy="61" r="11" fill="var(--pk-accent)"/><text x="59" y="66" text-anchor="middle" fill="var(--pk-accent-text)" font-size="14" font-weight="800">{badge}</text>
</svg>'''
