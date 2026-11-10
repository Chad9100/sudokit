import pytest

from sudokit.grid import (
    BOXES,
    PEERS,
    PuzzleFormatError,
    box_of,
    cell_name,
    find_conflicts,
    format_grid,
    parse,
    parse_many,
    to_line,
)

PUZZLE = "3.9...5..86579..4..4...8679.5.......7.4...8.1.......5.5231...9..9..52183..6...7.5"


def test_geometry():
    assert all(len(p) == 20 for p in PEERS)
    assert BOXES[4][0] == 30
    assert box_of(80) == 8 and box_of(30) == 4
    assert cell_name(0) == "r1c1" and cell_name(80) == "r9c9" and cell_name(22) == "r3c5"


def test_parse_line_accepts_dots_and_zeros():
    cells = parse(PUZZLE)
    assert len(cells) == 81 and cells[0] == 3 and cells[1] == 0
    assert parse(PUZZLE.replace(".", "0")) == cells


def test_formatted_grid_round_trips():
    cells = parse(PUZZLE)
    drawn = format_grid(cells)
    assert drawn.splitlines()[0] == "+-------+-------+-------+"
    assert parse(drawn) == cells
    assert to_line(parse(drawn)) == PUZZLE


def test_parse_ignores_comments_and_bom():
    text = "﻿# a comment line\n" + "\n".join(PUZZLE[i:i + 9] for i in range(0, 81, 9)) + "\n"
    assert parse(text) == parse(PUZZLE)


def test_parse_errors():
    with pytest.raises(PuzzleFormatError, match="expected 81 cells, found 80"):
        parse(PUZZLE[:-1])
    with pytest.raises(PuzzleFormatError, match="unexpected character 'x' on line 1"):
        parse("x" + PUZZLE[1:])


def test_parse_many_reads_one_puzzle_per_line():
    other = PUZZLE.replace("3", ".", 1)
    many = parse_many(f"# batch\n{PUZZLE}\n\n{other}\n")
    assert len(many) == 2 and many[1][0] == 0
    assert len(parse_many(format_grid(parse(PUZZLE)))) == 1


def test_labeled_grid_has_coordinates():
    drawn = format_grid(parse(PUZZLE), labels=True).splitlines()
    assert drawn[0].strip() == "1 2 3   4 5 6   7 8 9"
    assert drawn[2].startswith("1 | 3 . 9 |")


def test_find_conflicts():
    cells = parse(PUZZLE)
    assert find_conflicts(cells) == []
    cells[1] = 3  # same row and box as r1c1
    names = {(name, digit) for name, digit, _ in find_conflicts(cells)}
    assert names == {("box 1", 3), ("row 1", 3)}
