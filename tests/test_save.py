import io
import json

import pytest

from sudokit.cli import main
from sudokit.game import Game
from sudokit.grid import parse
from sudokit.storage import SaveError, data_dir, read_save, save_path, write_save

# Made by `sudokit generate --difficulty easy --seed 7 --format line`.
PUZZLE = "..43.7.98....894.51......7.4.2.365.....8.5.....521.7.9.6......79.167....74.9.12.."
SOLUTION = "254367198376189425189542673492736581617895342835214769563428917921673854748951236"


class Clock:
    def __init__(self):
        self.t = 50.0

    def __call__(self):
        return self.t


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def run(*argv, commands=()):
    out, err = io.StringIO(), io.StringIO()
    stdin = io.StringIO("".join(c + "\n" for c in commands))
    code = main(list(argv), stdin=stdin, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def missing_moves():
    return [f"r{i // 9 + 1}c{i % 9 + 1} {SOLUTION[i]}" for i in range(81) if PUZZLE[i] == "."]


# ------------------------------------------------------------ data dir


def test_data_dir_override_and_platform_defaults(tmp_path):
    assert data_dir({"SUDOKIT_HOME": str(tmp_path)}) == tmp_path
    assert data_dir({"LOCALAPPDATA": "C:/L"}, "win32").as_posix() == "C:/L/sudokit"
    assert data_dir({"HOME": "/h"}, "darwin").as_posix() == "/h/Library/Application Support/sudokit"
    assert data_dir({"HOME": "/h"}, "linux").as_posix() == "/h/.local/share/sudokit"
    assert data_dir({"HOME": "/h", "XDG_DATA_HOME": "/x"}, "linux").as_posix() == "/x/sudokit"


# ------------------------------------------------------- game round trip


def test_game_round_trip_keeps_board_marks_undo_and_counters():
    clock = Clock()
    game = Game(parse(PUZZLE), parse(SOLUTION), clock=clock, info={"difficulty": "easy", "seed": 7})
    game.handle("r1c1 2")
    game.handle("pencil r1c2 56")
    game.handle("hint")
    game.handle("check")
    clock.t += 95
    data = json.loads(json.dumps(game.to_dict()))

    later = Clock()
    back = Game.from_dict(data, clock=later)
    assert back.values == game.values and back.marks == game.marks
    assert (back.hints, back.checks, back.info) == (1, 1, {"difficulty": "easy", "seed": 7})
    assert back.handle("time") == "Elapsed: 01:35"
    later.t += 5
    assert back.handle("time") == "Elapsed: 01:40"
    back.handle("undo")
    assert back.marks[1] == set() and back.values[0] == 2
    back.handle("undo")
    assert back.values[0] == 0


@pytest.mark.parametrize("change, message", [
    ({"values": PUZZLE[:2] + "5" + PUZZLE[3:]}, "given"),
    ({"puzzle": "x" * 81}, "81-character"),
    ({"solution": "1" * 81}, "does not fit"),
    ({"marks": ["1"] * 80}, "marks"),
    ({"elapsed": -3}, "elapsed"),
])
def test_from_dict_rejects_damaged_data(change, message):
    data = Game(parse(PUZZLE), parse(SOLUTION)).to_dict()
    data.update(change)
    with pytest.raises(ValueError, match=message):
        Game.from_dict(data)


def test_save_without_a_saver():
    assert Game(parse(PUZZLE), parse(SOLUTION)).handle("save") == "Saving is not available here."


def test_read_save_errors(tmp_path):
    path = tmp_path / "saved.json"
    with pytest.raises(SaveError, match="no saved game"):
        read_save(path)
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(SaveError, match="cannot read"):
        read_save(path)
    path.write_text('{"version": 99}', encoding="utf-8")
    with pytest.raises(SaveError, match="format version 99"):
        read_save(path)


# ------------------------------------------------------------------ CLI


def test_play_save_then_resume(home):
    code, out, _ = run("play", "-d", "easy", "--seed", "7",
                       commands=["r1c1 2", "pencil r1c2 56", "save", "quit"])
    assert code == 0
    path = home / "saved.json"
    assert f"Saved to {path}. Carry on later with: sudokit resume" in out
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["puzzle"] == PUZZLE and data["values"][0] == "2"
    assert data["info"] == {"difficulty": "easy", "seed": 7}

    code, out, _ = run("resume", commands=["marks", "check", "quit"])
    assert code == 0
    assert out.startswith("sudokit: resuming easy puzzle, seed 7, 46 cell(s) to go\n")
    assert "1 | 2 . 4 | 3 . 7 |" in out
    assert "[2] 56" in out
    assert "No mistakes so far. 46 cell(s) to go." in out
    assert path.exists()  # quitting without saving keeps the old save


def test_finishing_a_resumed_game_removes_the_save(home):
    run("play", "-d", "easy", "--seed", "7", commands=["save"])
    assert save_path().exists()
    code, out, _ = run("resume", commands=missing_moves())
    assert code == 0 and "Solved in" in out
    assert not save_path().exists()
    code, _, err = run("resume")
    assert code == 2 and "no saved game" in err


def test_finishing_another_game_keeps_the_save(home):
    run("play", "-d", "easy", "--seed", "7", commands=["save"])
    run("play", "--puzzle", SOLUTION[:-1] + ".", commands=["r9c9 6"])
    assert save_path().exists()


def test_resume_reports_a_damaged_save(home):
    data = Game(parse(PUZZLE), parse(SOLUTION)).to_dict()
    data["values"] = PUZZLE[:2] + "5" + PUZZLE[3:]
    write_save(data, save_path())
    code, _, err = run("resume")
    assert code == 2
    assert "is damaged: a given was changed" in err
