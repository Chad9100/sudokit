"""Turn the logic steps into a hint a person can follow."""

from __future__ import annotations

from typing import Sequence

from .grid import cell_name, find_conflicts
from .logic import Board, Step, steps_to_next_placement
from .solver import POPCOUNT, solve


def describe(step: Step) -> str:
    name = step.technique[0].upper() + step.technique[1:]
    return f"{name}: {step.explanation}"


def hint_text(values: Sequence[int], solution: Sequence[int] | None = None) -> str:
    """Explain the next digit that can be placed, with any steps leading to it."""
    conflicts = find_conflicts(values)
    if conflicts:
        name, digit, cells = conflicts[0]
        where = ", ".join(cell_name(c) for c in cells)
        return f"{digit} appears more than once in {name} ({where}). Fix that first."
    if all(values):
        return "The grid is already full."
    note = ""
    if solution is None:
        result = solve(values)
        if result.status == "none":
            return "This grid has no solution, so some entry is wrong."
        if result.status == "multiple":
            note = "Note: this grid has more than one solution.\n"
        solution = result.solution
    steps, found = steps_to_next_placement(values)
    if found:
        lines = [describe(s) for s in steps]
        if len(steps) > 1:
            lines = [f"{n}. {line}" for n, line in enumerate(lines, start=1)]
        cell, digit = steps[-1].placements[0]
        lines.append(f"Next: {cell_name(cell)} = {digit}.")
        return note + "\n".join(lines)
    # Logic is stuck: point at the most constrained cell and give its value.
    board = Board(values)
    open_cells = [i for i in range(81) if not values[i]]
    cell = min(open_cells, key=lambda i: (POPCOUNT[board.cands[i]], i))
    assert solution is not None
    return (
        note
        + "No step found with the techniques sudokit knows (singles, pairs, triples, "
        "pointing, box/line, X-wing, finned X-wing, XY-wing, swordfish).\n"
        f"From the solution: {cell_name(cell)} = {solution[cell]}."
    )
