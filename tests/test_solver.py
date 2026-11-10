import random

from sudokit.grid import find_conflicts, parse, to_line
from sudokit.solver import has_unique_solution, random_solution, solve, solve_all

EASY = "3.9...5..86579..4..4...8679.5.......7.4...8.1.......5.5231...9..9..52183..6...7.5"
EASY_SOLUTION = "379264518865791342241538679958416237734925861612873954523187496497652183186349725"
EXPERT = "..6.1.......7..5..84....9.24..3....8...29...3..5.......82..5......82...631...7..."


def is_valid_solution(cells, puzzle):
    return 0 not in cells and not find_conflicts(cells) and all(
        p == 0 or p == c for p, c in zip(puzzle, cells)
    )


def test_solves_easy_puzzle():
    result = solve(parse(EASY))
    assert result.status == "unique"
    assert to_line(result.solution) == EASY_SOLUTION


def test_solves_puzzle_that_needs_search():
    puzzle = parse(EXPERT)
    result = solve(puzzle)
    assert result.status == "unique"
    assert is_valid_solution(result.solution, puzzle)


def test_detects_multiple_solutions():
    found = solve_all(parse("." * 81), limit=2)
    assert len(found) == 2 and found[0] != found[1]
    result = solve(parse("." * 81))
    assert result.status == "multiple" and result.other != result.solution


def test_detects_no_solution_from_clash():
    puzzle = parse(EASY)
    puzzle[1] = 3  # 3 already in row 1
    assert solve(puzzle).status == "none"


def test_detects_no_solution_without_a_visible_clash():
    # The puzzle has a unique solution with 6 in r1c5, so a 1 there breaks it
    # even though no row, column or box repeats a digit.
    puzzle = parse(EASY)
    puzzle[4] = 1
    assert find_conflicts(puzzle) == []
    assert solve(puzzle).status == "none"


def test_full_valid_grid_is_its_own_solution():
    full = parse(EASY_SOLUTION)
    assert solve(full).solution == full
    assert has_unique_solution(full)


def test_random_solution_is_valid_and_seeded():
    a = random_solution(random.Random(5))
    b = random_solution(random.Random(5))
    assert a == b
    assert is_valid_solution(a, [0] * 81)
    assert random_solution(random.Random(6)) != a
