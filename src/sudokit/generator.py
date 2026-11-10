"""Puzzle generation with a target difficulty.

Start from a random full grid and remove clues in symmetric pairs (the cell
and its mirror through the centre). A removal is kept only if the puzzle can
still be solved by logic using techniques no harder than the target, which
also proves the solution is unique. A finished puzzle whose hardest needed
technique is below the target is thrown away and another grid is tried.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .logic import EASY, HARD, LEVEL_NAMES, LEVELS, MEDIUM, solve_logically
from .solver import random_solution

#: Fewest clues kept for each level (easy puzzles stay roomy).
MIN_CLUES = {EASY: 34, MEDIUM: 26, HARD: 17}
MAX_ATTEMPTS = 200


class GenerationError(RuntimeError):
    """No puzzle of the requested difficulty was found."""


@dataclass
class Puzzle:
    cells: list[int]
    solution: list[int]
    level: int
    techniques: dict[str, int]

    @property
    def difficulty(self) -> str:
        return LEVEL_NAMES[self.level]

    @property
    def clues(self) -> int:
        return sum(1 for v in self.cells if v)


def _attempt(rng: random.Random, level: int) -> Puzzle | None:
    solution = random_solution(rng)
    cells = solution[:]
    pairs = list(range(41))  # cell i pairs with 80 - i; 40 is the centre
    rng.shuffle(pairs)
    clues = 81
    for i in pairs:
        group = (i,) if i == 40 else (i, 80 - i)
        if clues - len(group) < MIN_CLUES[level]:
            continue
        for c in group:
            cells[c] = 0
        if solve_logically(cells, max_level=level).solved:
            clues -= len(group)
        else:
            for c in group:
                cells[c] = solution[c]
    result = solve_logically(cells, max_level=level)
    if result.level != level:
        return None
    return Puzzle(cells, solution, level, result.technique_counts())


def generate(difficulty: str = "medium", seed: int | None = None, rng: random.Random | None = None) -> Puzzle:
    """A puzzle with a unique solution needing exactly ``difficulty`` techniques."""
    if difficulty not in LEVELS or LEVELS[difficulty] > HARD:
        raise ValueError(f"unknown difficulty {difficulty!r} (use easy, medium or hard)")
    level = LEVELS[difficulty]
    if rng is None:
        rng = random.Random(seed)
    for _ in range(MAX_ATTEMPTS):
        puzzle = _attempt(rng, level)
        if puzzle is not None:
            return puzzle
    raise GenerationError(f"no {difficulty} puzzle found in {MAX_ATTEMPTS} tries")
