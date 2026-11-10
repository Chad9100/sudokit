"""The interactive, line-based game: state, commands and the input loop."""

from __future__ import annotations

import re
import time
from typing import Callable, Iterable, TextIO

from .grid import PEERS, cell_name, find_conflicts, format_grid
from .hints import hint_text

HELP_TEXT = """\
Commands:
  r3c5 7          put 7 in row 3, column 5 (also r3c5=7 or just 357)
  r3c5 0          clear that cell (also: clear r3c5)
  pencil r3c5 1 2 toggle pencil marks 1 and 2 in r3c5 (pencil r3c5 12 works too)
  pencil auto     fill in every possible candidate
  pencil clear    remove all pencil marks
  marks           show the pencil marks
  undo            take back the last change
  hint            explain the next logical step
  check           list mistakes and clashes
  show            draw the board again
  time            show the elapsed time
  reveal          show the solution and end the game
  help            show this help
  quit            leave the game (Ctrl+D / Ctrl+Z also works)"""

_PLACE = re.compile(r"^r\s*([1-9])\s*c\s*([1-9])\s*(?:=\s*|\s+)([0-9.])$")
_SHORT = re.compile(r"^([1-9])([1-9])([0-9.])$")
_CELL = re.compile(r"^r\s*([1-9])\s*c\s*([1-9])$")


def format_seconds(seconds: float) -> str:
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _parse_cell(text: str) -> int | None:
    m = _CELL.match(text.strip().lower())
    if not m:
        return None
    return (int(m.group(1)) - 1) * 9 + int(m.group(2)) - 1


class Game:
    def __init__(self, puzzle: list[int], solution: list[int], clock: Callable[[], float] = time.monotonic):
        self.puzzle = list(puzzle)
        self.solution = list(solution)
        self.values = list(puzzle)
        self.marks: list[set[int]] = [set() for _ in range(81)]
        self.history: list[tuple[list[int], list[set[int]]]] = []
        self.clock = clock
        self.started = clock()
        self.finished_at: float | None = None
        self.hints = 0
        self.checks = 0
        self.revealed = False

    # ---------------------------------------------------------- state

    def elapsed(self) -> float:
        end = self.finished_at if self.finished_at is not None else self.clock()
        return end - self.started

    def is_given(self, cell: int) -> bool:
        return bool(self.puzzle[cell])

    def solved(self) -> bool:
        return self.values == self.solution

    def over(self) -> bool:
        return self.finished_at is not None

    def _snapshot(self) -> None:
        self.history.append((self.values[:], [set(m) for m in self.marks]))

    def board_text(self) -> str:
        return format_grid(self.values, labels=True)

    def marks_text(self) -> str:
        """Every cell as its pencil marks (filled cells in brackets), 9x9."""
        texts = []
        for i in range(81):
            if self.values[i]:
                texts.append(f"[{self.values[i]}]")
            elif self.marks[i]:
                texts.append("".join(str(d) for d in sorted(self.marks[i])))
            else:
                texts.append(".")
        width = max(len(t) for t in texts)
        rule = "   " + "+".join("-" * (3 * (width + 1) + 1) for _ in range(3))
        lines = []
        for r in range(9):
            if r and r % 3 == 0:
                lines.append(rule)
            chunks = []
            for b in range(3):
                chunk = " ".join(texts[r * 9 + c].ljust(width) for c in range(b * 3, b * 3 + 3))
                chunks.append(" " + chunk + " ")
            lines.append(f"{r + 1}  " + "|".join(chunks).rstrip())
        return "\n".join(lines)

    # ------------------------------------------------------- commands

    def place(self, cell: int, digit: int) -> str:
        if self.is_given(cell):
            return f"{cell_name(cell)} is a given and cannot be changed."
        if self.values[cell] == digit:
            return f"{cell_name(cell)} is already {digit or 'empty'}."
        self._snapshot()
        self.values[cell] = digit
        if not digit:
            return f"Cleared {cell_name(cell)}."
        self.marks[cell].clear()
        for p in PEERS[cell]:
            self.marks[p].discard(digit)
        clash = sorted(p for p in PEERS[cell] if self.values[p] == digit)
        msg = f"{cell_name(cell)} = {digit}."
        if clash:
            msg += f" Careful: {digit} is also in " + ", ".join(cell_name(p) for p in clash) + "."
        if self.solved():
            self.finished_at = self.clock()
        return msg

    def pencil(self, args: list[str]) -> str:
        if not args:
            return "Usage: pencil r3c5 1 2 | pencil auto | pencil clear [r3c5]"
        if args[0] == "auto":
            self._snapshot()
            for i in range(81):
                if self.values[i]:
                    continue
                used = {self.values[p] for p in PEERS[i]}
                self.marks[i] = set(range(1, 10)) - used
            return "Filled in all candidates."
        if args[0] == "clear":
            if len(args) == 1:
                self._snapshot()
                self.marks = [set() for _ in range(81)]
                return "Removed all pencil marks."
            cell = _parse_cell("".join(args[1:]))
            if cell is None:
                return f"Not a cell: {' '.join(args[1:])} (use r3c5)."
            self._snapshot()
            self.marks[cell].clear()
            return f"Removed pencil marks from {cell_name(cell)}."
        cell = _parse_cell(args[0])
        rest = args[1:]
        if cell is None and len(args) >= 2:
            cell = _parse_cell(args[0] + args[1])
            rest = args[2:]
        if cell is None:
            return f"Not a cell: {args[0]} (use r3c5)."
        digits = "".join(rest)
        if not digits or not all(ch in "123456789" for ch in digits):
            return "Give the digits to toggle, e.g. pencil r3c5 1 2."
        if self.values[cell]:
            return f"{cell_name(cell)} is filled; clear it before pencilling."
        self._snapshot()
        for ch in digits:
            self.marks[cell] ^= {int(ch)}
        shown = "".join(str(d) for d in sorted(self.marks[cell])) or "none"
        return f"Pencil marks in {cell_name(cell)}: {shown}."

    def undo(self) -> str:
        if not self.history:
            return "Nothing to undo."
        self.values, self.marks = self.history.pop()
        return "Undone."

    def wrong_cells(self) -> list[int]:
        return [i for i in range(81) if self.values[i] and self.values[i] != self.solution[i]]

    def check(self) -> str:
        self.checks += 1
        lines = []
        for name, digit, cells in find_conflicts(self.values):
            lines.append(f"{digit} appears twice in {name}: " + ", ".join(cell_name(c) for c in cells))
        wrong = self.wrong_cells()
        if wrong:
            lines.append(f"{len(wrong)} wrong: " + ", ".join(cell_name(c) for c in wrong))
        empty = self.values.count(0)
        if not lines:
            lines.append(f"No mistakes so far. {empty} cell(s) to go.")
        return "\n".join(lines)

    def hint(self) -> str:
        self.hints += 1
        wrong = self.wrong_cells()
        if wrong:
            name = cell_name(wrong[0])
            return f"{name} is not right. Clear it ({name} 0) or undo, then ask again."
        return hint_text(self.values, self.solution)

    def reveal(self) -> str:
        self.revealed = True
        self.values = list(self.solution)
        self.finished_at = self.clock()
        return "Solution:\n" + self.board_text()

    def summary(self) -> str:
        parts = [f"Solved in {format_seconds(self.elapsed())}"]
        extras = []
        if self.hints:
            extras.append(f"{self.hints} hint(s)")
        if self.checks:
            extras.append(f"{self.checks} check(s)")
        if extras:
            parts.append(" with " + " and ".join(extras))
        return "".join(parts) + "."

    def handle(self, line: str) -> str | None:
        """Run one command. Returns the reply, or None to quit."""
        text = line.strip().lower()
        if not text:
            return ""
        words = text.split()
        cmd = words[0]
        if cmd in ("quit", "exit", "q"):
            return None
        m = _PLACE.match(text) or _SHORT.match(text)
        if m:
            cell = (int(m.group(1)) - 1) * 9 + int(m.group(2)) - 1
            digit = 0 if m.group(3) in "0." else int(m.group(3))
            reply = self.place(cell, digit)
            if self.over():
                return reply + "\n" + self.board_text() + "\n" + self.summary()
            return reply
        if cmd == "clear":
            cell = _parse_cell("".join(words[1:]))
            if cell is None:
                return "Usage: clear r3c5"
            return self.place(cell, 0)
        if cmd in ("pencil", "p"):
            return self.pencil(words[1:])
        if cmd == "marks":
            return self.marks_text()
        if cmd in ("undo", "u"):
            return self.undo() + "\n" + self.board_text()
        if cmd in ("hint", "h"):
            return self.hint()
        if cmd in ("check", "c"):
            return self.check()
        if cmd in ("show", "board", "s"):
            return self.board_text()
        if cmd in ("time", "t"):
            return f"Elapsed: {format_seconds(self.elapsed())}"
        if cmd == "reveal":
            return self.reveal()
        if cmd in ("help", "?"):
            return HELP_TEXT
        return f"Unknown command: {line.strip()}. Type help for the list."


def play(game: Game, lines: Iterable[str], out: TextIO, echo: bool = False, header: str = "") -> int:
    """Run the game loop over input ``lines``. Returns an exit status."""
    if header:
        out.write(header + "\n")
    out.write(game.board_text() + "\n")
    out.write("Type help for commands.\n")
    first = True
    it = iter(lines)
    while not game.over():
        out.write(f"[{format_seconds(game.elapsed())}] > ")
        out.flush()
        try:
            line = next(it)
        except StopIteration:
            out.write("\nBye.\n")
            return 0
        if first:
            line = line.lstrip("﻿")
            first = False
        line = line.rstrip("\r\n")
        if echo:
            out.write(line + "\n")
        reply = game.handle(line)
        if reply is None:
            out.write("Bye.\n")
            return 0
        if reply:
            out.write(reply + "\n")
    return 0
