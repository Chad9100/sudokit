import pytest

from sudokit.grid import parse
from sudokit.logic import (
    EASY,
    EXPERT,
    HARD,
    MEDIUM,
    Board,
    claiming,
    hidden_pair,
    hidden_single_box,
    naked_pair,
    naked_single,
    naked_triple,
    next_step,
    pointing,
    rate,
    solve_logically,
    steps_to_next_placement,
    x_wing,
    xy_wing,
)
from sudokit.solver import solve

EASY_PUZZLE = "3.9...5..86579..4..4...8679.5.......7.4...8.1.......5.5231...9..9..52183..6...7.5"
MEDIUM_PUZZLE = ".536......7...9..66.4...93.49.1...5.....8.....6...4.82.36...2.55..9...1......364."
HARD_PUZZLE = "...8..2.........814..2.75..1.....34..7..3..6..36.....9..26.4..898.........1..9..."
EXPERT_PUZZLE = "..6.1.......7..5..84....9.24..3....8...29...3..5.......82..5......82...631...7..."


def mask(*digits):
    return sum(1 << d for d in digits)


def empty_board():
    return Board([0] * 81)


def first(technique, board):
    return next(iter(technique(board)), None)


# ------------------------------------------------------------ singles


def test_board_candidates_follow_givens():
    board = Board(parse(EASY_PUZZLE))
    # r1c2 sees 3 5 9 in its row, 4 5 6 9 in its column and 3 4 5 6 8 9 in its box
    assert board.cands[1] == mask(1, 7)
    assert board.cands[0] == 0  # a given


def test_board_rejects_clashing_grid():
    cells = parse(EASY_PUZZLE)
    cells[1] = 3
    with pytest.raises(ValueError):
        Board(cells)


def test_hidden_single_in_box():
    step = first(hidden_single_box, Board(parse(EASY_PUZZLE)))
    assert step.technique == "hidden single" and step.level == EASY
    (cell, digit), = step.placements
    assert solve(parse(EASY_PUZZLE)).solution[cell] == digit
    assert step.explanation.startswith("In box ")


def test_naked_single():
    board = empty_board()
    board.cands[40] = mask(7)
    step = first(naked_single, board)
    assert step.placements == [(40, 7)]
    assert "r5c5 can only be 7" in step.explanation


# -------------------------------------------------- medium techniques


def test_naked_pair_removes_digits_from_the_rest_of_the_unit():
    board = empty_board()
    board.cands[0] = board.cands[1] = mask(1, 2)
    step = first(naked_pair, board)
    assert step.technique == "naked pair" and step.level == MEDIUM
    assert (2, 1) in step.eliminations and (2, 2) in step.eliminations
    assert not any(cell in (0, 1) for cell, _ in step.eliminations)
    assert "r1c1, r1c2 hold only 1/2" in step.explanation


def test_hidden_pair_strips_other_candidates():
    board = empty_board()
    for cell in range(2, 9):
        board.cands[cell] &= ~mask(1, 2)
    step = first(hidden_pair, board)
    assert step.technique == "hidden pair"
    assert {cell for cell, _ in step.eliminations} == {0, 1}
    assert sorted({d for _, d in step.eliminations}) == [3, 4, 5, 6, 7, 8, 9]
    assert step.explanation.startswith("In row 1, 1/2 fit only in r1c1, r1c2")


def test_pointing_pair():
    board = empty_board()
    for cell in (2, 9, 10, 11, 18, 19, 20):
        board.cands[cell] &= ~mask(5)
    step = first(pointing, board)
    assert step.technique == "pointing pair"
    assert step.eliminations == [(c, 5) for c in range(3, 9)]


def test_box_line_reduction():
    board = empty_board()
    for cell in range(3, 9):  # 5 only in box 1 within row 1
        board.cands[cell] &= ~mask(5)
    step = first(claiming, board)
    assert step.technique == "box/line reduction"
    assert step.eliminations == [(c, 5) for c in (9, 10, 11, 18, 19, 20)]


# ---------------------------------------------------- hard techniques


def test_naked_triple():
    board = empty_board()
    board.cands[0], board.cands[1], board.cands[2] = mask(1, 2), mask(2, 3), mask(1, 3)
    step = first(naked_triple, board)
    assert step.technique == "naked triple" and step.level == HARD
    assert (9, 1) in step.eliminations and (9, 3) in step.eliminations
    assert not any(cell in (0, 1, 2) for cell, _ in step.eliminations)


def test_x_wing_on_rows():
    board = empty_board()
    for row in (0, 4):
        for col in range(9):
            if col not in (1, 7):
                board.cands[row * 9 + col] &= ~mask(4)
    step = first(x_wing, board)
    assert step.technique == "X-wing"
    cells = {cell for cell, digit in step.eliminations}
    assert all(digit == 4 for _, digit in step.eliminations)
    assert cells == {r * 9 + c for r in range(9) if r not in (0, 4) for c in (1, 7)}


def test_xy_wing():
    board = empty_board()
    board.cands[0] = mask(1, 2)   # pivot r1c1
    board.cands[4] = mask(1, 3)   # r1c5
    board.cands[36] = mask(2, 3)  # r5c1
    step = first(xy_wing, board)
    assert step.technique == "XY-wing"
    assert step.eliminations == [(40, 3)]  # r5c5 sees both wings


# ------------------------------------------------------------ rating


@pytest.mark.parametrize(
    "puzzle, name",
    [(EASY_PUZZLE, "easy"), (MEDIUM_PUZZLE, "medium"), (HARD_PUZZLE, "hard"), (EXPERT_PUZZLE, "expert")],
)
def test_rating(puzzle, name):
    assert rate(parse(puzzle)).name == name


def test_hard_rating_lists_the_hard_technique():
    rating = rate(parse(HARD_PUZZLE))
    assert rating.level == HARD and "XY-wing" in rating.techniques


def test_expert_puzzle_gets_stuck():
    result = solve_logically(parse(EXPERT_PUZZLE))
    assert not result.solved and result.level == EXPERT


def test_max_level_limits_techniques():
    assert not solve_logically(parse(MEDIUM_PUZZLE), max_level=EASY).solved
    assert solve_logically(parse(MEDIUM_PUZZLE), max_level=MEDIUM).solved


@pytest.mark.parametrize("puzzle", [EASY_PUZZLE, MEDIUM_PUZZLE, HARD_PUZZLE, EXPERT_PUZZLE])
def test_every_step_agrees_with_the_solution(puzzle):
    cells = parse(puzzle)
    solution = solve(cells).solution
    board = Board(cells)
    while (step := next_step(board)) is not None:
        assert all(solution[c] == d for c, d in step.placements)
        assert all(solution[c] != d for c, d in step.eliminations)
        board.apply(step)
    assert all(v == 0 or v == s for v, s in zip(board.values, solution))


def test_steps_to_next_placement_ends_with_a_placement():
    steps, found = steps_to_next_placement(parse(HARD_PUZZLE))
    assert found and steps[-1].placements
