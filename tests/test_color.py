import io
import re

from sudokit.cli import main, use_color
from sudokit.game import CLASH_STYLE, ENTRY_STYLE, FOCUS_STYLE, GIVEN_STYLE, Game
from sudokit.grid import parse

PUZZLE = "3.9...5..86579..4..4...8679.5.......7.4...8.1.......5.5231...9..9..52183..6...7.5"
SOLUTION = "379264518865791342241538679958416237734925861612873954523187496497652183186349725"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def new_game(color=True):
    game = Game(parse(PUZZLE), parse(SOLUTION))
    game.color = color
    return game


def paint(style, ch):
    return f"\x1b[{style}m{ch}\x1b[0m"


class Tty(io.StringIO):
    def isatty(self):
        return True


def test_plain_board_has_no_escape_codes():
    assert "\x1b" not in new_game(color=False).board_text()


def test_colour_marks_givens_and_entries():
    game = new_game()
    game.handle("r1c2 7")
    game.focus = 0  # the placed-digit highlight has its own tests below
    text = game.board_text()
    assert paint(GIVEN_STYLE, "3") in text
    assert paint(ENTRY_STYLE, "7") in text


def test_colour_marks_clashes():
    game = new_game()
    game.handle("r1c2 3")  # a second 3 in row 1
    game.focus = 0
    text = game.board_text()
    assert paint(CLASH_STYLE, "3") in text
    assert text.count(CLASH_STYLE) >= 2  # the new entry and the given 3


def test_colour_does_not_change_the_layout():
    game = new_game()
    game.handle("r1c2 7")
    coloured = game.board_text()
    game.color = False
    assert ANSI.sub("", coloured) == game.board_text()


def test_use_color_modes():
    assert use_color("always", io.StringIO(), {"NO_COLOR": "1"}) is True
    assert use_color("never", Tty(), {}) is False
    assert use_color("auto", Tty(), {}) is True
    assert use_color("auto", io.StringIO(), {}) is False
    assert use_color("auto", Tty(), {"NO_COLOR": "1"}) is False
    assert use_color("auto", Tty(), {"TERM": "dumb"}) is False
    assert use_color("auto", Tty(), {"NO_COLOR": ""}) is True


def run_play(monkeypatch, tmp_path, *argv):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path))
    out, err = io.StringIO(), io.StringIO()
    code = main(["play", *argv], stdin=io.StringIO("quit\n"), stdout=out, stderr=err)
    return code, out.getvalue()


def test_play_color_always_and_never(monkeypatch, tmp_path):
    code, out = run_play(monkeypatch, tmp_path, "--puzzle", PUZZLE, "--color", "always")
    assert code == 0
    assert paint(GIVEN_STYLE, "3") in out
    code, out = run_play(monkeypatch, tmp_path, "--puzzle", PUZZLE, "--color", "never")
    assert code == 0
    assert "\x1b" not in out


def test_play_default_is_plain_when_piped(monkeypatch, tmp_path):
    monkeypatch.delenv("NO_COLOR", raising=False)
    code, out = run_play(monkeypatch, tmp_path, "--puzzle", PUZZLE)
    assert code == 0
    assert "\x1b" not in out


def test_placed_digit_is_highlighted_everywhere():
    game = new_game()
    game.handle("r1c2 7")
    text = game.board_text()
    assert paint(ENTRY_STYLE + ";" + FOCUS_STYLE, "7") in text  # the new entry
    assert paint(GIVEN_STYLE + ";" + FOCUS_STYLE, "7") in text  # a given 7
    assert text.count(";" + FOCUS_STYLE + "m") == game.values.count(7)
    assert paint(GIVEN_STYLE, "3") in text  # other digits untouched


def test_highlight_follows_the_last_placement_and_clears():
    game = new_game()
    game.handle("r1c2 7")
    game.handle("r1c4 2")
    text = game.board_text()
    assert text.count(";" + FOCUS_STYLE + "m") == game.values.count(2)
    game.handle("undo")
    assert ";" + FOCUS_STYLE + "m" not in game.board_text()
    game.handle("r1c2 7")
    game.handle("r1c2 0")
    assert ";" + FOCUS_STYLE + "m" not in game.board_text()


def test_highlight_is_off_without_colour():
    game = new_game(color=False)
    game.handle("r1c2 7")
    assert "\x1b" not in game.board_text()
