import io

from sudokit.game import Game, format_seconds, play
from sudokit.grid import PEERS, parse

PUZZLE = "3.9...5..86579..4..4...8679.5.......7.4...8.1.......5.5231...9..9..52183..6...7.5"
SOLUTION = "379264518865791342241538679958416237734925861612873954523187496497652183186349725"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def new_game(clock=None):
    return Game(parse(PUZZLE), parse(SOLUTION), clock=clock or Clock())


def run(game, *lines):
    out = io.StringIO()
    code = play(game, [line + "\n" for line in lines], out, echo=True)
    return code, out.getvalue()


def missing_moves():
    """``r?c? d`` commands for every empty cell, in order."""
    return [f"r{i // 9 + 1}c{i % 9 + 1} {SOLUTION[i]}" for i in range(81) if PUZZLE[i] == "."]


def test_place_and_clear():
    game = new_game()
    assert game.handle("r1c2 7") == "r1c2 = 7."
    assert game.values[1] == 7
    assert game.handle("r1c2 0") == "Cleared r1c2."
    assert game.handle("R1C2=7") == "r1c2 = 7."
    assert game.handle("clear r1c2") == "Cleared r1c2."
    assert game.handle("127") == "r1c2 = 7."


def test_cannot_change_a_given():
    game = new_game()
    assert game.handle("r1c1 5") == "r1c1 is a given and cannot be changed."
    assert game.values[0] == 3


def test_placing_a_clash_warns():
    game = new_game()
    reply = game.handle("r1c2 3")
    assert "Careful: 3 is also in r1c1" in reply


def test_redo_replays_undone_changes():
    game = new_game()
    assert game.redo() == "Nothing to redo."
    game.handle("r1c2 7")
    game.handle("pencil r1c4 12")
    game.handle("undo")
    game.handle("undo")
    assert game.values[1] == 0
    assert "Redone." in game.handle("redo")
    assert game.values[1] == 7
    game.handle("redo")
    assert game.marks[3] == {1, 2}
    assert game.redo() == "Nothing to redo."
    game.handle("undo")
    assert game.marks[3] == set()


def test_new_change_clears_redo():
    game = new_game()
    game.handle("r1c2 7")
    game.handle("undo")
    game.handle("r1c2 4")
    assert game.redo() == "Nothing to redo."
    assert game.values[1] == 4


def test_undo_restores_values_and_marks():
    game = new_game()
    game.handle("r1c2 7")
    game.handle("pencil r1c4 12")
    assert game.marks[3] == {1, 2}
    game.handle("undo")
    assert game.marks[3] == set()
    game.handle("undo")
    assert game.values[1] == 0
    assert game.undo() == "Nothing to undo."


def test_pencil_toggle_auto_and_clear():
    game = new_game()
    assert game.handle("pencil r1c2 1 2") == "Pencil marks in r1c2: 12."
    assert game.handle("pencil r1c2 2") == "Pencil marks in r1c2: 1."
    game.handle("pencil auto")
    assert game.marks[1] == {1, 7} and game.marks[0] == set()
    assert any(1 in game.marks[p] for p in PEERS[1])
    game.handle("r1c2 1")  # wrong, but allowed
    # placing a digit removes it from the pencil marks of every peer
    assert not any(1 in game.marks[p] for p in PEERS[1])
    game.handle("pencil clear")
    assert all(not m for m in game.marks)
    assert "filled" in game.handle("pencil r1c1 4")


def test_marks_view():
    game = new_game()
    game.handle("pencil r1c2 12")
    first_row = game.marks_text().splitlines()[0]
    assert first_row.startswith("1   [3]") and "12" in first_row


def test_check_reports_wrong_entries_and_clashes():
    game = new_game()
    assert game.handle("check") == "No mistakes so far. 47 cell(s) to go."
    game.handle("r1c2 3")
    reply = game.handle("check")
    assert "3 appears twice in box 1: r1c1, r1c2" in reply
    assert "1 wrong: r1c2" in reply
    assert game.checks == 2


def test_hint_points_at_mistake_first():
    game = new_game()
    game.handle("r1c2 1")
    assert game.handle("hint") == "r1c2 is not right. Clear it (r1c2 0) or undo, then ask again."
    game.handle("undo")
    assert "Next: r" in game.handle("hint")
    assert game.hints == 2


def test_timer_and_time_command():
    clock = Clock()
    game = new_game(clock)
    clock.t += 125
    assert game.handle("time") == "Elapsed: 02:05"
    assert format_seconds(3725) == "1:02:05"


def test_full_game_is_won_with_summary():
    clock = Clock()
    game = new_game(clock)
    clock.t += 61
    code, out = run(game, "hint", *missing_moves(), "this is never read")
    assert code == 0
    assert game.solved() and game.over()
    assert "Solved in 01:01 with 1 hint(s)." in out
    assert "this is never read" not in out


def test_loop_quits_on_eof_and_quit():
    assert run(new_game())[1].endswith("> \nBye.\n")
    code, out = run(new_game(), "quit")
    assert code == 0 and out.endswith("> quit\nBye.\n")


def test_unknown_command_and_help():
    game = new_game()
    assert game.handle("dance").startswith("Unknown command: dance.")
    assert "pencil auto" in game.handle("help")


def test_reveal_ends_the_game():
    _, out = run(new_game(), "reveal")
    assert "Solution:" in out and "| 3 7 9 |" in out


def test_leading_bom_on_first_line_is_ignored():
    game = new_game()
    run(game, "﻿r1c2 7")
    assert game.values[1] == 7
