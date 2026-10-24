"""Pure WCAG color contrast helpers."""
from __future__ import annotations


def _rgb(color: str) -> tuple[int, int, int]:
    if len(color) != 7 or not color.startswith("#"):
        raise ValueError("color must use #RRGGBB")
    try:
        return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError("color must use #RRGGBB") from exc


def relative_luminance(color: str) -> float:
    """Return WCAG relative luminance for a #RRGGBB color."""
    channels = []
    for raw in _rgb(color):
        value = raw / 255
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two #RRGGBB colors."""
    lighter, darker = sorted((relative_luminance(foreground), relative_luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
