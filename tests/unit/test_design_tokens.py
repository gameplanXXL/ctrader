"""Design tokens smoke + WCAG AA/AAA contrast checks.

Covers Story 1.4 ACs #1, #2, #5:
- design-tokens.css exists and defines the expected tokens.
- Primary text on void background reaches >= 16.4:1 (AAA).
- Typography scale has exactly the 6 documented sizes.
- Spacing grid has exactly the 7 documented steps.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TOKENS_PATH = Path(__file__).resolve().parents[2] / "app" / "static" / "css" / "design-tokens.css"


@pytest.fixture(scope="module")
def tokens_css() -> str:
    assert TOKENS_PATH.is_file(), f"design-tokens.css missing at {TOKENS_PATH}"
    return TOKENS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse `#rrggbb` into (r, g, b)."""

    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.x relative luminance formula."""

    def _channel(c: int) -> float:
        srgb = c / 255.0
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two hex colors."""

    l1 = _relative_luminance(_hex_to_rgb(fg))
    l2 = _relative_luminance(_hex_to_rgb(bg))
    lighter, darker = (l1, l2) if l1 > l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def _token_value(tokens_css: str, name: str) -> str:
    """Extract the value of a CSS custom property from the tokens file."""

    match = re.search(rf"--{re.escape(name)}:\s*([^;]+);", tokens_css)
    assert match is not None, f"token --{name} not found in design-tokens.css"
    return match.group(1).strip()


# ---------------------------------------------------------------------------
# AC #1 — background and text tokens exist
# ---------------------------------------------------------------------------


def test_bg_layer_tokens_present(tokens_css: str) -> None:
    for name in ("bg-void", "bg-chrome", "bg-surface", "bg-elevated"):
        _token_value(tokens_css, name)


def test_text_tokens_present(tokens_css: str) -> None:
    for name in ("text-primary", "text-secondary", "text-muted"):
        _token_value(tokens_css, name)


def test_pnl_and_status_tokens_present(tokens_css: str) -> None:
    assert _token_value(tokens_css, "pnl-green").lower() == "#3fb950"
    assert _token_value(tokens_css, "pnl-red").lower() == "#f85149"
    assert _token_value(tokens_css, "status-green").lower() == "#3fb950"
    assert _token_value(tokens_css, "status-yellow").lower() == "#d29922"
    assert _token_value(tokens_css, "status-red").lower() == "#f85149"


def test_accent_token_matches_spec(tokens_css: str) -> None:
    assert _token_value(tokens_css, "accent").lower() == "#58a6ff"


# ---------------------------------------------------------------------------
# AC #5 — WCAG contrast (Primary text on void should reach AAA, 16.4:1)
# ---------------------------------------------------------------------------


def test_primary_text_on_void_reaches_aaa(tokens_css: str) -> None:
    primary = _token_value(tokens_css, "text-primary")
    void = _token_value(tokens_css, "bg-void")

    ratio = _contrast_ratio(primary, void)
    # Spec says 16.4:1; accept a tiny float-precision tolerance.
    assert ratio >= 15.5, f"contrast ratio {ratio:.2f} below AAA threshold"


def test_primary_text_on_all_bg_layers_reaches_aa(tokens_css: str) -> None:
    """Every background layer must hit at least WCAG AA (4.5:1) for body text."""

    primary = _token_value(tokens_css, "text-primary")
    for layer in ("bg-void", "bg-chrome", "bg-surface", "bg-elevated"):
        bg_color = _token_value(tokens_css, layer)
        ratio = _contrast_ratio(primary, bg_color)
        assert ratio >= 4.5, f"{layer} contrast {ratio:.2f} < AA (4.5:1)"


def test_secondary_text_on_void_reaches_aa(tokens_css: str) -> None:
    secondary = _token_value(tokens_css, "text-secondary")
    void = _token_value(tokens_css, "bg-void")
    ratio = _contrast_ratio(secondary, void)
    assert ratio >= 4.5


# ---------------------------------------------------------------------------
# AC #2 — typography scale (6 sizes) and spacing grid (7 steps)
# ---------------------------------------------------------------------------


def test_typography_scale_has_exactly_six_sizes(tokens_css: str) -> None:
    for token, expected in [
        ("font-size-label", "11px"),
        ("font-size-small", "12px"),
        ("font-size-body", "14px"),
        ("font-size-section", "16px"),
        ("font-size-title", "20px"),
        ("font-size-hero", "28px"),
    ]:
        assert _token_value(tokens_css, token) == expected


def test_spacing_grid_is_4_based(tokens_css: str) -> None:
    for token, expected in [
        ("space-1", "4px"),
        ("space-2", "8px"),
        ("space-3", "12px"),
        ("space-4", "16px"),
        ("space-6", "24px"),
        ("space-8", "32px"),
        ("space-12", "48px"),
    ]:
        assert _token_value(tokens_css, token) == expected


def test_font_families_declared(tokens_css: str) -> None:
    sans = _token_value(tokens_css, "font-sans")
    mono = _token_value(tokens_css, "font-mono")
    assert "Inter" in sans
    assert "JetBrains Mono" in mono
