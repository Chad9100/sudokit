import io

from sudokit.cli import main
from sudokit.stats import format_summary, summarize
from sudokit.storage import append_history, history_path

# Made by `sudokit generate --difficulty easy --seed 7 --format line`.
PUZZLE = "..43.7.98....894.51......7.4.2.365.....8.5.....521.7.9.6......79.167....74.9.12.."
SOLUTION = "254367198376189425189542673492736581617895342835214769563428917921673854748951236"


def run(*argv, commands=()):
    out, err = io.StringIO(), io.StringIO()
    stdin = io.StringIO("".join(c + "\n" for c in commands))
    code = main(list(argv), stdin=stdin, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def game(difficulty="easy", seconds=100.0, hints=0, revealed=False):
    return {"version": 1, "difficulty": difficulty, "seconds": seconds, "hints": hints,
            "checks": 0, "revealed": revealed}


def test_summarize_levels_times_and_streaks():
    records = [
        game("easy", 300.0), game("easy", 100.0), game("easy", 200.0, hints=2),
        game("hard", 900.0, revealed=True), game("medium", 400.0), game("medium", 500.0),
        game(None, 50.0), game("easy", 120.0), game("easy", 999.0, revealed=True),
        game("easy", 130.0), game("medium", 600.0),
    ]
    s = summarize(records)
    assert s.games == 11
    easy = s.levels["easy"]
    assert (easy.solved, easy.revealed) == (5, 1)
    assert easy.best == 100.0 and easy.median == 130.0   # revealed time not counted
    assert s.levels["medium"].median == 500.0
    assert (s.levels["hard"].solved, s.levels["hard"].best) == (0, None)
    assert s.levels["own"].solved == 1
    # medium 400, medium 500, own, easy 120 in a row; then reveal; then two more.
    assert (s.streak, s.best_streak) == (2, 4)


def test_summarize_tolerates_odd_records():
    s = summarize([{"version": 1}, {"version": 1, "difficulty": "easy", "seconds": "fast", "hints": 0},
                   {"version": 1, "difficulty": "easy", "seconds": True, "hints": 0}])
    assert s.levels["own"].solved == 1 and s.levels["easy"].times == []
    assert (s.streak, s.best_streak) == (2, 2)   # a missing hints field breaks the streak


def test_format_summary_table():
    text = format_summary(summarize([
        game(None, 50.0), game("hard", 3725.0, hints=1), game("easy", 65.0),
        game("easy", 125.0), game("medium", 10.0, revealed=True),
    ]))
    assert text.splitlines() == [
        "Games: 5 (4 solved, 1 revealed)",
        "",
        "Level   Solved  Revealed     Best   Median",
        "easy         2         0    01:05    01:35",
        "medium       0         1        -        -",
        "hard         1         0  1:02:05  1:02:05",
        "own          1         0    00:50    00:50",
        "",
        "Hint-free streak: 0 (best 2)",
    ]


def test_stats_command_with_no_history(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path))
    code, out, err = run("stats")
    assert code == 0 and err == ""
    assert out == f"No finished games yet (the history is kept in {tmp_path / 'history.jsonl'}).\n"


def test_stats_command_after_real_games(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path))
    moves = [f"r{i // 9 + 1}c{i % 9 + 1} {SOLUTION[i]}" for i in range(81) if PUZZLE[i] == "."]
    run("play", "-d", "easy", "--seed", "7", commands=moves)
    run("play", "-d", "easy", "--seed", "7", commands=["reveal"])
    run("play", "-d", "easy", "--seed", "7", commands=moves)
    with open(history_path(), "a", encoding="utf-8") as fh:
        fh.write("not json\n")
    code, out, err = run("stats")
    assert code == 0
    assert err == f"sudokit: skipped 1 unreadable line(s) in {history_path()}\n"
    lines = out.splitlines()
    assert lines[0] == "Games: 3 (2 solved, 1 revealed)"
    assert lines[3].split()[:3] == ["easy", "2", "1"]
    assert lines[-1] == "Hint-free streak: 1 (best 1)"


def test_stats_command_unreadable_history(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path))
    history_path().mkdir()   # a directory where the file should be
    code, out, err = run("stats")
    assert code == 2 and out == ""
    assert err.startswith("sudokit: cannot read the history in ")


def test_append_then_stats_counts_own_puzzles(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDOKIT_HOME", str(tmp_path))
    append_history({"difficulty": None, "seconds": 42.0, "hints": 0, "revealed": False}, history_path())
    code, out, _ = run("stats")
    assert code == 0 and out.splitlines()[3].split() == ["own", "1", "0", "00:42", "00:42"]
