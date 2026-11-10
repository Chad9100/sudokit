import pytest

from sudokit.generator import MIN_CLUES, generate
from sudokit.grid import find_conflicts
from sudokit.logic import EASY, rate
from sudokit.solver import solve


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_generated_puzzle_is_unique_and_rated(difficulty):
    puzzle = generate(difficulty, seed=11)
    result = solve(puzzle.cells)
    assert result.status == "unique"
    assert result.solution == puzzle.solution
    assert puzzle.difficulty == difficulty
    assert rate(puzzle.cells).name == difficulty


def test_same_seed_same_puzzle():
    assert generate("medium", seed=42).cells == generate("medium", seed=42).cells
    assert generate("medium", seed=42).cells != generate("medium", seed=43).cells


def test_givens_match_solution_and_grid_is_valid():
    puzzle = generate("easy", seed=3)
    assert not find_conflicts(puzzle.solution) and 0 not in puzzle.solution
    assert all(v == 0 or v == s for v, s in zip(puzzle.cells, puzzle.solution))


def test_clues_are_symmetric():
    cells = generate("medium", seed=5).cells
    assert all(bool(cells[i]) == bool(cells[80 - i]) for i in range(81))


def test_easy_puzzles_keep_enough_clues():
    puzzle = generate("easy", seed=8)
    assert puzzle.clues >= MIN_CLUES[EASY]
    assert set(puzzle.techniques) <= {"hidden single", "naked single"}


def test_unknown_difficulty():
    with pytest.raises(ValueError, match="unknown difficulty"):
        generate("expert", seed=1)
