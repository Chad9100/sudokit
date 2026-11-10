"""Command-line interface."""

from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import random
import sys
from typing import Sequence, TextIO

from . import __version__
from .game import Game, play
from .generator import GenerationError, generate
from .grid import (
    PuzzleFormatError,
    cell_name,
    clue_count,
    find_conflicts,
    format_grid,
    parse_many,
    to_line,
)
from .hints import describe, hint_text
from .logic import EXPERT, rate, solve_logically
from .solver import solve
from .stats import format_summary, summarize
from .storage import (
    SaveError,
    append_history,
    history_path,
    read_history,
    read_save,
    remove_save,
    save_path,
    write_save,
)

EXIT_OK, EXIT_UNSOLVED, EXIT_USAGE = 0, 1, 2


class InputError(Exception):
    pass


def _decode(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


def read_text(source: str | None, stdin: TextIO) -> str:
    """Text of a puzzle argument: a file, a literal puzzle, or stdin (``-``)."""
    if source is None or source == "-":
        if source is None and stdin.isatty():
            raise InputError("give a puzzle: an 81-character string, a file, or pipe it in")
        buffer = getattr(stdin, "buffer", None)
        text = _decode(buffer.read()) if buffer is not None else stdin.read()
        return text.lstrip("﻿")
    if os.path.isfile(source):
        with open(source, "rb") as fh:
            return _decode(fh.read())
    return source


def load_puzzles(source: str | None, stdin: TextIO) -> list[list[int]]:
    text = read_text(source, stdin)
    try:
        return parse_many(text)
    except PuzzleFormatError as exc:
        if source not in (None, "-") and not os.path.exists(source) and len(source) < 60:
            raise InputError(f"{source!r} is neither a file nor a puzzle ({exc})") from None
        raise InputError(str(exc)) from None


def load_one(source: str | None, stdin: TextIO) -> list[int]:
    puzzles = load_puzzles(source, stdin)
    if len(puzzles) != 1:
        raise InputError(f"expected one puzzle, found {len(puzzles)}")
    return puzzles[0]


def _render(cells: Sequence[int], fmt: str) -> str:
    return to_line(cells) if fmt == "line" else format_grid(cells)


def _no_solution_reason(cells: Sequence[int]) -> str:
    conflicts = find_conflicts(cells)
    if conflicts:
        name, digit, where = conflicts[0]
        return f"no solution: {digit} appears more than once in {name} ({', '.join(cell_name(c) for c in where)})"
    return "no solution"


def _multiple_reason(first: Sequence[int], second: Sequence[int]) -> str:
    cell = next(i for i in range(81) if first[i] != second[i])
    return (f"more than one solution (for example {cell_name(cell)} can be "
            f"{min(first[cell], second[cell])} or {max(first[cell], second[cell])})")


# ------------------------------------------------------------- commands


def cmd_solve(args, stdin, out, err) -> int:
    puzzles = load_puzzles(args.puzzle, stdin)
    batch = len(puzzles) > 1
    status = EXIT_OK
    for n, cells in enumerate(puzzles, start=1):
        prefix = f"puzzle {n}: " if batch else ""
        result = solve(cells)
        if result.status == "none":
            err.write(f"sudokit: {prefix}{_no_solution_reason(cells)}\n")
            status = EXIT_UNSOLVED
            continue
        if result.status == "multiple":
            err.write(f"sudokit: {prefix}{_multiple_reason(result.solution, result.other)}\n")
            status = EXIT_UNSOLVED
            continue
        if args.explain:
            logic = solve_logically(cells)
            for i, step in enumerate(logic.steps, start=1):
                out.write(f"{i}. {describe(step)}\n")
            if not logic.solved:
                out.write(f"Stuck after {len(logic.steps)} step(s): the rest needs trial and error.\n")
        if batch and args.format != "line" and n > 1:
            out.write("\n")
        out.write(_render(result.solution, args.format) + "\n")
    return status


def cmd_rate(args, stdin, out, err) -> int:
    cells = load_one(args.puzzle, stdin)
    result = solve(cells)
    if result.status == "none":
        err.write(f"sudokit: {_no_solution_reason(cells)}\n")
        return EXIT_UNSOLVED
    if result.status == "multiple":
        err.write(f"sudokit: {_multiple_reason(result.solution, result.other)}; cannot rate it\n")
        return EXIT_UNSOLVED
    rating = rate(cells)
    line = f"Difficulty: {rating.name}"
    if rating.level == EXPERT:
        line += " (needs more than the techniques sudokit knows)"
    out.write(line + "\n")
    out.write(f"Clues: {clue_count(cells)}\n")
    techniques = ", ".join(f"{name} x{count}" for name, count in rating.techniques.items())
    out.write(f"Techniques: {techniques or 'none'}\n")
    return EXIT_OK


def cmd_generate(args, stdin, out, err) -> int:
    if args.count < 1:
        err.write("sudokit: --count must be at least 1\n")
        return EXIT_USAGE
    base = args.seed if args.seed is not None else random.SystemRandom().randrange(1_000_000)
    for n in range(args.count):
        seed = base + n
        try:
            puzzle = generate(args.difficulty, seed=seed)
        except GenerationError as exc:
            err.write(f"sudokit: {exc}\n")
            return EXIT_UNSOLVED
        if args.format == "line":
            out.write(to_line(puzzle.cells) + "\n")
            continue
        if n:
            out.write("\n")
        techniques = ", ".join(puzzle.techniques)
        out.write(f"# sudokit {puzzle.difficulty} puzzle, seed {seed}, {puzzle.clues} clues\n")
        out.write(f"# techniques: {techniques}\n")
        out.write(format_grid(puzzle.cells) + "\n")
    return EXIT_OK


def cmd_hint(args, stdin, out, err) -> int:
    cells = load_one(args.puzzle, stdin)
    out.write(hint_text(cells) + "\n")
    return EXIT_OK


def cmd_play(args, stdin, out, err) -> int:
    if args.puzzle is not None:
        cells = load_one(args.puzzle, io.StringIO())
        result = solve(cells)
        if result.status != "unique":
            reason = (_no_solution_reason(cells) if result.status == "none"
                      else _multiple_reason(result.solution, result.other))
            err.write(f"sudokit: cannot play this puzzle: {reason}\n")
            return EXIT_UNSOLVED
        solution = result.solution
        info: dict = {}
        header = f"sudokit: your puzzle, {clue_count(cells)} clues"
    else:
        seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1_000_000)
        puzzle = generate(args.difficulty, seed=seed)
        cells, solution = puzzle.cells, puzzle.solution
        info = {"difficulty": puzzle.difficulty, "seed": seed}
        header = f"sudokit: {puzzle.difficulty} puzzle, seed {seed}, {puzzle.clues} clues"
    return _run_game(Game(cells, solution, info=info), stdin, out, header)


def _describe_saved(game: Game) -> str:
    info = game.info
    if "difficulty" in info and "seed" in info:
        what = f"{info['difficulty']} puzzle, seed {info['seed']}"
    else:
        what = "your puzzle"
    return f"{what}, {game.values.count(0)} cell(s) to go"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_finished(game: Game, out: TextIO) -> None:
    record = {"finished": _utc_now(), **game.result()}
    try:
        append_history(record, history_path())
    except OSError as exc:
        out.write(f"Could not record the game in the history: {exc}\n")


def _run_game(game: Game, stdin: TextIO, out: TextIO, header: str) -> int:
    """Play ``game`` with saving wired up.

    A finished game (solved or revealed) is logged to the history and clears
    its save.
    """
    path = save_path()

    def saver(g: Game) -> str:
        try:
            write_save(g.to_dict(), path)
        except OSError as exc:
            return f"Could not save: {exc}"
        return f"Saved to {path}. Carry on later with: sudokit resume"

    game.saver = saver
    interactive = stdin.isatty()
    if not interactive and getattr(stdin, "buffer", None) is not None:
        stdin = io.TextIOWrapper(stdin.buffer, encoding="utf-8-sig", errors="replace")
    status = play(game, stdin, out, echo=not interactive, header=header)
    if game.over():
        _log_finished(game, out)
        try:
            saved = read_save(path)
        except SaveError:
            saved = None
        if saved is not None and saved.get("puzzle") == to_line(game.puzzle):
            remove_save(path)
    return status


def cmd_resume(args, stdin, out, err) -> int:
    path = save_path()
    try:
        data = read_save(path)
        game = Game.from_dict(data)
    except SaveError as exc:
        raise InputError(str(exc)) from None
    except ValueError as exc:
        raise InputError(f"the saved game in {path} is damaged: {exc}") from None
    header = f"sudokit: resuming {_describe_saved(game)}"
    return _run_game(game, stdin, out, header)


def cmd_stats(args, stdin, out, err) -> int:
    path = history_path()
    try:
        records, bad = read_history(path)
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read the history in {path}: {exc}") from None
    if bad:
        err.write(f"sudokit: skipped {bad} unreadable line(s) in {path}\n")
    if not records:
        out.write(f"No finished games yet (the history is kept in {path}).\n")
        return EXIT_OK
    out.write(format_summary(summarize(records)) + "\n")
    return EXIT_OK


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sudokit",
        description="Solve, generate, rate and play Sudoku in the terminal.",
    )
    parser.add_argument("--version", action="version", version=f"sudokit {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    puzzle_help = "81-character puzzle, a grid file, or - for stdin (the default)"

    p = sub.add_parser("solve", help="solve a puzzle (or one per line in a file)")
    p.add_argument("puzzle", nargs="?", help=puzzle_help)
    p.add_argument("--format", choices=["grid", "line"], default="grid", help="output style (default: grid)")
    p.add_argument("--explain", action="store_true", help="print the logical steps before the solution")
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("rate", help="rate a puzzle's difficulty")
    p.add_argument("puzzle", nargs="?", help=puzzle_help)
    p.set_defaults(func=cmd_rate)

    p = sub.add_parser("generate", help="make new puzzles with a unique solution")
    p.add_argument("--difficulty", "-d", choices=["easy", "medium", "hard"], default="medium")
    p.add_argument("--seed", type=int, help="seed for a repeatable puzzle")
    p.add_argument("--count", "-n", type=int, default=1, help="how many puzzles (seeds count up)")
    p.add_argument("--format", choices=["grid", "line"], default="grid")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("hint", help="explain the next logical step")
    p.add_argument("puzzle", nargs="?", help=puzzle_help)
    p.set_defaults(func=cmd_hint)

    p = sub.add_parser("play", help="play in the terminal")
    p.add_argument("--difficulty", "-d", choices=["easy", "medium", "hard"], default="medium")
    p.add_argument("--seed", type=int, help="seed for a repeatable puzzle")
    p.add_argument("--puzzle", help="play this puzzle instead (81-character string or file)")
    p.set_defaults(func=cmd_play)

    p = sub.add_parser("resume", help="carry on with the game you saved in play")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("stats", help="games per level, best and median times, hint-free streak")
    p.set_defaults(func=cmd_stats)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        return args.func(args, stdin, out, err)
    except InputError as exc:
        err.write(f"sudokit: {exc}\n")
        return EXIT_USAGE
    except KeyboardInterrupt:
        out.write("\n")
        return 130
