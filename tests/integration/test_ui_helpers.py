"""Pure helper tests for the RenewRight UI."""
from __future__ import annotations

import html
import re
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

from app.a11y import contrast_ratio, relative_luminance
from app.format import countdown, format_money, long_date, month_long, plain_protected_by
from app.highlight import escape_plain, highlight_quote
from app.theme import CONTRAST_PAIRS, TOKENS, build_css, pip_svg


def test_display_formatting_is_plain_and_exact() -> None:
    assert format_money(Decimal("60")) == "$60.00"
    assert format_money(Decimal("1234.567")) == "$1,234.57"
    assert long_date(date(2027, 3, 6)) == "March 6, 2027"
    assert month_long("2027-02") == "February 2027"
    assert countdown(date(2027, 3, 1), date(2027, 3, 6)) == "Proof due in 5 days"
    assert countdown(date(2027, 3, 6), date(2027, 3, 6)) == "Proof due today"
    assert countdown(date(2027, 3, 7), date(2027, 3, 6)) == "Proof was due 1 day ago"
    assert plain_protected_by("exemption:medically_frail") == "Medical frailty exemption"
    assert plain_protected_by("compliance:hours") == "80+ hours this month"
    assert plain_protected_by("compliance:income") == "$580+ income this month"
    assert plain_protected_by(None) is None


@given(st.decimals(min_value=Decimal("0"), max_value=Decimal("999999999.99"), places=4,
                   allow_nan=False, allow_infinity=False))
def test_format_money_is_decimal_two_places(value: Decimal) -> None:
    rendered = format_money(value)
    assert re.fullmatch(r"\$\d{1,3}(?:,\d{3})*\.\d{2}", rendered)
    assert "e" not in rendered.lower()


@given(st.text(max_size=300))
def test_escape_plain_never_leaves_script_markup(value: str) -> None:
    rendered = escape_plain(value + "<script>alert(1)</script>")
    assert "<script" not in rendered.lower()
    assert "&lt;script&gt;" in rendered.lower()


@given(st.text(min_size=1, max_size=200), st.data())
def test_highlight_quote_escapes_every_slice_and_marks_exact_quote(text: str, data: st.DataObject) -> None:
    start = data.draw(st.integers(min_value=0, max_value=len(text) - 1))
    end = data.draw(st.integers(min_value=start + 1, max_value=len(text)))
    rendered = highlight_quote(text, start, end)
    assert rendered.count("<mark>") == 1
    assert rendered.count("</mark>") == 1
    inside = rendered.split("<mark>", 1)[1].split("</mark>", 1)[0]
    assert html.unescape(inside) == text[start:end]
    without_our_mark = rendered.replace("<mark>", "").replace("</mark>", "")
    assert html.unescape(without_our_mark) == text
    assert "<script" not in without_our_mark.lower()


@pytest.mark.parametrize("bad", [(-1, 1), (2, 1), (0, 4)])
def test_highlight_quote_rejects_invalid_offsets(bad: tuple[int, int]) -> None:
    with pytest.raises(ValueError):
        highlight_quote("abc", *bad)


def test_wcag_reference_contrast() -> None:
    assert relative_luminance("#000000") == pytest.approx(0)
    assert relative_luminance("#ffffff") == pytest.approx(1)
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21)


def test_all_declared_theme_pairs_meet_wcag_aa() -> None:
    assert set(TOKENS) == {"light", "dark"}
    assert CONTRAST_PAIRS
    for theme, tokens in TOKENS.items():
        for foreground, background in CONTRAST_PAIRS:
            assert foreground in tokens and background in tokens
            assert contrast_ratio(tokens[foreground], tokens[background]) >= 4.5, (
                theme, foreground, background
            )


def test_css_and_pip_are_static_accessible_assets() -> None:
    css = build_css("dark", large_text=True, comfortable=True, reduce_motion=True)
    assert "--pk-bg:" in css
    assert "prefers-color-scheme" in css
    assert "focus-visible" in css
    assert "44px" in css
    assert "font-size: 125%" in css
    assert "animation: none" in css
    for status in ("protected", "needs_review", "at_risk"):
        mascot = pip_svg(status)
        assert mascot.startswith("<svg")
        assert 'aria-hidden="true"' in mascot
    with pytest.raises(ValueError):
        pip_svg("unknown")


def test_packet_contains_verified_summary_and_escapes_dynamic_content() -> None:
    from pathlib import Path

    from app.data import load_demo_data
    from app.state import build_member_view, make_llm
    from proofkit.integration.packet import build_packet_html

    root = Path(__file__).resolve().parents[2]
    data = load_demo_data(root)
    llm, _ = make_llm(live=False, data=data)
    view = build_member_view("SYN-0005", data, llm, root / "config/frailty_rules.json",
                             root / "config/wallet_rules.json")
    malicious_member = view.member.model_copy(update={"display_name": "<script>alert(1)</script>"})
    packet = build_packet_html(malicious_member, view.status, view.findings)
    assert "RenewRight evidence packet" in packet
    assert "At risk" in packet
    assert "February 2027" in packet
    assert "$410.00" in packet
    assert "30" in packet
    assert "<mark>" in packet
    assert "right ankle sprain" in packet.lower()
    assert "RenewRight organizes evidence. MassHealth makes all eligibility determinations." in packet
    assert "<script" not in packet.lower()
    assert "&lt;" in packet  # injected source markup/instructions render as text when present


def test_packet_includes_clinician_statement_for_exempt_persona() -> None:
    from pathlib import Path

    from app.data import load_demo_data
    from app.state import build_member_view, make_llm
    from proofkit.integration.packet import build_packet_html

    root = Path(__file__).resolve().parents[2]
    data = load_demo_data(root)
    llm, _ = make_llm(live=False, data=data)
    view = build_member_view("SYN-0001", data, llm, root / "config/frailty_rules.json",
                             root / "config/wallet_rules.json")
    packet = build_packet_html(view.member, view.status, view.findings)
    assert "Clinician statement" in packet
    assert "reviewed and signed by a licensed clinician" in packet
