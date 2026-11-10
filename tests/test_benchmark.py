"""Rating regression check against a fixed set of sudokit-made puzzles.

``tests/data/benchmark.txt`` holds one ``level puzzle`` pair per line, made with
``sudokit generate --difficulty LEVEL --seed N --format line``. If a logic
change moves any puzzle to another level, this test fails.
"""

from pathlib import Path

import pytest

from sudokit.grid import parse
from sudokit.logic import rate
from sudokit.solver import solve

DATA = Path(__file__).parent / "data" / "benchmark.txt"
ENTRIES = [line.split() for line in DATA.read_text().splitlines() if line.strip()]


def test_benchmark_covers_every_generated_level():
    assert {level for level, _ in ENTRIES} == {"easy", "medium", "hard"}
    assert len(ENTRIES) >= 12


@pytest.mark.parametrize("level,text", ENTRIES, ids=[f"{lv}-{i}" for i, (lv, _) in enumerate(ENTRIES)])
def test_benchmark_puzzle_keeps_its_rating(level, text):
    cells = parse(text)
    assert solve(cells).status == "unique"
    assert rate(cells).name == level
