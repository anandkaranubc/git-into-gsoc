"""Pixel-grid geometry for the git-into-gsoc brand.

Every brand asset is drawn on an integer grid and converted to a single crisp
SVG path (the union outline of the filled cells). No fonts, no raster sources,
no external tools are required to regenerate the SVGs.
"""

from __future__ import annotations

from collections import defaultdict

Cell = tuple[int, int]
Cells = set[Cell]


def rect(x0: int, y0: int, x1: int, y1: int) -> Cells:
    """Inclusive rectangle of cells."""
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def parse(rows: list[str], x0: int = 0, y0: int = 0, on: str = "X#") -> Cells:
    """Parse an ASCII grid (``X`` = filled) into cells, offset by (x0, y0)."""
    cells: Cells = set()
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch in on:
                cells.add((x0 + dx, y0 + dy))
    return cells


def translate(cells: Cells, dx: int, dy: int) -> Cells:
    return {(x + dx, y + dy) for x, y in cells}


def bounds(cells: Cells) -> tuple[int, int, int, int]:
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _cell_edges(x: int, y: int) -> list[tuple[Cell, Cell]]:
    return [
        ((x, y), (x + 1, y)),
        ((x + 1, y), (x + 1, y + 1)),
        ((x + 1, y + 1), (x, y + 1)),
        ((x, y + 1), (x, y)),
    ]


def _fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s or "0"


def outline(cells: Cells) -> list[list[Cell]]:
    """Trace ``cells`` into closed loops of corner points (axis-aligned polygons).

    Shared edges between neighbouring cells cancel out, leaving only the
    boundary. Loops are walked with a clockwise preference so diagonally
    touching shapes stay separate. Holes come out counter-clockwise, which the
    nonzero fill rule handles in both SVG and TrueType.
    """
    edges: set[tuple[Cell, Cell]] = set()
    for x, y in cells:
        for a, b in _cell_edges(x, y):
            if (b, a) in edges:
                edges.remove((b, a))
            else:
                edges.add((a, b))

    out: dict[Cell, list[Cell]] = defaultdict(list)
    for a, b in edges:
        out[a].append(b)
    remaining = set(edges)
    loops: list[list[Cell]] = []

    def pick(d_in: Cell, cur: Cell, cands: list[Cell]) -> Cell:
        dx, dy = d_in
        for d in ((-dy, dx), (dx, dy), (dy, -dx)):  # right, straight, left
            nxt = (cur[0] + d[0], cur[1] + d[1])
            if nxt in cands:
                return nxt
        return cands[0]

    while remaining:
        a, b = min(remaining)  # deterministic output
        loop = [a]
        remaining.discard((a, b))
        prev, cur = a, b
        while cur != a:
            loop.append(cur)
            cands = [n for n in out[cur] if (cur, n) in remaining]
            if not cands:
                break
            nxt = (
                pick((cur[0] - prev[0], cur[1] - prev[1]), cur, cands)
                if len(cands) > 1
                else cands[0]
            )
            remaining.discard((cur, nxt))
            prev, cur = cur, nxt
        # drop collinear points
        pts: list[Cell] = []
        n = len(loop)
        for i in range(n):
            p0, p1, p2 = loop[i - 1], loop[i], loop[(i + 1) % n]
            cross = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
            if cross != 0:
                pts.append(p1)
        if len(pts) >= 4:
            loops.append(pts)
    return loops


def to_path(cells: Cells, scale: float = 1.0, ox: float = 0.0, oy: float = 0.0) -> str:
    """Return an SVG path ``d`` string tracing the outline of ``cells``."""
    parts: list[str] = []
    for pts in outline(cells):
        x0, y0 = pts[0]
        d = [f"M{_fmt(ox + x0 * scale)} {_fmt(oy + y0 * scale)}"]
        px = x0
        for x, y in pts[1:]:
            d.append(f"V{_fmt(oy + y * scale)}" if x == px else f"H{_fmt(ox + x * scale)}")
            px = x
        d.append("Z")
        parts.append("".join(d))
    return "".join(parts)


# --- 1-bit dither -----------------------------------------------------------

BAYER_4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]


def dither(x0: int, y0: int, w: int, h: int, level: float) -> Cells:
    """Ordered-dither a rectangle at density ``level`` (0..1) using a 4x4 Bayer matrix."""
    cells: Cells = set()
    threshold = level * 16
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if BAYER_4[y % 4][x % 4] < threshold:
                cells.add((x, y))
    return cells


def dither_ramp(
    x0: int, y0: int, w: int, h: int, start: float, end: float, axis: str = "x"
) -> Cells:
    """A dithered gradient from density ``start`` to ``end`` along ``axis``."""
    cells: Cells = set()
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            t = (x - x0) / max(w - 1, 1) if axis == "x" else (y - y0) / max(h - 1, 1)
            level = start + (end - start) * t
            if BAYER_4[y % 4][x % 4] < level * 16:
                cells.add((x, y))
    return cells
