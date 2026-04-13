"""Server-side SVG sparkline generator (Story 4.2 / UX-DR14).

Takes a sequence of floats and returns an inline SVG path that the
hero block renders beneath each metric card. Pure string output — no
third-party dep, no JS runtime required.

The sparkline's job is to show trend shape, not exact values, so
everything is normalized into a fixed 120×24 viewbox. A flat series
renders as a single horizontal line at the midline.
"""

from __future__ import annotations

from collections.abc import Iterable

_DEFAULT_WIDTH = 120
_DEFAULT_HEIGHT = 24


def render_sparkline_svg(
    points: Iterable[float],
    *,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
    stroke: str = "currentColor",
    aria_label: str = "Trendverlauf",
) -> str:
    """Return a single `<svg>` string, ready to inline in a template.

    `points` is the raw numeric series (e.g., cumulative P&L). The
    output is normalized to the SVG viewbox, with the first point
    pinned left and the last pinned right.
    """

    series = [float(p) for p in points]

    if len(series) < 2:
        # Flat baseline for empty / single-point series.
        mid = height / 2
        path = f"M 0 {mid:.1f} L {width} {mid:.1f}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img" aria-label="{aria_label}">'
            f'<path d="{path}" stroke="{stroke}" stroke-width="1.2" fill="none" '
            f'stroke-linecap="round"/>'
            f"</svg>"
        )

    lo = min(series)
    hi = max(series)
    span = hi - lo
    if span == 0:
        # Constant series → flat line in the middle.
        mid = height / 2
        path = f"M 0 {mid:.1f} L {width} {mid:.1f}"
    else:
        step = width / (len(series) - 1)
        usable_h = height - 4  # 2px padding top+bottom
        coords: list[str] = []
        for i, value in enumerate(series):
            x = i * step
            # Flip Y so higher values render higher on the page.
            y = 2 + (1 - (value - lo) / span) * usable_h
            coords.append(f"{x:.1f} {y:.1f}")
        path = "M " + " L ".join(coords)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{aria_label}">'
        f'<path d="{path}" stroke="{stroke}" stroke-width="1.4" fill="none" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f"</svg>"
    )
