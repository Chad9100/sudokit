import json
import io
import subprocess
import sys

from sudokit import __version__
from sudokit.cli import main
from sudokit.grid import parse, to_line
from sudokit.solver import solve

PUZZLE = "3.9...5..86579..4..4...8679.5.......7.4...8.1.......5.5231...9..9..52183..6...7.5"
SOLUTION = "379264518865791342241538679958416237734925861612873954523187496497652183186349725"
EXPERT = "..6.1.......7..5..84....9.24..3....8...29...3..5.......82..5......82...631...7..."


class BytesStdin(io.TextIOWrapper):
    """A piped stdin: not a TTY, with a binary ``buffer``."""

    def __init__(self, data: bytes):
        super().__init__(io.BytesIO(data), encoding="utf-8")


def run(*argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    code = main(list(argv), stdin=stdin or io.StringIO(""), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


# --------------------------------------------------------------- solve


def test_solve_string_prints_grid():
    code, out, _ = run("solve", PUZZLE)
    assert code == 0
    assert parse(out) == parse(SOLUTION)
    assert out.splitlines()[1] == "| 3 7 9 | 2 6 4 | 5 1 8 |"


def test_solve_line_format():
    assert run("solve", PUZZLE, "--format", "line")[1] == SOLUTION + "\n"


def test_solve_file_and_batch(tmp_path):
    single = tmp_path / "one.txt"
    single.write_text("# my puzzle\n" + "\n".join(PUZZLE[i:i + 9] for i in range(0, 81, 9)) + "\n")
    assert run("solve", str(single), "--format", "line")[1] == SOLUTION + "\n"
    batch = tmp_path / "many.txt"
    batch.write_text(f"{PUZZLE}\n{EXPERT}\n")
    code, out, _ = run("solve", str(batch), "--format", "line")
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == SOLUTION and lines[1] == to_line(solve(parse(EXPERT)).solution)


def test_solve_stdin_with_bom():
    code, out, err = run("solve", "--format", "line", stdin=BytesStdin(b"\xef\xbb\xbf" + PUZZLE.encode() + b"\r\n"))
    assert code == 0, err
    assert out == SOLUTION + "\n"


def test_solve_reports_multiple_solutions():
    almost_empty = "1" + "." * 80
    code, out, err = run("solve", almost_empty)
    assert code == 1 and out == ""
    assert "more than one solution (for example r" in err


def test_solve_reports_no_solution():
    clash = "33" + PUZZLE[2:]
    code, _, err = run("solve", clash)
    assert code == 1
    assert "no solution: 3 appears more than once in box 1 (r1c1, r1c2)" in err
    dead_end = PUZZLE[:4] + "1" + PUZZLE[5:]
    assert run("solve", dead_end)[2] == "sudokit: no solution\n"


def test_solve_batch_failure_is_numbered(tmp_path):
    batch = tmp_path / "many.txt"
    batch.write_text(f"{PUZZLE}\n{'1' + '.' * 80}\n")
    code, out, err = run("solve", str(batch), "--format", "line")
    assert code == 1 and out == SOLUTION + "\n"
    assert err.startswith("sudokit: puzzle 2: more than one solution")


def test_solve_bad_input():
    code, _, err = run("solve", "nofile.txt")
    assert code == 2
    assert "'nofile.txt' is neither a file nor a puzzle (unexpected character 'n' on line 1)" in err
    assert "expected 81 cells, found 80" in run("solve", PUZZLE[:-1])[2]


def test_solve_explain_lists_steps():
    code, out, _ = run("solve", PUZZLE, "--explain", "--format", "line")
    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("1. Hidden single: ")
    assert lines[-1] == SOLUTION
    stuck = run("solve", EXPERT, "--explain", "--format", "line")[1]
    assert "the rest needs trial and error" in stuck


# ------------------------------------------------------- rate and hint


def test_rate():
    code, out, _ = run("rate", PUZZLE)
    assert code == 0
    assert out.splitlines()[:2] == ["Difficulty: easy", "Clues: 34"]
    assert run("rate", EXPERT)[1].startswith("Difficulty: expert (needs more than")
    assert run("rate", "." * 81)[0] == 1


def test_rate_expert_puzzle_solved_by_swordfish():
    # sudokit-made (grid filler and clue removal, seed 93)
    fish = "5721.....9.........1.562......3.756...7.9.3...632.5......951.4.........6.....6895"
    code, out, _ = run("rate", fish)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "Difficulty: expert"
    assert "swordfish x1" in lines[2]


def test_hint_command():
    code, out, _ = run("hint", PUZZLE)
    assert code == 0 and "Next: r" in out


# ------------------------------------------------------------ generate


def test_generate_grid_output_can_be_solved():
    code, out, _ = run("generate", "--difficulty", "easy", "--seed", "4")
    assert code == 0
    assert out.startswith("# sudokit easy puzzle, seed 4, ")
    # the comment lines are ignored when reading it back
    assert run("solve", out, "--format", "line")[0] == 0


def test_generate_count_and_line_format():
    code, out, _ = run("generate", "-d", "medium", "--seed", "10", "-n", "2", "--format", "line")
    assert code == 0
    lines = out.splitlines()
    assert len(lines) == 2 and all(len(line) == 81 for line in lines)
    assert run("rate", lines[1])[1].startswith("Difficulty: medium")
    # seeds count up, so the second puzzle is the one seed 11 gives on its own
    assert run("generate", "-d", "medium", "--seed", "11", "--format", "line")[1].strip() == lines[1]


def test_generate_is_repeatable_and_rejects_bad_count():
    first = run("generate", "--seed", "21", "--format", "line")[1]
    assert first == run("generate", "--seed", "21", "--format", "line")[1]
    assert run("generate", "--count", "0")[0] == 2


# ---------------------------------------------------------------- play


def test_play_with_piped_commands_and_bom():
    data = "﻿r1c2 7\ncheck\nquit\n".encode("utf-8")
    code, out, _ = run("play", "--puzzle", PUZZLE, stdin=BytesStdin(data))
    assert code == 0
    assert out.startswith("sudokit: your puzzle, 34 clues\n")
    assert "> r1c2 7\nr1c2 = 7." in out
    assert "No mistakes so far. 46 cell(s) to go." in out


def test_play_generated_puzzle():
    code, out, _ = run("play", "-d", "easy", "--seed", "2", stdin=BytesStdin(b"quit\n"))
    assert code == 0
    assert out.startswith("sudokit: easy puzzle, seed 2, ")


def test_play_refuses_puzzle_without_unique_solution():
    code, _, err = run("play", "--puzzle", "." * 81)
    assert code == 1 and "cannot play this puzzle" in err


# ------------------------------------------------------------------ misc


def test_version_and_missing_command(capsys):
    assert run("--version")[0] == 0
    assert __version__ in capsys.readouterr().out
    assert run()[0] == 2


def test_module_entry_point():
    proc = subprocess.run(
        [sys.executable, "-m", "sudokit", "solve", PUZZLE, "--format", "line"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == SOLUTION


# ---------------------------------------------------------------- --json


def test_solve_json_object_per_puzzle():
    code, out, err = run("solve", PUZZLE, "--json")
    assert code == 0 and err == ""
    data = json.loads(out)
    assert data == {"puzzle": PUZZLE, "status": "solved", "solution": SOLUTION}


def test_solve_json_batch_and_explain():
    code, out, _ = run("solve", PUZZLE + "\n" + EXPERT, "--json", "--explain")
    assert code == 0
    first, second = [json.loads(line) for line in out.splitlines()]
    assert first["steps"] and first["stuck"] is False
    assert second["status"] == "solved" and len(second["solution"]) == 81


def test_solve_json_reports_failures_on_stdout():
    code, out, err = run("solve", "33" + "." * 79, "--json")
    assert code == 1 and err == ""
    data = json.loads(out)
    assert data["status"] == "none" and "box 1" in data["reason"]
    code, out, _ = run("solve", "1" + "." * 80, "--json")
    assert code == 1 and json.loads(out)["status"] == "multiple"


def test_rate_json():
    code, out, _ = run("rate", PUZZLE, "--json")
    data = json.loads(out)
    assert code == 0
    assert data["difficulty"] in ("easy", "medium", "hard", "expert")
    assert data["clues"] == 81 - PUZZLE.count(".")
    assert isinstance(data["techniques"], dict)
    code, out, _ = run("rate", "1" + "." * 80, "--json")
    assert code == 1 and json.loads(out)["status"] == "multiple"


def test_hint_json():
    code, out, _ = run("hint", PUZZLE, "--json")
    data = json.loads(out)
    assert code == 0 and data["puzzle"] == PUZZLE
    cell, digit = data["next"]["cell"], data["next"]["digit"]
    assert cell.startswith("r") and SOLUTION[(int(cell[1]) - 1) * 9 + int(cell[3]) - 1] == str(digit)
    assert data["hint"].endswith(f"Next: {cell} = {digit}.")
    code, out, _ = run("hint", SOLUTION, "--json")
    assert "next" not in json.loads(out)


def test_solve_reads_an_sdk_file(tmp_path):
    rows = [PUZZLE[i:i + 9] for i in range(0, 81, 9)]
    path = tmp_path / "p.sdk"
    path.write_text("#A Nobody\n[Puzzle]\n" + "\n".join(rows) + "\n", encoding="utf-8")
    code, out, _ = run("solve", str(path), "--format", "line")
    assert code == 0 and out == SOLUTION + "\n"
