"""Human-style solving: one explained step at a time.

Each technique looks at the pencil-mark candidates and either places a digit
or removes candidates, and says why in plain words. Techniques are always
tried from simplest to hardest, so the hardest one a puzzle needs is a fair
measure of its difficulty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Iterator, Sequence

from .grid import (
    BOXES,
    COLS,
    PEERS,
    ROWS,
    UNIT_NAMES,
    UNITS,
    box_of,
    cell_name,
    cell_names,
    col_of,
    find_conflicts,
    row_of,
)
from .solver import ALL, POPCOUNT, digits_of

EASY, MEDIUM, HARD, EXPERT = 1, 2, 3, 4
LEVEL_NAMES = {EASY: "easy", MEDIUM: "medium", HARD: "hard", EXPERT: "expert"}
LEVELS = {name: level for level, name in LEVEL_NAMES.items()}


@dataclass
class Step:
    technique: str
    level: int
    explanation: str
    placements: list[tuple[int, int]] = field(default_factory=list)
    eliminations: list[tuple[int, int]] = field(default_factory=list)


class Board:
    """Values plus candidate bitmasks (0 for filled cells)."""

    def __init__(self, cells: Sequence[int]):
        if len(cells) != 81:
            raise ValueError("a grid has 81 cells")
        if find_conflicts(cells):
            raise ValueError("the grid repeats a digit in a row, column or box")
        self.values = list(cells)
        self.cands = [0] * 81
        for i in range(81):
            if not self.values[i]:
                used = 0
                for p in PEERS[i]:
                    if self.values[p]:
                        used |= 1 << self.values[p]
                self.cands[i] = ALL & ~used

    def solved(self) -> bool:
        return all(self.values)

    def broken(self) -> bool:
        """True if some empty cell has no candidate left."""
        return any(not v and not c for v, c in zip(self.values, self.cands))

    def place(self, cell: int, digit: int) -> None:
        self.values[cell] = digit
        self.cands[cell] = 0
        bit = ~(1 << digit)
        for p in PEERS[cell]:
            self.cands[p] &= bit

    def apply(self, step: Step) -> None:
        for cell, digit in step.placements:
            self.place(cell, digit)
        for cell, digit in step.eliminations:
            self.cands[cell] &= ~(1 << digit)


def _digits_text(mask: int) -> str:
    ds = digits_of(mask)
    return "/".join(str(d) for d in ds)


def _elim_text(elims: list[tuple[int, int]]) -> str:
    by_digit: dict[int, list[int]] = {}
    for cell, digit in elims:
        by_digit.setdefault(digit, []).append(cell)
    parts = [f"{d} from {cell_names(cells)}" for d, cells in sorted(by_digit.items())]
    return "remove " + "; ".join(parts)


# ----------------------------------------------------------------- singles


def _hidden_single(board: Board, units: range) -> Iterator[Step]:
    for u in units:
        unit = UNITS[u]
        for d in range(1, 10):
            bit = 1 << d
            places = [i for i in unit if board.cands[i] & bit]
            if len(places) == 1 and not any(board.values[i] == d for i in unit):
                cell = places[0]
                yield Step(
                    "hidden single",
                    EASY,
                    f"In {UNIT_NAMES[u]}, {d} can only go in {cell_name(cell)}.",
                    placements=[(cell, d)],
                )


def hidden_single_box(board: Board) -> Iterator[Step]:
    return _hidden_single(board, range(0, 9))


def hidden_single_line(board: Board) -> Iterator[Step]:
    return _hidden_single(board, range(9, 27))


def naked_single(board: Board) -> Iterator[Step]:
    for i in range(81):
        m = board.cands[i]
        if not board.values[i] and m and POPCOUNT[m] == 1:
            d = digits_of(m)[0]
            yield Step(
                "naked single",
                EASY,
                f"{cell_name(i)} can only be {d}: every other digit is already "
                f"in its row, column or box.",
                placements=[(i, d)],
            )


# ------------------------------------------------------- locked candidates


def pointing(board: Board) -> Iterator[Step]:
    for b, box in enumerate(BOXES):
        for d in range(1, 10):
            bit = 1 << d
            places = [i for i in box if board.cands[i] & bit]
            if len(places) < 2:
                continue
            for kind, index, lines in (("row", row_of, ROWS), ("column", col_of, COLS)):
                if len({index(i) for i in places}) == 1:
                    line = index(places[0])
                    elims = [(i, d) for i in lines[line] if box_of(i) != b and board.cands[i] & bit]
                    if elims:
                        yield Step(
                            "pointing pair" if len(places) == 2 else "pointing triple",
                            MEDIUM,
                            f"In box {b + 1}, {d} can only be in {kind} {line + 1} "
                            f"({cell_names(places)}), so {_elim_text(elims)}.",
                            eliminations=elims,
                        )


def claiming(board: Board) -> Iterator[Step]:
    for kind, lines in (("row", ROWS), ("column", COLS)):
        for n, line in enumerate(lines):
            for d in range(1, 10):
                bit = 1 << d
                places = [i for i in line if board.cands[i] & bit]
                if len(places) < 2 or len({box_of(i) for i in places}) != 1:
                    continue
                b = box_of(places[0])
                elims = [(i, d) for i in BOXES[b] if i not in line and board.cands[i] & bit]
                if elims:
                    yield Step(
                        "box/line reduction",
                        MEDIUM,
                        f"In {kind} {n + 1}, {d} can only be in box {b + 1} "
                        f"({cell_names(places)}), so {_elim_text(elims)}.",
                        eliminations=elims,
                    )


# ----------------------------------------------------------------- subsets

_SIZE_WORDS = {2: "pair", 3: "triple", 4: "quad"}


def _naked_subset(board: Board, size: int, level: int) -> Iterator[Step]:
    for u, unit in enumerate(UNITS):
        open_cells = [i for i in unit if not board.values[i]]
        pool = [i for i in open_cells if 2 <= POPCOUNT[board.cands[i]] <= size]
        for group in combinations(pool, size):
            union = 0
            for i in group:
                union |= board.cands[i]
            if POPCOUNT[union] != size:
                continue
            elims = [
                (i, d)
                for i in open_cells
                if i not in group
                for d in digits_of(board.cands[i] & union)
            ]
            if elims:
                yield Step(
                    f"naked {_SIZE_WORDS[size]}",
                    level,
                    f"In {UNIT_NAMES[u]}, {cell_names(group)} hold only "
                    f"{_digits_text(union)} between them, so those digits go there; "
                    f"{_elim_text(elims)}.",
                    eliminations=elims,
                )


def _hidden_subset(board: Board, size: int, level: int) -> Iterator[Step]:
    for u, unit in enumerate(UNITS):
        placed = {board.values[i] for i in unit if board.values[i]}
        where = {
            d: [i for i in unit if board.cands[i] >> d & 1]
            for d in range(1, 10)
            if d not in placed
        }
        pool = [d for d, cells in where.items() if 2 <= len(cells) <= size]
        for digits in combinations(pool, size):
            cells = sorted({i for d in digits for i in where[d]})
            if len(cells) != size:
                continue
            keep = sum(1 << d for d in digits)
            elims = [(i, d) for i in cells for d in digits_of(board.cands[i] & ~keep)]
            if elims:
                yield Step(
                    f"hidden {_SIZE_WORDS[size]}",
                    level,
                    f"In {UNIT_NAMES[u]}, {_digits_text(keep)} fit only in "
                    f"{cell_names(cells)}, so those cells hold nothing else; "
                    f"{_elim_text(elims)}.",
                    eliminations=elims,
                )


def naked_pair(board: Board) -> Iterator[Step]:
    return _naked_subset(board, 2, MEDIUM)


def hidden_pair(board: Board) -> Iterator[Step]:
    return _hidden_subset(board, 2, MEDIUM)


def naked_triple(board: Board) -> Iterator[Step]:
    return _naked_subset(board, 3, HARD)


def hidden_triple(board: Board) -> Iterator[Step]:
    return _hidden_subset(board, 3, HARD)


def naked_quad(board: Board) -> Iterator[Step]:
    return _naked_subset(board, 4, EXPERT)


def hidden_quad(board: Board) -> Iterator[Step]:
    return _hidden_subset(board, 4, EXPERT)


# ------------------------------------------------------------------ wings


def x_wing(board: Board) -> Iterator[Step]:
    for kind, other, lines, cross, pos in (
        ("rows", "columns", ROWS, COLS, col_of),
        ("columns", "rows", COLS, ROWS, row_of),
    ):
        for d in range(1, 10):
            bit = 1 << d
            spots = {}
            for n, line in enumerate(lines):
                places = [i for i in line if board.cands[i] & bit]
                if len(places) == 2:
                    spots[n] = tuple(pos(i) for i in places)
            for a, b in combinations(sorted(spots), 2):
                if spots[a] != spots[b]:
                    continue
                corners = [i for n in (a, b) for i in lines[n] if board.cands[i] & bit]
                elims = [
                    (i, d)
                    for x in spots[a]
                    for i in cross[x]
                    if i not in corners and board.cands[i] & bit
                ]
                if elims:
                    yield Step(
                        "X-wing",
                        HARD,
                        f"In {kind} {a + 1} and {b + 1}, {d} can only be in {other} "
                        f"{spots[a][0] + 1} and {spots[a][1] + 1} ({cell_names(corners)}), "
                        f"so it is in one of those two places in each of them; "
                        f"{_elim_text(elims)}.",
                        eliminations=elims,
                    )


def finned_x_wing(board: Board) -> Iterator[Step]:
    """An X-wing with extra candidates (fins) in one corner's box. One of the
    corner or a fin must hold the digit, so cells that see both lose it."""
    for kind, other, lines, cross, pos in (
        ("rows", "columns", ROWS, COLS, col_of),
        ("columns", "rows", COLS, ROWS, row_of),
    ):
        for d in range(1, 10):
            bit = 1 << d
            places = {
                n: [i for i in line if board.cands[i] & bit] for n, line in enumerate(lines)
            }
            for a, clean in places.items():
                if len(clean) != 2:
                    continue
                pair = {pos(i) for i in clean}
                for b, wide in places.items():
                    if b == a or not 3 <= len(wide) <= 4:
                        continue
                    if not pair <= {pos(i) for i in wide}:
                        continue
                    fins = [i for i in wide if pos(i) not in pair]
                    boxes = {box_of(i) for i in fins}
                    if len(boxes) != 1:
                        continue
                    box = boxes.pop()
                    for x in sorted(pair):
                        corner = next(i for i in wide if pos(i) == x)
                        if box_of(corner) != box:
                            continue
                        elims = [
                            (i, d)
                            for i in cross[x]
                            if box_of(i) == box
                            and i not in lines[a]
                            and i not in lines[b]
                            and board.cands[i] & bit
                        ]
                        if not elims:
                            continue
                        yield Step(
                            "finned X-wing",
                            HARD,
                            f"In {kind} {a + 1} and {b + 1}, {d} forms an X-wing in "
                            f"{other} {min(pair) + 1} and {max(pair) + 1}, except for "
                            f"the extra {cell_names(fins)} (fin{'s' if len(fins) > 1 else ''}) in "
                            f"{kind[:-1]} {b + 1}. Either a fin or the corner {cell_name(corner)} "
                            f"holds {d}, and both see the rest of box {box + 1} in "
                            f"{other[:-1]} {x + 1}, so {_elim_text(elims)}.",
                            eliminations=elims,
                        )


def swordfish(board: Board) -> Iterator[Step]:
    """An X-wing grown to three lines: in three rows a digit's spots all fall
    in the same three columns (or the other way round)."""
    for kind, other, lines, cross, pos in (
        ("rows", "columns", ROWS, COLS, col_of),
        ("columns", "rows", COLS, ROWS, row_of),
    ):
        for d in range(1, 10):
            bit = 1 << d
            spots = {}
            for n, line in enumerate(lines):
                places = [i for i in line if board.cands[i] & bit]
                if 2 <= len(places) <= 3:
                    spots[n] = {pos(i) for i in places}
            for base in combinations(sorted(spots), 3):
                covers = sorted(set().union(*(spots[n] for n in base)))
                if len(covers) != 3:
                    continue
                corners = [i for n in base for i in lines[n] if board.cands[i] & bit]
                elims = [
                    (i, d)
                    for x in covers
                    for i in cross[x]
                    if i not in corners and board.cands[i] & bit
                ]
                if elims:
                    b1, b2, b3 = (n + 1 for n in base)
                    c1, c2, c3 = (x + 1 for x in covers)
                    yield Step(
                        "swordfish",
                        EXPERT,
                        f"In {kind} {b1}, {b2} and {b3}, the digit {d} can only go in "
                        f"{other} {c1}, {c2} and {c3} ({cell_names(corners)}). Each of "
                        f"those {kind} needs its own {d} there, which uses up the {d} "
                        f"of all three {other}, so {_elim_text(elims)}.",
                        eliminations=elims,
                    )


def xy_wing(board: Board) -> Iterator[Step]:
    bivalue = [i for i in range(81) if POPCOUNT[board.cands[i]] == 2]
    for pivot in bivalue:
        pm = board.cands[pivot]
        wings = [i for i in bivalue if i in PEERS[pivot] and POPCOUNT[pm & board.cands[i]] == 1]
        for w1, w2 in combinations(wings, 2):
            m1, m2 = board.cands[w1], board.cands[w2]
            z = m1 & m2 & ~pm
            if not z or POPCOUNT[z] != 1 or (m1 & pm) == (m2 & pm):
                continue
            d = digits_of(z)[0]
            seen = (PEERS[w1] & PEERS[w2]) - {pivot}
            elims = [(i, d) for i in sorted(seen) if board.cands[i] & z]
            if elims:
                yield Step(
                    "XY-wing",
                    HARD,
                    f"{cell_name(pivot)} is {_digits_text(pm)}; whichever it is, "
                    f"{cell_name(w1)} ({_digits_text(m1)}) or {cell_name(w2)} "
                    f"({_digits_text(m2)}) must be {d}, so {_elim_text(elims)}.",
                    eliminations=elims,
                )


def xyz_wing(board: Board) -> Iterator[Step]:
    """Pivot x/y/z with wings x/z and y/z: any cell seeing all three cannot be z."""
    for pivot in range(81):
        pm = board.cands[pivot]
        if POPCOUNT[pm] != 3:
            continue
        wings = [
            i for i in sorted(PEERS[pivot])
            if POPCOUNT[board.cands[i]] == 2 and board.cands[i] & ~pm == 0
        ]
        for w1, w2 in combinations(wings, 2):
            m1, m2 = board.cands[w1], board.cands[w2]
            z = m1 & m2
            if POPCOUNT[z] != 1 or (m1 | m2) != pm:
                continue
            d = digits_of(z)[0]
            seen = PEERS[pivot] & PEERS[w1] & PEERS[w2]
            elims = [(i, d) for i in sorted(seen) if board.cands[i] & z]
            if elims:
                yield Step(
                    "XYZ-wing",
                    HARD,
                    f"{cell_name(pivot)} is {_digits_text(pm)}, with wings "
                    f"{cell_name(w1)} ({_digits_text(m1)}) and {cell_name(w2)} "
                    f"({_digits_text(m2)}); one of the three cells must be {d}, "
                    f"so {_elim_text(elims)}.",
                    eliminations=elims,
                )


Technique = Callable[[Board], Iterator[Step]]

#: Every technique, simplest first.
TECHNIQUES: list[Technique] = [
    hidden_single_box,
    naked_single,
    hidden_single_line,
    pointing,
    claiming,
    naked_pair,
    hidden_pair,
    naked_triple,
    hidden_triple,
    x_wing,
    finned_x_wing,
    xy_wing,
    xyz_wing,
    swordfish,
    naked_quad,
    hidden_quad,
]
_TECHNIQUE_LEVEL = {
    hidden_single_box: EASY,
    naked_single: EASY,
    hidden_single_line: EASY,
    pointing: MEDIUM,
    claiming: MEDIUM,
    naked_pair: MEDIUM,
    hidden_pair: MEDIUM,
    naked_triple: HARD,
    hidden_triple: HARD,
    x_wing: HARD,
    finned_x_wing: HARD,
    xy_wing: HARD,
    xyz_wing: HARD,
    swordfish: EXPERT,
    naked_quad: EXPERT,
    hidden_quad: EXPERT,
}


def next_step(board: Board, max_level: int = EXPERT) -> Step | None:
    """The simplest available step, or None when nothing applies."""
    for technique in TECHNIQUES:
        if _TECHNIQUE_LEVEL[technique] > max_level:
            break
        for step in technique(board):
            return step
    return None


@dataclass
class LogicResult:
    steps: list[Step]
    board: Board
    solved: bool

    @property
    def level(self) -> int:
        """Difficulty level: the hardest technique used, EXPERT if stuck
        (expert puzzles are either solved with an expert technique such as a
        swordfish, or need more than sudokit knows)."""
        if not self.solved:
            return EXPERT
        return max((s.level for s in self.steps), default=EASY)

    def technique_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.steps:
            counts[s.technique] = counts.get(s.technique, 0) + 1
        return counts


def solve_logically(cells: Sequence[int], max_level: int = EXPERT) -> LogicResult:
    """Apply steps until solved or stuck. Raises ValueError on a broken grid."""
    board = Board(cells)
    steps: list[Step] = []
    while not board.solved():
        if board.broken():
            break
        step = next_step(board, max_level)
        if step is None:
            break
        board.apply(step)
        steps.append(step)
    return LogicResult(steps, board, board.solved())


@dataclass
class Rating:
    level: int
    name: str
    techniques: dict[str, int]
    steps: int
    #: False when logic got stuck and the rest needs trial and error.
    solved: bool = True


def rate(cells: Sequence[int]) -> Rating:
    """Difficulty of a puzzle (assumed to have a unique solution)."""
    result = solve_logically(cells)
    level = result.level
    return Rating(
        level, LEVEL_NAMES[level], result.technique_counts(), len(result.steps), result.solved
    )


def steps_to_next_placement(cells: Sequence[int], max_level: int = EXPERT) -> tuple[list[Step], bool]:
    """Steps from ``cells`` up to and including the next placed digit.

    Returns ``(steps, found)``; ``found`` is False if logic got stuck before
    any digit could be placed (the steps so far are still returned).
    """
    board = Board(cells)
    steps: list[Step] = []
    while not board.solved() and not board.broken():
        step = next_step(board, max_level)
        if step is None:
            return steps, False
        steps.append(step)
        if step.placements:
            return steps, True
        board.apply(step)
    return steps, False
