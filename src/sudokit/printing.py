"""Plain-text sheets: puzzles first, solutions on separate pages."""

from __future__ import annotations

from typing import Sequence

from .grid import format_grid

FORM_FEED = "\f"


def _page(blocks: list[tuple[str, Sequence[int]]]) -> str:
    parts = []
    for title, cells in blocks:
        parts.append(title + "\n\n" + format_grid(cells))
    return "\n\n\n".join(parts) + "\n"


def _pages(items: list[tuple[str, Sequence[int]]], per_page: int) -> list[str]:
    return [_page(items[i:i + per_page]) for i in range(0, len(items), per_page)]


def build_sheet(
    puzzles: Sequence[Sequence[int]],
    solutions: Sequence[Sequence[int]],
    labels: Sequence[str] | None = None,
    per_page: int = 2,
) -> str:
    """Puzzle pages, then solution pages, separated by form feeds.

    A form feed (``\\f``) starts every new page, so a printer breaks the page
    there. Puzzle ``n`` is titled ``Puzzle n`` (plus its label, if any) and
    its solution ``Solution n``.
    """
    if per_page < 1:
        raise ValueError("per_page must be at least 1")
    labels = labels or [""] * len(puzzles)
    front = [(f"Puzzle {n}" + (f" ({lab})" if lab else ""), p)
             for n, (p, lab) in enumerate(zip(puzzles, labels), start=1)]
    back = [(f"Solution {n}", s) for n, s in enumerate(solutions, start=1)]
    return FORM_FEED.join(_pages(front, per_page) + _pages(back, per_page))
