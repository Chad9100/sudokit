"""Fast solver: constraint propagation plus depth-first search.

Candidates are bitmasks with bit ``d`` set when digit ``d`` (1-9) is still
possible. Propagation applies naked singles (a solved cell removes its digit
from its peers) and hidden singles (a digit with one place left in a unit)
until nothing changes; the search then branches on the cell with the fewest
candidates.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .grid import PEER_LIST, UNITS, find_conflicts

ALL = 0b1111111110  # bits 1..9
POPCOUNT = [bin(m).count("1") for m in range(1024)]
DIGIT_OF = {1 << d: d for d in range(1, 10)}


def digits_of(mask: int) -> list[int]:
    return [d for d in range(1, 10) if mask >> d & 1]


def _propagate(cands: list[int]) -> bool:
    """Reduce ``cands`` in place. False if a contradiction shows up."""
    queue = [i for i in range(81) if POPCOUNT[cands[i]] == 1]
    done = bytearray(81)
    while True:
        while queue:
            i = queue.pop()
            if done[i]:
                continue
            done[i] = 1
            bit = cands[i]
            for p in PEER_LIST[i]:
                if cands[p] & bit:
                    m = cands[p] & ~bit
                    if not m:
                        return False
                    cands[p] = m
                    if not m & (m - 1):
                        queue.append(p)
        changed = False
        for unit in UNITS:
            once = twice = 0
            for i in unit:
                m = cands[i]
                twice |= once & m
                once |= m
            if once != ALL:
                return False  # some digit has no place in this unit
            only = once & ~twice
            if not only:
                continue
            for i in unit:
                hit = cands[i] & only
                if hit and cands[i] != hit:
                    if hit & (hit - 1):
                        return False  # two digits both need this one cell
                    cands[i] = hit
                    queue.append(i)
                    changed = True
        if not changed and not queue:
            return True


def _search(cands: list[int], found: list[list[int]], limit: int, rng: random.Random | None) -> None:
    if not _propagate(cands):
        return
    best = -1
    best_n = 10
    for i in range(81):
        n = POPCOUNT[cands[i]]
        if 1 < n < best_n:
            best, best_n = i, n
            if n == 2:
                break
    if best < 0:
        found.append([DIGIT_OF[m] for m in cands])
        return
    choices = digits_of(cands[best])
    if rng is not None:
        rng.shuffle(choices)
    for d in choices:
        trial = cands[:]
        trial[best] = 1 << d
        _search(trial, found, limit, rng)
        if len(found) >= limit:
            return


def solve_all(cells: Sequence[int], limit: int = 2, rng: random.Random | None = None) -> list[list[int]]:
    """Up to ``limit`` solutions of the grid (an empty list when there are none)."""
    if len(cells) != 81:
        raise ValueError("a grid has 81 cells")
    if find_conflicts(cells):
        return []
    cands = [(1 << v) if v else ALL for v in cells]
    found: list[list[int]] = []
    _search(cands, found, limit, rng)
    return found


@dataclass
class SolveResult:
    status: str  # "unique", "multiple" or "none"
    solution: list[int] | None
    #: A second solution when ``status`` is "multiple".
    other: list[int] | None = None


def solve(cells: Sequence[int]) -> SolveResult:
    """Solve and say whether the solution is unique."""
    found = solve_all(cells, limit=2)
    if not found:
        return SolveResult("none", None)
    if len(found) == 1:
        return SolveResult("unique", found[0])
    return SolveResult("multiple", found[0], found[1])


def has_unique_solution(cells: Sequence[int]) -> bool:
    return len(solve_all(cells, limit=2)) == 1


def random_solution(rng: random.Random) -> list[int]:
    """A random complete, valid grid."""
    return solve_all([0] * 81, limit=1, rng=rng)[0]
