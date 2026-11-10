from sudokit.grid import parse
from sudokit.hints import hint_text
from sudokit.logic import solve_logically
from sudokit.solver import solve

EASY_PUZZLE = "3.9...5..86579..4..4...8679.5.......7.4...8.1.......5.5231...9..9..52183..6...7.5"
EASY_SOLUTION = "379264518865791342241538679958416237734925861612873954523187496497652183186349725"
HARD_PUZZLE = "...8..2.........814..2.75..1.....34..7..3..6..36.....9..26.4..898.........1..9..."
EXPERT_PUZZLE = "..6.1.......7..5..84....9.24..3....8...29...3..5.......82..5......82...631...7..."


def test_hint_names_technique_and_next_move():
    text = hint_text(parse(EASY_PUZZLE))
    assert text.startswith("Hidden single: In box ")
    last = text.splitlines()[-1]
    assert last.startswith("Next: r") and last.endswith(".")


def test_hint_move_is_correct():
    text = hint_text(parse(HARD_PUZZLE))
    cell = text.splitlines()[-1].split()[1]  # e.g. r3c5
    r, c = int(cell[1]) - 1, int(cell[3]) - 1
    digit = int(text.rstrip(".").split()[-1])
    assert solve(parse(HARD_PUZZLE)).solution[r * 9 + c] == digit


def test_hint_reports_clash():
    cells = parse(EASY_PUZZLE)
    cells[1] = 3
    assert "3 appears more than once in box 1" in hint_text(cells)


def test_hint_reports_dead_end():
    cells = parse(EASY_PUZZLE)
    cells[4] = 1  # no clash, but the solution has 6 there
    assert hint_text(cells) == "This grid has no solution, so some entry is wrong."


def test_hint_on_full_grid():
    assert hint_text(parse(EASY_SOLUTION)) == "The grid is already full."


def test_hint_falls_back_to_solution_when_logic_is_stuck():
    stuck = solve_logically(parse(EXPERT_PUZZLE)).board.values
    text = hint_text(stuck)
    assert "No step found" in text
    assert "From the solution: r" in text


def test_hint_mentions_multiple_solutions():
    assert hint_text(parse("." * 81)).startswith("Note: this grid has more than one solution.")
