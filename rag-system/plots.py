"""
Draw the figures for Kapitel 4 as SVG.

Written by hand rather than with matplotlib: no dependency to install, and SVG
places cleanly into Word at any size without going blurry.
"""

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

W, H = 660, 380
PAD_L, PAD_R, PAD_T, PAD_B = 70, 150, 30, 55
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B

SERIES_COLOURS = ["#1f4e79", "#c0504d", "#4f8a10", "#7b4397"]


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _x(i: int, n: int) -> float:
    return PAD_L + (PLOT_W * i / (n - 1) if n > 1 else PLOT_W / 2)


def _y(value: float, top: float) -> float:
    return PAD_T + PLOT_H * (1 - (value / top if top else 0))


def line_chart(
    title: str,
    x_labels: Sequence[str],
    series: List[Tuple[str, Sequence[float]]],
    y_label: str,
    y_max: float = None,
    percent: bool = False,
) -> str:
    """Render a line chart with one line per series."""
    n = len(x_labels)
    top = y_max if y_max is not None else max(
        [v for _, values in series for v in values] + [1e-9]
    ) * 1.15

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        f'<text x="{PAD_L}" y="20" font-size="14" font-weight="bold" '
        f'fill="#222">{_esc(title)}</text>',
    ]

    # Horizontal gridlines with value labels.
    for step in range(5):
        value = top * step / 4
        y = _y(value, top)
        parts.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + PLOT_W}" y2="{y:.1f}" '
            f'stroke="#e3e3e3" stroke-width="1"/>'
        )
        label = f"{value * 100:.0f}%" if percent else f"{value:.0f}"
        parts.append(
            f'<text x="{PAD_L - 8}" y="{y + 4:.1f}" font-size="10" fill="#666" '
            f'text-anchor="end">{label}</text>'
        )

    # Axes.
    parts.append(
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + PLOT_H}" '
        f'stroke="#444" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{PAD_L}" y1="{PAD_T + PLOT_H}" x2="{PAD_L + PLOT_W}" '
        f'y2="{PAD_T + PLOT_H}" stroke="#444" stroke-width="1.5"/>'
    )

    for i, label in enumerate(x_labels):
        parts.append(
            f'<text x="{_x(i, n):.1f}" y="{PAD_T + PLOT_H + 18}" font-size="10" '
            f'fill="#444" text-anchor="middle">{_esc(str(label))}</text>'
        )
    parts.append(
        f'<text x="{PAD_L + PLOT_W / 2:.1f}" y="{H - 14}" font-size="11" fill="#444" '
        f'text-anchor="middle">Dokumente in der Wissensbasis</text>'
    )
    parts.append(
        f'<text x="16" y="{PAD_T + PLOT_H / 2:.1f}" font-size="11" fill="#444" '
        f'text-anchor="middle" transform="rotate(-90 16 {PAD_T + PLOT_H / 2:.1f})">'
        f'{_esc(y_label)}</text>'
    )

    for idx, (name, values) in enumerate(series):
        colour = SERIES_COLOURS[idx % len(SERIES_COLOURS)]
        points = " ".join(
            f"{_x(i, n):.1f},{_y(v, top):.1f}" for i, v in enumerate(values)
        )
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{colour}" stroke-width="2.5"/>'
        )
        for i, v in enumerate(values):
            parts.append(
                f'<circle cx="{_x(i, n):.1f}" cy="{_y(v, top):.1f}" r="4" fill="{colour}"/>'
            )
        legend_y = PAD_T + 14 + idx * 20
        parts.append(
            f'<line x1="{PAD_L + PLOT_W + 16}" y1="{legend_y}" '
            f'x2="{PAD_L + PLOT_W + 40}" y2="{legend_y}" stroke="{colour}" stroke-width="2.5"/>'
        )
        parts.append(
            f'<text x="{PAD_L + PLOT_W + 46}" y="{legend_y + 4}" font-size="10" '
            f'fill="#333">{_esc(name)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def write_figures(rows: List[Dict], out_dir: str = "measurements/figures") -> List[str]:
    """Produce the standard figure set from measurement rows."""
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    modes = sorted({r["noise_mode"] for r in rows})
    levels = sorted({r["noise_level"] for r in rows})
    written = []

    hit_series = []
    for mode in modes:
        values = []
        for level in levels:
            subset = [r for r in rows if r["noise_mode"] == mode and r["noise_level"] == level]
            values.append(sum(r["hit"] for r in subset) / len(subset) if subset else 0.0)
        hit_series.append((mode, values))

    path = target / "abb_trefferquote.svg"
    path.write_text(
        line_chart(
            "Trefferquote des Abrufs nach Dokumentenmenge",
            [str(l) for l in levels], hit_series,
            "Trefferquote", y_max=1.0, percent=True,
        ),
        encoding="utf-8",
    )
    written.append(str(path))

    time_series = []
    for mode in modes:
        values = []
        for level in levels:
            subset = [r for r in rows if r["noise_mode"] == mode and r["noise_level"] == level]
            values.append(
                sum(r["retrieval_time_ms"] for r in subset) / len(subset) if subset else 0.0
            )
        time_series.append((mode, values))

    path = target / "abb_suchzeit.svg"
    path.write_text(
        line_chart(
            "Suchzeit nach Korpusgroesse",
            [str(l) for l in levels], time_series, "Millisekunden",
        ),
        encoding="utf-8",
    )
    written.append(str(path))

    return written
