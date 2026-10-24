"""Buttons take BOTH background and text colour from RenewRight's theme tokens.

Streamlit colours buttons from the browser's light/dark setting, while the app's chosen theme colours text. When
they disagree (browser light + app Dark, or the reverse) secondary buttons became white-on-white or dark-on-dark,
e.g. the Coverage Coach suggested questions. The theme must set both, from one token set."""
import re

import pytest

from app.theme import build_css


@pytest.mark.parametrize("theme", ["system", "light", "dark"])
def test_secondary_buttons_get_background_and_text_from_the_theme(theme):
    css = build_css(theme, large_text=False, comfortable=False, reduce_motion=False)
    rule = re.search(r'button\[kind="secondary"\][^{]*\{([^}]*)\}', css)
    assert rule, "no rule for secondary buttons"
    body = rule.group(1)
    assert "background:var(--pk-surface)" in body and "color:var(--pk-text)" in body
    assert "border:1px solid var(--pk-border)" in body


def test_button_labels_inherit_the_button_colour():
    css = build_css("dark", large_text=False, comfortable=False, reduce_motion=False)
    assert re.search(r'button\[kind="secondary"\] p[^{]*\{[^}]*color:inherit', css)
