"""Build every git-into-gsoc brand asset from the pixel definitions.

    python -m scripts.brand.build            # SVGs, tokens, font (if fontTools is installed)
    python -m scripts.brand.build --raster   # also PNG/ICO via rsvg-convert + ImageMagick

Everything is generated from ``glyphs.py`` (typeface + icons) and the mark
geometry below, so the whole identity can be regenerated, tweaked on the grid,
and diffed in git. Output goes to ``brand/``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from scripts.brand.glyphs import (
    ASCENT,
    DESCENT,
    GLYPHS,
    ICONS,
    SPACE,
    TRACK,
    XHEIGHT,
    glyph_width,
    icon,
    text,
)
from scripts.brand.pixel import Cells, dither_ramp, outline, rect, to_path, translate

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "brand"

# --- colour tokens -----------------------------------------------------------

COLORS = {
    "ink": "#15121E",  # near-black aubergine. Dark surfaces, text on paper.
    "ink-2": "#211C2E",  # raised surfaces on ink
    "ink-3": "#332C47",  # borders on ink
    "paper": "#F4F1FA",  # lavender-tinted off-white. Light surfaces, text on ink.
    "paper-2": "#E9E4F4",  # raised surfaces on paper
    "paper-3": "#CFC7E3",  # borders on paper
    "merge": "#7A5AF8",  # violet. The G. Fills, large text, links on ink.
    "merge-deep": "#4C2FD9",  # violet for body text and links on paper
    "merge-soft": "#C2B5FF",  # violet tint for text on ink
    "open": "#C6F432",  # lime. The cursor. Accents on ink only.
    "open-deep": "#3F6A00",  # lime for text on paper
    "mute": "#67607A",  # secondary text on paper
    "mute-on-ink": "#A49DB4",  # secondary text on ink
    "warn": "#FFB224",  # amber, semantic only
    "danger": "#FF6A4D",  # coral, semantic only
}

INK, PAPER, MERGE, OPEN = COLORS["ink"], COLORS["paper"], COLORS["merge"], COLORS["open"]


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


# --- the mark: a pixel G whose opening is a doorway, and a cursor stepping in --

MARK = 20  # grid units
STROKE = 4


def g_cells() -> Cells:
    n, s = MARK, STROKE
    g: Cells = set()
    g |= rect(0, 0, s - 1, n - 1)  # left stem
    g |= rect(0, 0, n - 1, s - 1)  # top arm
    g |= rect(n - s, s, n - 1, s + 1)  # beak under the top-right corner
    g |= rect(10, n - 2 * s, n - 1, n - s - 1)  # bar (the doormat)
    g |= rect(n - s, n - 2 * s, n - 1, n - 1)  # right lower stem
    g |= rect(0, n - s, n - 1, n - 1)  # bottom arm
    for cx, cy, dx, dy in (
        (0, 0, 1, 1),
        (n - 1, 0, -1, 1),
        (0, n - 1, 1, -1),
        (n - 1, n - 1, -1, -1),
    ):
        g -= {(cx, cy), (cx + dx, cy), (cx, cy + dy)}  # rounded pixel corners
    g |= {(s, s), (s, n - s - 1)}  # soften the inner counter corners
    return g


G_CELLS = g_cells()
CURSOR = rect(18, 7, 20, 10)  # 3x4, one step through the doorway
MARK_W, MARK_H = 21, 20


# --- svg helpers -------------------------------------------------------------


def svg(w: float, h: float, body: str, title: str, size: int | None = None, extra: str = "") -> str:
    wh = f' width="{size}" height="{round(size * h / w)}"' if size else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"{wh} role="img" '
        f'aria-label="{title}"{extra}>\n<title>{title}</title>\n{body}\n</svg>\n'
    )


def path(
    cells: Cells, fill: str, scale: float = 1, ox: float = 0, oy: float = 0, attrs: str = ""
) -> str:
    return f'<path d="{to_path(cells, scale, ox, oy)}" fill="{fill}"{attrs}/>'


BLINK = (
    '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" '
    'dur="1.1s" repeatCount="indefinite" calcMode="discrete"/>'
)


def mark_body(
    gcol: str, ccol: str, scale: float = 1, ox: float = 0, oy: float = 0, blink: bool = False
) -> str:
    g = path(G_CELLS, gcol, scale, ox, oy)
    if blink:
        c = f'<path d="{to_path(CURSOR, scale, ox, oy)}" fill="{ccol}">{BLINK}</path>'
    else:
        c = path(CURSOR, ccol, scale, ox, oy)
    return g + c


def wordmark_cells(s: str = "git into gsoc") -> tuple[Cells, int, int]:
    """Cells for a line of Gig Pixel text, normalised so the top-left is (0, 0)."""
    cells, w = text(s)
    return translate(cells, 0, ASCENT), w, ASCENT + XHEIGHT + DESCENT


def tittles(s: str = "git into gsoc") -> Cells:
    """The dots of the i's: tiny cursors. Used as the colour accent in lockups."""
    cells: Cells = set()
    x = 0
    for ch in s:
        if ch == " ":
            x += SPACE
            continue
        if ch == "i":
            cells |= rect(x, 0, x + 1, 1)  # rows -3..-2 before normalisation
        x += glyph_width(ch) + TRACK
    return cells


# --- assets ------------------------------------------------------------------

SCHEMES = {
    # name: (g colour, cursor colour, wordmark colour, background)
    "light": (MERGE, INK, INK, None),
    "dark": (MERGE, OPEN, PAPER, None),
    "mono-ink": (INK, INK, INK, None),
    "mono-paper": (PAPER, PAPER, PAPER, None),
}


def build_marks(out: Path) -> None:
    d = out / "logo"
    d.mkdir(parents=True, exist_ok=True)
    pad = 2  # canvas 25x24 → keep square 24x24 with the cursor poking to x=23
    for name, (gcol, ccol, _, _) in SCHEMES.items():
        body = mark_body(gcol, ccol, 1, pad - 1, pad)
        (d / f"mark-{name}.svg").write_text(svg(24, 24, body, "git-into-gsoc mark", 256))
    # tile: ink rounded square, universal (works on any background, avatar-ready)
    tile = f'<rect width="24" height="24" rx="4.5" fill="{INK}"/>' + mark_body(MERGE, OPEN, 1, 1, 2)
    (d / "mark-tile.svg").write_text(svg(24, 24, tile, "git-into-gsoc mark on tile", 256))
    tile_blink = f'<rect width="24" height="24" rx="4.5" fill="{INK}"/>' + mark_body(
        MERGE, OPEN, 1, 1, 2, blink=True
    )
    (d / "mark-tile-animated.svg").write_text(
        svg(24, 24, tile_blink, "git-into-gsoc mark, blinking", 256)
    )
    # violet tile (merch / social alt)
    tile_v = f'<rect width="24" height="24" rx="4.5" fill="{MERGE}"/>' + mark_body(
        INK, OPEN, 1, 1, 2
    )
    (d / "mark-tile-violet.svg").write_text(
        svg(24, 24, tile_v, "git-into-gsoc mark on violet tile", 256)
    )


def build_wordmarks(out: Path) -> None:
    d = out / "logo"
    cells, w, h = wordmark_cells()
    dots = tittles()
    pad = 1
    for name, color in (("ink", INK), ("paper", PAPER), ("merge", MERGE)):
        body = path(cells, color, 1, pad, pad)
        (d / f"wordmark-{name}.svg").write_text(
            svg(w + 2 * pad, h + 2 * pad, body, "git into gsoc", 640)
        )
    # accent versions: the dots of the i's are cursors
    for name, color, dot in (("light", INK, MERGE), ("dark", PAPER, OPEN)):
        body = path(cells - dots, color, 1, pad, pad) + path(dots, dot, 1, pad, pad)
        (d / f"wordmark-{name}.svg").write_text(
            svg(w + 2 * pad, h + 2 * pad, body, "git into gsoc", 640)
        )


def lockup_h(
    gcol: str, ccol: str, wcol: str, dot: str, blink: bool = False
) -> tuple[str, int, int]:
    cells, w, h = wordmark_cells()
    dots = translate(tittles(), 0, 0)
    gap = 6
    W, H = MARK_W + gap + w, MARK_H
    # wordmark: x-height block centred on the mark's optical centre
    wy = (MARK_H - h) // 2 + 1
    body = mark_body(gcol, ccol, 1, 0, 0, blink)
    body += path(cells - dots, wcol, 1, MARK_W + gap, wy) + path(dots, dot, 1, MARK_W + gap, wy)
    return body, W, H


def lockup_v(
    gcol: str, ccol: str, wcol: str, dot: str, blink: bool = False
) -> tuple[str, int, int]:
    cells, w, h = wordmark_cells()
    dots = tittles()
    gap = 5
    W = max(w, MARK_W)
    H = MARK_H + gap + h
    mx = (W - MARK_W) // 2
    body = mark_body(gcol, ccol, 1, mx, 0, blink)
    wx = (W - w) // 2
    body += path(cells - dots, wcol, 1, wx, MARK_H + gap) + path(dots, dot, 1, wx, MARK_H + gap)
    return body, W, H


def build_lockups(out: Path) -> None:
    d = out / "logo"
    combos = {
        "light": (MERGE, INK, INK, MERGE),
        "dark": (MERGE, OPEN, PAPER, OPEN),
        "mono-ink": (INK, INK, INK, INK),
        "mono-paper": (PAPER, PAPER, PAPER, PAPER),
    }
    pad = 2
    for name, (g, c, wcol, dot) in combos.items():
        body, W, H = lockup_h(g, c, wcol, dot)
        (d / f"lockup-horizontal-{name}.svg").write_text(
            svg(
                W + 2 * pad,
                H + 2 * pad,
                f'<g transform="translate({pad},{pad})">{body}</g>',
                "git into gsoc",
                720,
            )
        )
        body, W, H = lockup_v(g, c, wcol, dot)
        (d / f"lockup-stacked-{name}.svg").write_text(
            svg(
                W + 2 * pad,
                H + 2 * pad,
                f'<g transform="translate({pad},{pad})">{body}</g>',
                "git into gsoc",
                480,
            )
        )


def build_favicons(out: Path) -> None:
    d = out / "favicon"
    d.mkdir(parents=True, exist_ok=True)
    # The tile mark on a 24-unit canvas. Browsers scale it; the ink tile keeps contrast in any tab bar.
    tile = f'<rect width="24" height="24" rx="5" fill="{INK}"/>' + mark_body(MERGE, OPEN, 1, 1, 2)
    (d / "favicon.svg").write_text(svg(24, 24, tile, "git-into-gsoc", 64))
    # Hand-tuned 16px version: a 10-unit G with a 2-unit stroke so it stays sharp at 1x.
    small_g = (
        rect(0, 0, 1, 9)
        | rect(0, 0, 9, 1)
        | rect(8, 2, 9, 2)
        | rect(5, 5, 9, 6)
        | rect(8, 5, 9, 9)
        | rect(0, 8, 9, 9)
    )
    small_g -= {(0, 0), (9, 0), (0, 9), (9, 9)}
    small_cursor = rect(9, 3, 10, 4) | rect(10, 3, 10, 4)
    body = (
        f'<rect width="16" height="16" rx="3" fill="{INK}"/>'
        + path(small_g, MERGE, 1, 2, 3)
        + path(small_cursor, OPEN, 1, 2, 3)
    )
    (d / "favicon-16.svg").write_text(svg(16, 16, body, "git-into-gsoc", 16))
    # Maskable / app icon: more padding, no rounded corners (the OS masks it)
    app = f'<rect width="24" height="24" fill="{INK}"/>' + mark_body(MERGE, OPEN, 0.8, 3.6, 4)
    (d / "app-icon.svg").write_text(svg(24, 24, app, "git-into-gsoc", 512))


def build_avatar(out: Path) -> None:
    d = out / "avatar"
    d.mkdir(parents=True, exist_ok=True)
    # GitHub crops avatars to a circle: keep the mark inside the inner 70%.
    body = f'<rect width="32" height="32" fill="{INK}"/>' + mark_body(MERGE, OPEN, 1, 5, 6)
    (d / "avatar.svg").write_text(svg(32, 32, body, "git-into-gsoc avatar", 512))
    body = f'<rect width="32" height="32" fill="{MERGE}"/>' + mark_body(INK, OPEN, 1, 5, 6)
    (d / "avatar-violet.svg").write_text(svg(32, 32, body, "git-into-gsoc avatar, violet", 512))


def text_block(s: str, color: str, scale: float, x: float, y: float, dot: str | None = None) -> str:
    cells, _ = text(s)
    if dot:
        dots = tittles(s)
        return path(cells - dots, color, scale, x, y) + path(dots, dot, scale, x, y)
    return path(cells, color, scale, x, y)


def fit_scale(s: str, max_px: float, scale: float) -> float:
    """Shrink ``scale`` until ``s`` fits in ``max_px``."""
    _, w = text(s)
    return min(scale, max_px / w)


def build_social(out: Path) -> None:
    d = out / "social"
    d.mkdir(parents=True, exist_ok=True)
    W, H = 1280, 640
    u = 8  # px per grid unit
    body = [f'<rect width="{W}" height="{H}" fill="{INK}"/>']
    # dithered violet horizon along the bottom: the light under the door
    ramp = dither_ramp(0, 0, W // u, 9, 0.0, 0.5, axis="y")
    body.append(path(ramp, MERGE, u, 0, H - 9 * u))
    body.append(mark_body(MERGE, OPEN, 14, 96, 104))
    body.append(text_block("git into gsoc", PAPER, 9, 420, 150, dot=OPEN))
    body.append(text_block("open source has a door.", COLORS["mute-on-ink"], 4.5, 420, 310))
    body.append(text_block("git in.", OPEN, 4.5, 420, 372))
    for i, line in enumerate(
        ("the right org. the right issue.", "one real contribution before applications open.")
    ):
        body.append(
            text_block(
                line, COLORS["mute-on-ink"], fit_scale(line, W - 420 - 60, 2.5), 420, 452 + i * 40
            )
        )
    (d / "social-preview.svg").write_text(
        svg(W, H, "".join(body), "git into gsoc: open source has a door. git in.")
    )


def build_readme_banners(out: Path) -> None:
    d = out / "readme"
    d.mkdir(parents=True, exist_ok=True)
    W, H = 1200, 260
    for name, (g, c, wcol, dot, mute) in {
        "light": (MERGE, INK, INK, MERGE, COLORS["mute"]),
        "dark": (MERGE, OPEN, PAPER, OPEN, COLORS["mute-on-ink"]),
    }.items():
        u = 8
        body = [mark_body(g, c, u, 24, 30, blink=True)]
        body.append(text_block("git into gsoc", wcol, 7, 230, 56, dot=dot))
        body.append(text_block("open source has a door. git in.", mute, 3, 230, 176))
        (d / f"banner-{name}.svg").write_text(
            svg(W, H, "".join(body), "git into gsoc. open source has a door. git in.")
        )
    # compact header for docs pages (no tagline)
    for name, (g, c, wcol, dot) in {
        "light": (MERGE, INK, INK, MERGE),
        "dark": (MERGE, OPEN, PAPER, OPEN),
    }.items():
        hbody, lw, lh = lockup_h(g, c, wcol, dot, blink=True)
        (d / f"header-{name}.svg").write_text(
            svg(lw + 4, lh + 4, f'<g transform="translate(2,2)">{hbody}</g>', "git into gsoc", 360)
        )


def build_icons(out: Path) -> None:
    d = out / "icons"
    d.mkdir(parents=True, exist_ok=True)
    for name in ICONS:
        cells = icon(name)
        for scheme, color in (("ink", INK), ("paper", PAPER), ("merge", MERGE)):
            (d / f"{name}-{scheme}.svg").write_text(
                svg(12, 12, path(cells, color), name.replace("_", " "), 48)
            )
    # sprite sheet for the docs
    cols = 8
    body = []
    for i, name in enumerate(ICONS):
        x, y = (i % cols) * 16 + 2, (i // cols) * 16 + 2
        body.append(path(icon(name), INK, 1, x, y))
    rows = (len(ICONS) + cols - 1) // cols
    (d / "sheet-ink.svg").write_text(
        svg(cols * 16, rows * 16, "".join(body), "git-into-gsoc icon set", 512)
    )


def stamp(label: str, line2: str, color: str, angle: float = -7) -> tuple[str, float, int]:
    """A passport-style entry stamp with pixel lettering."""
    s = 4
    _, w1 = text(label)
    _, w2 = text(line2)
    w = max(w1, w2) * s + 56
    h = 120
    inner = (
        f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="12" fill="none" stroke="{color}" stroke-width="5"/>'
        f'<rect x="13" y="13" width="{w - 26}" height="{h - 26}" rx="7" fill="none" stroke="{color}" stroke-width="2"/>'
        + text_block(label, color, s, (w - w1 * s) / 2, 30)
        + text_block(line2, color, 2.5, (w - w2 * 2.5) / 2, 84)
    )
    return f'<g transform="rotate({angle} {w / 2} {h / 2})">{inner}</g>', w, h


STAMPS = [
    ("entered", "open source  2027"),
    ("discovered", "org shortlist  3/5"),
    ("evaluated", "repo health  a"),
    ("first pr", "reviewed + merged"),
    ("merged.", "one real contribution"),
    ("proposed", "before the deadline"),
]


def build_stamps(out: Path) -> None:
    d = out / "stamps"
    d.mkdir(parents=True, exist_ok=True)
    for label, line2 in STAMPS:
        for scheme, color in (("merge", MERGE), ("ink", INK), ("open", OPEN)):
            sbody, sw, sh = stamp(label, line2, color)
            name = label.strip(".").replace(" ", "-")
            (d / f"stamp-{name}-{scheme}.svg").write_text(
                svg(sw, sh, sbody, f"stamp: {label}", int(sw))
            )


def build_stickers(out: Path) -> None:
    d = out / "stickers"
    d.mkdir(parents=True, exist_ok=True)
    # 1. round sticker: tile mark + "git in." ring text is avoided (no curved pixel text); use a badge layout
    body = (
        f'<circle cx="60" cy="60" r="58" fill="{INK}"/><circle cx="60" cy="60" r="54" fill="none" stroke="{MERGE}" stroke-width="2"/>'
        + mark_body(MERGE, OPEN, 2.4, 35, 20)
        + text_block("git in.", PAPER, 1.5, 60 - text("git in.")[1] * 0.75, 76)
    )
    (d / "sticker-git-in.svg").write_text(svg(120, 120, body, "git in."))
    # 2. wide label sticker: "the door is open."
    _, w = text("the door is open.")
    W = w * 3 + 40
    body = f'<rect width="{W}" height="64" rx="12" fill="{OPEN}"/>' + text_block(
        "the door is open.", INK, 3, 20, 14
    )
    (d / "sticker-door-open.svg").write_text(svg(W, 64, body, "the door is open."))
    # 3. "evidence > vibes"
    _, w = text("evidence > vibes")
    W = w * 3 + 40
    body = f'<rect width="{W}" height="64" rx="12" fill="{MERGE}"/>' + text_block(
        "evidence > vibes", PAPER, 3, 20, 14
    )
    (d / "sticker-evidence.svg").write_text(svg(W, 64, body, "evidence > vibes"))
    # 4. "no drive-by prs"
    _, w = text("no drive-by prs")
    W = w * 3 + 40
    body = f'<rect width="{W}" height="64" rx="12" fill="{INK}"/>' + text_block(
        "no drive-by prs", OPEN, 3, 20, 14
    )
    (d / "sticker-no-driveby.svg").write_text(svg(W, 64, body, "no drive-by prs"))
    # 5. "merged." lime square
    body = f'<rect width="120" height="120" rx="20" fill="{OPEN}"/>' + text_block(
        "merged.", INK, 1.75, 60 - text("merged.")[1] * 0.875, 50
    )
    (d / "sticker-merged.svg").write_text(svg(120, 120, body, "merged."))
    # 6. cursor sticker: just the cursor, blinking (die-cut rectangle)
    body = f'<rect width="36" height="48" fill="{OPEN}">{BLINK}</rect>'
    (d / "sticker-cursor.svg").write_text(svg(36, 48, body, "cursor"))


def build_merch(out: Path) -> None:
    d = out / "merch"
    d.mkdir(parents=True, exist_ok=True)
    # Sticker sheet: 4x6.4 inch at 100 px/inch
    W, H = 400, 640
    sheet = [f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']

    def place(svg_body: str, x: float, y: float, scale: float = 1) -> None:
        sheet.append(f'<g transform="translate({x},{y}) scale({scale})">{svg_body}</g>')

    place(
        f'<circle cx="60" cy="60" r="58" fill="{INK}"/>'
        + mark_body(MERGE, OPEN, 2.4, 35, 20)
        + text_block("git in.", PAPER, 1.5, 60 - text("git in.")[1] * 0.75, 76),
        24,
        24,
    )
    place(
        f'<rect width="120" height="120" rx="20" fill="{OPEN}"/>'
        + text_block("merged.", INK, 1.75, 60 - text("merged.")[1] * 0.875, 50),
        160,
        24,
    )
    place(
        f'<rect width="24" height="24" rx="4.5" fill="{INK}"/>' + mark_body(MERGE, OPEN, 1, 1, 2),
        304,
        24,
        3,
    )
    place(f'<rect width="36" height="48" fill="{OPEN}"/>', 322, 108)
    y = 168
    for label, bg, fg in (
        ("the door is open.", OPEN, INK),
        ("evidence > vibes", MERGE, PAPER),
        ("no drive-by prs", INK, OPEN),
    ):
        _, w = text(label)
        place(
            f'<rect width="{w * 3 + 40}" height="64" rx="12" fill="{bg}"/>'
            + text_block(label, fg, 3, 20, 14),
            24,
            y,
            0.9,
        )
        y += 72
    for label, line2 in STAMPS[:3]:
        sb, _, _ = stamp(label, line2, MERGE, angle=-4)
        place(sb, 28, y, 0.45)
        y += 62
    (d / "sticker-sheet.svg").write_text(svg(W, H, "".join(sheet), "git-into-gsoc sticker sheet"))

    # Tee back print: stacked lockup + tagline, print-ready on transparent
    tag = "open source has a door. git in."
    _, tw = text(tag)
    for garment, (g, c, wcol, dot, tcol) in {
        "dark": (MERGE, OPEN, PAPER, OPEN, OPEN),
        "light": (MERGE, INK, INK, MERGE, INK),
    }.items():
        lbody, lw, lh = lockup_v(g, c, wcol, dot)
        W = max(lw * 8, tw * 3) + 80
        parts = [f'<g transform="translate({(W - lw * 8) / 2},40) scale(8)">{lbody}</g>']
        parts.append(text_block(tag, tcol, 3, (W - tw * 3) / 2, lh * 8 + 90))
        (d / f"tee-back-{garment}.svg").write_text(
            svg(W, lh * 8 + 170, "".join(parts), f"tee back print, {garment} garment")
        )
    # Tee front: small tile mark (left chest)
    (d / "tee-front-chest.svg").write_text(
        svg(
            24,
            24,
            f'<rect width="24" height="24" rx="4.5" fill="{INK}"/>'
            + mark_body(MERGE, OPEN, 1, 1, 2),
            "tee chest mark",
            300,
        )
    )


# --- typeface ----------------------------------------------------------------


def build_font(out: Path) -> bool:
    try:
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.ttGlyphPen import TTGlyphPen
    except ImportError:
        print("fontTools not installed; skipping font (pip install fonttools brotli)")
        return False
    d = out / "font"
    d.mkdir(parents=True, exist_ok=True)
    cell = 64  # font units per grid cell → UPM 1024, so a cell is exactly 1/16 em
    upm = 1024
    ascender = (ASCENT + XHEIGHT) * cell  # 704
    descender = -DESCENT * cell  # -192

    names = [".notdef", "space"]
    cmap: dict[int, str] = {0x20: "space", 0xA0: "space"}
    glyph_cells: dict[str, Cells] = {}
    advances: dict[str, int] = {".notdef": 9 * cell, "space": SPACE * cell}
    for ch, (top, rows) in GLYPHS.items():
        if ch == " ":
            continue
        gname = f"uni{ord(ch):04X}"
        names.append(gname)
        cmap[ord(ch)] = gname
        if ch.isalpha() and ch.lower() == ch:
            cmap[ord(ch.upper())] = gname  # uppercase → the same lowercase drawing
        w = max(len(r) for r in rows)
        cells: Cells = set()
        for dy, row in enumerate(rows):
            for dx, c in enumerate(row):
                if c == "X":
                    cells.add((dx, top + dy))
        glyph_cells[gname] = cells
        advances[gname] = (w + TRACK) * cell
    # .notdef: a hollow box
    glyph_cells[".notdef"] = rect(0, -3, 6, 7) - rect(2, -1, 4, 5)

    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    glyf = {}
    for gname in names:
        pen = TTGlyphPen(None)
        for loop in outline(glyph_cells.get(gname, set())):
            # grid y grows downwards; font y grows upwards. Row 0 top = x-height line.
            pts = [(x * cell, (XHEIGHT - y) * cell) for x, y in loop]
            # outline() emits outer loops clockwise in screen space, which is counter-clockwise
            # once y is flipped; TrueType wants clockwise outers, so reverse.
            pts.reverse()
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
        glyf[gname] = pen.glyph()
    fb.setupGlyf(glyf)
    metrics = {g: (advances[g], glyf[g].xMin if hasattr(glyf[g], "xMin") else 0) for g in names}
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ascender + cell, descent=descender - cell)
    fb.setupNameTable(
        {
            "familyName": "Gig Pixel",
            "styleName": "Regular",
            "uniqueFontIdentifier": "GigPixel-Regular;git-into-gsoc",
            "fullName": "Gig Pixel Regular",
            "psName": "GigPixel-Regular",
            "version": "Version 1.000",
            "copyright": "git-into-gsoc contributors. MIT License.",
            "description": "The git-into-gsoc brand typeface: a lowercase pixel face on a 2-cell stroke.",
            "licenseDescription": "MIT License",
        }
    )
    fb.setupOS2(
        sTypoAscender=ascender + cell,
        sTypoDescender=descender - cell,
        sTypoLineGap=0,
        usWinAscent=ascender + cell,
        usWinDescent=-(descender - cell),
        sxHeight=XHEIGHT * cell,
        sCapHeight=(ASCENT + XHEIGHT) * cell,
        achVendID="GIGP",
        fsType=0,
    )
    fb.setupPost()
    fb.save(str(d / "GigPixel.ttf"))
    font = fb.font
    font.flavor = "woff2"
    font.save(str(d / "GigPixel.woff2"))
    # specimen
    lines = [
        "abcdefghijklmnopqrstuvwxyz",
        "0123456789 .,:;!?-_/<>()[]#+='\"*@&%",
        "the quick brown fox jumps over the lazy dog",
        "open source has a door. git in.",
    ]
    body = [f'<rect width="900" height="300" fill="{PAPER}"/>']
    y = 20
    for i, line in enumerate(lines):
        scale = 3 if i < 3 else 4
        body.append(text_block(line, INK, scale, 20, y + 3 * scale))
        y += int(16 * scale) + 8
    (d / "specimen.svg").write_text(svg(900, 300, "".join(body), "Gig Pixel specimen"))
    return True


# --- tokens ------------------------------------------------------------------


def build_tokens(out: Path) -> None:
    css = [
        "/* git-into-gsoc brand tokens. Generated by scripts/brand/build.py; edit COLORS there. */",
        ":root {",
    ]
    for name, hex_value in COLORS.items():
        css.append(f"  --gig-{name}: {hex_value};")
    css += [
        '  --gig-font-pixel: "Gig Pixel", ui-monospace, "SF Mono", Menlo, Consolas, monospace;',
        '  --gig-font-sans: "Instrument Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;',
        '  --gig-font-mono: ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;',
        "  --gig-radius: 6px;",
        "  --gig-radius-lg: 14px;",
        "  --gig-blink: gig-blink 1.1s steps(1, end) infinite;",
        "}",
        "@keyframes gig-blink { 50% { opacity: 0; } }",
        "@media (prefers-reduced-motion: reduce) { :root { --gig-blink: none; } }",
        "",
        "/* Semantic roles. Light is the default; dark flips the roles. */",
        ':root, [data-theme="light"] {',
        "  --bg: var(--gig-paper); --bg-2: var(--gig-paper-2); --line: var(--gig-paper-3);",
        "  --fg: var(--gig-ink); --fg-2: var(--gig-mute);",
        "  --accent: var(--gig-merge); --accent-text: var(--gig-merge-deep);",
        "  --cursor: var(--gig-ink); --open-text: var(--gig-open-deep);",
        "}",
        '@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {',
        "  --bg: var(--gig-ink); --bg-2: var(--gig-ink-2); --line: var(--gig-ink-3);",
        "  --fg: var(--gig-paper); --fg-2: var(--gig-mute-on-ink);",
        "  --accent: var(--gig-merge); --accent-text: var(--gig-merge-soft);",
        "  --cursor: var(--gig-open); --open-text: var(--gig-open);",
        "} }",
        '[data-theme="dark"] {',
        "  --bg: var(--gig-ink); --bg-2: var(--gig-ink-2); --line: var(--gig-ink-3);",
        "  --fg: var(--gig-paper); --fg-2: var(--gig-mute-on-ink);",
        "  --accent: var(--gig-merge); --accent-text: var(--gig-merge-soft);",
        "  --cursor: var(--gig-open); --open-text: var(--gig-open);",
        "}",
        "",
    ]
    (out / "tokens.css").write_text("\n".join(css))
    pairs = {
        "ink on paper": contrast(INK, PAPER),
        "merge-deep on paper": contrast(COLORS["merge-deep"], PAPER),
        "merge on paper (large text only)": contrast(MERGE, PAPER),
        "open-deep on paper": contrast(COLORS["open-deep"], PAPER),
        "mute on paper": contrast(COLORS["mute"], PAPER),
        "paper on ink": contrast(PAPER, INK),
        "merge-soft on ink": contrast(COLORS["merge-soft"], INK),
        "merge on ink (large text only)": contrast(MERGE, INK),
        "open on ink": contrast(OPEN, INK),
        "mute-on-ink on ink": contrast(COLORS["mute-on-ink"], INK),
        "ink on open": contrast(INK, OPEN),
        "paper on merge": contrast(PAPER, MERGE),
        "ink on merge": contrast(INK, MERGE),
    }
    (out / "tokens.json").write_text(
        json.dumps(
            {
                "colors": COLORS,
                "contrast": pairs,
                "type": {
                    "pixel": "Gig Pixel (brand/font). lowercase only; uppercase maps to lowercase.",
                    "sans": "Instrument Sans (Google Fonts) or system-ui",
                    "mono": "system monospace",
                },
                "mark": {"grid": MARK, "stroke": STROKE, "cursor": "3x4 at (18,7)"},
            },
            indent=2,
        )
        + "\n"
    )
    for label, ratio in pairs.items():
        flag = (
            "AAA" if ratio >= 7 else "AA" if ratio >= 4.5 else "AA-large" if ratio >= 3 else "FAIL"
        )
        print(f"  {label:36s} {ratio:5.2f}  {flag}")


# --- raster ------------------------------------------------------------------


def render_png(src: Path, dst: Path, width: int, height: int | None = None) -> bool:
    if not shutil.which("rsvg-convert"):
        return False
    args = ["rsvg-convert", "-w", str(width)]
    if height:
        args += ["-h", str(height)]
    subprocess.run([*args, str(src), "-o", str(dst)], check=True)
    return True


def build_raster(out: Path) -> None:
    jobs = [
        ("favicon/favicon.svg", "favicon/favicon-32.png", 32),
        ("favicon/favicon-16.svg", "favicon/favicon-16.png", 16),
        ("favicon/favicon.svg", "favicon/favicon-48.png", 48),
        ("favicon/favicon.svg", "favicon/apple-touch-icon.png", 180),
        ("favicon/app-icon.svg", "favicon/icon-192.png", 192),
        ("favicon/app-icon.svg", "favicon/icon-512.png", 512),
        ("avatar/avatar.svg", "avatar/avatar-512.png", 512),
        ("avatar/avatar.svg", "avatar/avatar-1024.png", 1024),
        ("social/social-preview.svg", "social/social-preview.png", 1280),
        ("logo/mark-tile.svg", "logo/mark-tile-512.png", 512),
        ("logo/lockup-horizontal-light.svg", "logo/lockup-horizontal-light-1200.png", 1200),
        ("logo/lockup-horizontal-dark.svg", "logo/lockup-horizontal-dark-1200.png", 1200),
        ("merch/sticker-sheet.svg", "merch/sticker-sheet.png", 1600),
        ("font/specimen.svg", "font/specimen.png", 1800),
    ]
    ok = False
    for src, dst, w in jobs:
        if (out / src).exists():
            ok = render_png(out / src, out / dst, w) or ok
    if not ok:
        print("rsvg-convert not found; skipping PNGs")
        return
    if shutil.which("magick"):
        subprocess.run(
            [
                "magick",
                str(out / "favicon/favicon-16.png"),
                str(out / "favicon/favicon-32.png"),
                str(out / "favicon/favicon-48.png"),
                str(out / "favicon/favicon.ico"),
            ],
            check=True,
        )
    else:
        print("ImageMagick not found; skipping favicon.ico")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--raster",
        action="store_true",
        help="also render PNG/ICO (needs rsvg-convert, ImageMagick)",
    )
    ap.add_argument("--no-font", action="store_true")
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    build_marks(out)
    build_wordmarks(out)
    build_lockups(out)
    build_favicons(out)
    build_avatar(out)
    build_social(out)
    build_readme_banners(out)
    build_icons(out)
    build_stamps(out)
    build_stickers(out)
    build_merch(out)
    if not args.no_font:
        build_font(out)
    print("contrast (WCAG):")
    build_tokens(out)
    if args.raster:
        build_raster(out)
    n = sum(1 for _ in out.rglob("*") if _.is_file())
    print(f"wrote {n} files to {out}")


if __name__ == "__main__":
    main()
