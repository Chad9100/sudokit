"""Summaries of the game history for ``sudokit stats``."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Iterable

from .game import format_seconds

LEVELS = ("easy", "medium", "hard")
OWN = "own"   # games started with --puzzle (no difficulty logged)


@dataclass
class LevelStats:
    solved: int = 0
    revealed: int = 0
    times: list[float] = field(default_factory=list)

    @property
    def best(self) -> float | None:
        return min(self.times) if self.times else None

    @property
    def median(self) -> float | None:
        return statistics.median(self.times) if self.times else None


@dataclass
class Summary:
    levels: dict[str, LevelStats]
    streak: int        # hint-free solves in a row, ending with the latest game
    best_streak: int

    @property
    def games(self) -> int:
        return sum(s.solved + s.revealed for s in self.levels.values())


def _level(record: dict[str, Any]) -> str:
    level = record.get("difficulty")
    return level if isinstance(level, str) and level else OWN


def _seconds(record: dict[str, Any]) -> float | None:
    value = record.get("seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def summarize(records: Iterable[dict[str, Any]]) -> Summary:
    """Tally ``records`` (oldest first, as ``read_history`` returns them).

    Times only count for solved games. A game counts towards the hint-free
    streak when it was solved without a hint; a revealed game or one where a
    hint was used ends the streak. Checks do not.
    """
    levels: dict[str, LevelStats] = {}
    streak = best_streak = 0
    for record in records:
        stats = levels.setdefault(_level(record), LevelStats())
        if record.get("revealed"):
            stats.revealed += 1
            streak = 0
            continue
        stats.solved += 1
        seconds = _seconds(record)
        if seconds is not None:
            stats.times.append(seconds)
        if record.get("hints") == 0:
            streak += 1
            best_streak = max(best_streak, streak)
        else:
            streak = 0
    return Summary(levels, streak, best_streak)


def _order(name: str) -> tuple[int, str]:
    if name in LEVELS:
        return LEVELS.index(name), ""
    return (len(LEVELS) + 1, "") if name == OWN else (len(LEVELS), name)


def _time(seconds: float | None) -> str:
    return "-" if seconds is None else format_seconds(seconds)


def format_summary(summary: Summary) -> str:
    rows = [("Level", "Solved", "Revealed", "Best", "Median")]
    for name in sorted(summary.levels, key=_order):
        s = summary.levels[name]
        rows.append((name, str(s.solved), str(s.revealed), _time(s.best), _time(s.median)))
    widths = [max(len(row[i]) for row in rows) for i in range(5)]
    solved = sum(s.solved for s in summary.levels.values())
    lines = [f"Games: {summary.games} ({solved} solved, {summary.games - solved} revealed)", ""]
    for row in rows:
        cells = [row[0].ljust(widths[0])] + [cell.rjust(w) for cell, w in zip(row[1:], widths[1:])]
        lines.append("  ".join(cells).rstrip())
    lines += ["", f"Hint-free streak: {summary.streak} (best {summary.best_streak})"]
    return "\n".join(lines)
