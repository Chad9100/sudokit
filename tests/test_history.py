import io
import json

from sudokit.cli import main
from sudokit.game import Game
from sudokit.grid import parse
from sudokit.storage import append_history, history_path, read_history

# Made by `sudokit generate --difficulty easy --seed 7 --format line`.
PUZZLE = "..43.7.98....894.51......7.4.2.365.....8.5.....521.7.9.6......79.167....74.9.12.."
SOLUTION = "254367198376189425189542673492736581617895342835214769563428917921673854748951236"


def run(*argv, commands=()):
    out, err = io.StringIO(), io.StringIO()
    stdin = io.StringIO("".join(c + "\n" for c in commands))
    code = main(list(argv), stdin=stdin, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def missing_moves():
    return [f"r{i // 9 + 1}c{i % 9 + 1} {SOLUTION[i]}" for i in range(81) if PUZZLE[i] == "."]


def test_game_result_record():
    t = [10.0]
    game = Game(parse(PUZZLE), parse(SOLUTION), clock=lambda: t[0], info={"difficulty": "easy", "seed": 7})
    game.handle("hint")
    game.handle("check")
    game.handle("check")
    t[0] += 61.26
    assert game.result() == {
        "difficulty": "easy", "seed": 7, "puzzle": PUZZLE, "seconds": 61.3,
        "hints": 1, "checks": 2, "revealed": False,
    }


def test_history_append_and_read_skips_damaged_lines(tmp_path):
    path = tmp_path / "data" / "history.jsonl"
    assert read_history(path) == ([], 0)
    append_history({"seconds": 1.0}, path)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"version": 1, "seconds": 2\n')   # cut short
        fh.write('{"version": 9}\n')                 # unknown format
        fh.write("\n")
    append_history({"seconds": 3.0}, path)
    records, bad = read_history(path)
    assert [r["seconds"] for r in records] == [1.0, 3.0]
    assert bad == 2


def test_solved_game_is_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path / "home"))
    code, out, _ = run("play", "-d", "easy", "--seed", "7", commands=["hint", "check"] + missing_moves())
    assert code == 0 and "Solved in" in out
    assert history_path() == tmp_path / "home" / "history.jsonl"
    lines = history_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    finished = record.pop("finished")
    assert len(finished) == 20 and finished.endswith("Z") and finished[10] == "T"
    seconds = record.pop("seconds")
    assert isinstance(seconds, float) and seconds >= 0
    assert record == {"version": 1, "difficulty": "easy", "seed": 7, "puzzle": PUZZLE,
                      "hints": 1, "checks": 1, "revealed": False}


def test_revealed_and_own_puzzles_are_logged_and_quitting_is_not(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path))
    run("play", "-d", "easy", "--seed", "7", commands=["r1c1 2", "quit"])
    assert read_history(history_path()) == ([], 0)
    run("play", "-d", "easy", "--seed", "7", commands=["reveal"])
    run("play", "--puzzle", SOLUTION[:-1] + ".", commands=["r9c9 6"])
    records, bad = read_history(history_path())
    assert bad == 0
    assert [(r["difficulty"], r["seed"], r["revealed"]) for r in records] == [
        ("easy", 7, True), (None, None, False)]
    assert records[1]["puzzle"] == SOLUTION[:-1] + "."


def test_resumed_game_is_logged_with_its_counters(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path))
    run("play", "-d", "easy", "--seed", "7", commands=["hint", "save"])
    run("resume", commands=["check"] + missing_moves())
    records, _ = read_history(history_path())
    assert len(records) == 1
    assert (records[0]["hints"], records[0]["checks"]) == (1, 1)


def test_history_write_failure_is_reported_not_fatal(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("SUDOKIT_HOME", str(blocker / "home"))
    code, out, _ = run("play", "--puzzle", SOLUTION[:-1] + ".", commands=["r9c9 6"])
    assert code == 0
    assert "Solved in" in out and "Could not record the game in the history:" in out
