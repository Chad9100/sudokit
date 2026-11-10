"""Grid geometry, parsing and formatting.

A grid is a list of 81 ints in row-major order; 0 means an empty cell.
"""

from __future__ import annotations

from typing import Iterable, Sequence

ROWS = [[r * 9 + c for c in range(9)] for r in range(9)]
COLS = [[r * 9 + c for r in range(9)] for c in range(9)]
BOXES = [
    [(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)]
    for br in range(3)
    for bc in range(3)
]
#: All 27 units, boxes first (the order a person usually scans them in).
UNITS = BOXES + ROWS + COLS
UNIT_NAMES = (
    [f"box {i + 1}" for i in range(9)]
    + [f"row {i + 1}" for i in range(9)]
    + [f"column {i + 1}" for i in range(9)]
)


def row_of(cell: int) -> int:
    return cell // 9


def col_of(cell: int) -> int:
    return cell % 9


def box_of(cell: int) -> int:
    return (cell // 27) * 3 + (cell % 9) // 3


PEERS: list[frozenset[int]] = [
    frozenset(ROWS[row_of(i)] + COLS[col_of(i)] + BOXES[box_of(i)]) - {i}
    for i in range(81)
]
#: Peers as tuples, for fast iteration in the solvers.
PEER_LIST: list[tuple[int, ...]] = [tuple(sorted(p)) for p in PEERS]

EMPTY_CHARS = "0._"
IGNORED_CHARS = "|-+=:"


class PuzzleFormatError(ValueError):
    """The text could not be read as a Sudoku grid."""


def cell_name(cell: int) -> str:
    """``r3c5`` style name (1-based) for a cell index."""
    return f"r{row_of(cell) + 1}c{col_of(cell) + 1}"


def cell_names(cells: Iterable[int]) -> str:
    return ", ".join(cell_name(c) for c in sorted(cells))


def _content_lines(text: str) -> list[tuple[int, str]]:
    text = text.lstrip("﻿")
    lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append((number, stripped))
    return lines


def parse(text: str) -> list[int]:
    """Read one grid from text.

    Digits 1-9 are givens; ``0``, ``.`` and ``_`` are empty cells. Whitespace,
    the border characters ``| - + = :`` and lines starting with ``#`` are
    ignored, so both an 81-character line and a drawn 9x9 grid work.
    """
    cells: list[int] = []
    for number, line in _content_lines(text):
        for ch in line:
            if ch in "123456789":
                cells.append(int(ch))
            elif ch in EMPTY_CHARS:
                cells.append(0)
            elif ch.isspace() or ch in IGNORED_CHARS:
                continue
            else:
                raise PuzzleFormatError(f"unexpected character {ch!r} on line {number}")
    if len(cells) != 81:
        raise PuzzleFormatError(f"expected 81 cells, found {len(cells)}")
    return cells


def parse_many(text: str) -> list[list[int]]:
    """Read one grid, or several when every content line is an 81-char puzzle."""
    lines = _content_lines(text)
    if len(lines) > 1 and all(len(line) == 81 for _, line in lines):
        puzzles = []
        for number, line in lines:
            try:
                puzzles.append(parse(line))
            except PuzzleFormatError as exc:
                raise PuzzleFormatError(f"line {number}: {exc}") from None
        return puzzles
    return [parse(text)]


def to_line(cells: Sequence[int]) -> str:
    """81-character form, ``.`` for empty cells."""
    return "".join(str(v) if v else "." for v in cells)


def format_grid(cells: Sequence[int], labels: bool = False) -> str:
    """A drawn 9x9 grid. With ``labels`` rows and columns are numbered.

    The unlabeled form can be read back by :func:`parse`.
    """
    pad = "  " if labels else ""
    rule = pad + "+-------+-------+-------+"
    out = []
    if labels:
        out.append(pad + "  1 2 3   4 5 6   7 8 9")
    for r in range(9):
        if r % 3 == 0:
            out.append(rule)
        parts = []
        for b in range(3):
            chunk = " ".join(str(cells[r * 9 + c]) if cells[r * 9 + c] else "." for c in range(b * 3, b * 3 + 3))
            parts.append(chunk)
        row = "| " + " | ".join(parts) + " |"
        out.append((f"{r + 1} " if labels else "") + row)
    out.append(rule)
    return "\n".join(out)


def find_conflicts(cells: Sequence[int]) -> list[tuple[str, int, list[int]]]:
    """Units where a digit appears more than once: ``(unit name, digit, cells)``."""
    found = []
    for name, unit in zip(UNIT_NAMES, UNITS):
        seen: dict[int, list[int]] = {}
        for cell in unit:
            if cells[cell]:
                seen.setdefault(cells[cell], []).append(cell)
        for digit, where in sorted(seen.items()):
            if len(where) > 1:
                found.append((name, digit, where))
    return found


def clue_count(cells: Sequence[int]) -> int:
    return sum(1 for v in cells if v)
