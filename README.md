# sudokit

A Sudoku toolkit for the terminal. It solves puzzles (and tells you when a
puzzle has no solution or more than one), generates new puzzles with a unique
solution at a chosen difficulty, rates puzzles by the solving techniques a
person would need, explains the next logical step as a hint, and lets you play
a game with pencil marks, undo and a timer.

**Who it is for:** people who like Sudoku and live in a terminal, and anyone
who wants a small, readable solver or puzzle source for scripts.

**Built with:** Python 3.10+ and the standard library only (no runtime
dependencies). Tests use pytest.

## Install

```sh
git clone https://github.com/Chad9100/sudokit.git
cd sudokit
python -m pip install .
```

That puts a `sudokit` command on your PATH. `python -m sudokit` works too.

## Puzzle input

Every command that takes a puzzle accepts any of these:

- an 81-character string, row by row, with `.`, `0` or `_` for empty cells;
- the path of a file holding a drawn grid (digits and `.`; spaces and the
  border characters `| - + = :` are ignored, as are lines starting with `#`);
- `-` or nothing at all, to read standard input.

A leading UTF-8 byte order mark (as written by Windows PowerShell and Notepad)
is ignored, both for puzzles and for commands piped into `sudokit play`.

## Usage

### Generate

```sh
sudokit generate [--difficulty easy|medium|hard] [--seed N] [--count N] [--format grid|line]
```

Puzzles have 180-degree rotational symmetry and exactly one solution. Without
`--seed` a random seed is picked and printed, so you can make the same puzzle
again; with `--count` the seeds count up from there. The output is real:

```text
$ sudokit generate --difficulty hard --seed 2026
# sudokit hard puzzle, seed 2026, 28 clues
# techniques: hidden single, naked single, box/line reduction, hidden pair, XY-wing
+-------+-------+-------+
| . 3 . | . 8 . | . 4 . |
| 1 . 4 | 7 . . | . . . |
| . . . | . . 2 | 5 . . |
+-------+-------+-------+
| . 8 . | 3 6 . | 4 . . |
| . 5 7 | . . . | 8 3 . |
| . . 1 | . 7 9 | . 5 . |
+-------+-------+-------+
| . . 6 | 1 . . | . . . |
| . . . | . . 7 | 2 . 4 |
| . 7 . | . 2 . | . 6 . |
+-------+-------+-------+
```

The examples below use this puzzle, saved as `puzzle.txt`. The `#` lines are
ignored when the grid is read back, so the output can go
straight into `solve`, `rate`, `hint` or `play --puzzle`. With `--format line`
you get one 81-character puzzle per line:

```text
$ sudokit generate --difficulty medium --seed 4 --count 3 --format line
7.6..951.8.....7...4..578....2...9.....3.1.....4...3....789..5...8.....7.536..2.8
.756...3.9..87....3....54...18....23.5.....4.43....18...47....1....89..4.9...436.
.....2..6278.15.4.6.....5.......675..6.5.1.8..574.......9.....2.2.83.1653..2.....
```

### Difficulty

Difficulty is the hardest technique a person needs, trying the simplest ones
first:

| Level  | Techniques                                                          |
|--------|---------------------------------------------------------------------|
| easy   | naked singles and hidden singles only (and at least 34 clues)       |
| medium | pointing pairs/triples, box/line reduction, naked and hidden pairs  |
| hard   | naked and hidden triples, X-wing, XY-wing                           |
| expert | none of the above is enough; needs trial and error (rated only)     |

The generator removes clues in symmetric pairs and keeps a removal only while
the puzzle can still be solved by logic at or below the target level. That
proves the solution is unique, and a finished puzzle that turns out easier
than asked for is thrown away. Typical times on a laptop are well under a
second for easy and medium and a second or two for hard.

```text
$ sudokit rate puzzle.txt
Difficulty: hard
Clues: 28
Techniques: hidden single x45, naked single x8, box/line reduction x1, hidden pair x2, XY-wing x2
$ sudokit rate ..6.1.......7..5..84....9.24..3....8...29...3..5.......82..5......82...631...7...
Difficulty: expert (needs more than the techniques sudokit knows)
Clues: 24
Techniques: hidden single x12, pointing pair x3, pointing triple x1, box/line reduction x1, naked pair x1, hidden pair x2
```

### Solve

```sh
sudokit solve [PUZZLE] [--format grid|line] [--explain]
```

The solver uses constraint propagation (naked and hidden singles over
candidate bitmasks) and a depth-first search on the cell with the fewest
candidates, so even puzzles beyond the logic techniques solve in a few
hundredths of a second. It always looks for a second solution.

```text
$ sudokit solve puzzle.txt
+-------+-------+-------+
| 2 3 5 | 9 8 1 | 7 4 6 |
| 1 9 4 | 7 5 6 | 3 2 8 |
| 7 6 8 | 4 3 2 | 5 9 1 |
+-------+-------+-------+
| 9 8 2 | 3 6 5 | 4 1 7 |
| 6 5 7 | 2 1 4 | 8 3 9 |
| 3 4 1 | 8 7 9 | 6 5 2 |
+-------+-------+-------+
| 8 2 6 | 1 4 3 | 9 7 5 |
| 5 1 3 | 6 9 7 | 2 8 4 |
| 4 7 9 | 5 2 8 | 1 6 3 |
+-------+-------+-------+
```

`--explain` prints the logical walkthrough first (`1. Hidden single: In box 4,
3 can only go in r6c1.` and so on), and says where logic got stuck for an
expert puzzle. A file with one 81-character puzzle per line is solved line by
line; with `--format line` that gives one solution per line.

Puzzles without exactly one solution are reported on stderr with exit status 1:

```text
$ sudokit solve 1................................................................................
sudokit: more than one solution (for example r8c3 can be 2 or 8)
$ sudokit solve 33...............................................................................
sudokit: no solution: 3 appears more than once in box 1 (r1c1, r1c2)
```

A grid can also have no solution without any visible clash; that is reported
as plain `no solution`. Unreadable input exits with status 2:

```text
$ sudokit solve puzle.txt
sudokit: 'puzle.txt' is neither a file nor a puzzle (unexpected character 'p' on line 1)
```

Piping works, including from PowerShell, which writes a byte order mark:

```text
$ sudokit generate -d easy --seed 1 --format line | sudokit solve --format line
639251748458367219172948536913574682527683194864192357791425863245836971386719425
```

### Hint

```sh
sudokit hint [PUZZLE]
```

Explains the next digit you can place and every elimination needed to get
there. A partly filled grid works as well as a fresh puzzle:

```text
$ sudokit hint .3.98..4.1.475..287.84.25...8.3654..6572..839341879652.261....5.1.6.72.4.7.52..6.
1. Hidden pair: In row 9, 4/8 fit only in r9c1, r9c6, so those cells hold nothing else; remove 3 from r9c6; 9 from r9c1.
2. XY-wing: r3c5 is 1/3; whichever it is, r3c8 (1/9) or r8c5 (3/9) must be 9, so remove 9 from r8c8.
3. Naked single: r8c8 can only be 8: every other digit is already in its row, column or box.
Next: r8c8 = 8.
```

If the grid repeats a digit or has no solution, the hint says so instead. If
no known technique applies, it names the most constrained cell and its value.

### Play

```sh
sudokit play [--difficulty easy|medium|hard] [--seed N] [--puzzle PUZZLE]
```

A line-based game: the board is drawn with row and column numbers and you
type commands at a prompt that shows the elapsed time.

| Command             | What it does                                         |
|---------------------|------------------------------------------------------|
| `r3c5 7`            | put 7 in row 3, column 5 (`r3c5=7` and `357` too)    |
| `r3c5 0`            | clear the cell (`clear r3c5` too)                    |
| `pencil r3c5 1 2`   | toggle pencil marks 1 and 2 (`pencil r3c5 12` too)   |
| `pencil auto`       | fill in every candidate                              |
| `pencil clear`      | remove all marks (`pencil clear r3c5` for one cell)  |
| `marks`             | show the pencil marks, filled cells in brackets      |
| `undo`              | take back the last change                            |
| `hint`              | explain the next step (or point at a wrong entry)    |
| `check`             | list clashes and entries that differ from the answer |
| `show`, `time`      | redraw the board, show the elapsed time              |
| `reveal`            | show the solution and end the game                   |
| `help`, `quit`      | list commands, leave (end of input also quits)       |

Givens cannot be changed. A digit that clashes with one in the same row,
column or box is allowed but flagged. Placing a digit clears it from the
pencil marks of every cell that sees it. Filling the grid correctly ends the
game with your time and how many hints and checks you used.

When commands are piped in, each one is echoed after the prompt so the output
reads as a transcript. Real output (the board is drawn first):

```text
$ printf 'r1c4 6\nr1c4 0\nhint\nr3c3 2\npencil r1c4 258\npencil r1c4 8\ncheck\nquit\n' | sudokit play --difficulty easy --seed 1
sudokit: easy puzzle, seed 1, 34 clues
    1 2 3   4 5 6   7 8 9
  +-------+-------+-------+
1 | 6 3 9 | . . 1 | . . . |
2 | . . 8 | . . 7 | . . 9 |
3 | 1 . . | 9 4 . | . 3 6 |
  +-------+-------+-------+
4 | 9 . 3 | . . . | . 8 . |
5 | . 2 . | 6 . 3 | . 9 . |
6 | . 6 . | . . . | 3 . 7 |
  +-------+-------+-------+
7 | 7 9 . | . 2 5 | . . 3 |
8 | 2 . . | 8 . . | 9 . . |
9 | . . . | 7 . . | 4 2 5 |
  +-------+-------+-------+
Type help for commands.
[00:00] > r1c4 6
r1c4 = 6. Careful: 6 is also in r1c1, r5c4.
[00:00] > r1c4 0
Cleared r1c4.
[00:00] > hint
Hidden single: In box 1, 2 can only go in r3c3.
Next: r3c3 = 2.
[00:00] > r3c3 2
r3c3 = 2.
[00:00] > pencil r1c4 258
Pencil marks in r1c4: 258.
[00:00] > pencil r1c4 8
Pencil marks in r1c4: 25.
[00:00] > check
No mistakes so far. 46 cell(s) to go.
[00:00] > quit
Bye.
```

## Exit status

| Code | Meaning                                                  |
|------|----------------------------------------------------------|
| 0    | success                                                  |
| 1    | the puzzle has no solution or more than one              |
| 2    | bad arguments or unreadable puzzle input                 |

## Development

```sh
python -m venv .venv
.venv/Scripts/activate        # or: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

The code lives in `src/sudokit/`: `grid.py` (geometry, parsing, drawing),
`solver.py` (propagation and search), `logic.py` (the human techniques and the
rating), `generator.py`, `hints.py`, `game.py` (the play loop) and `cli.py`.
CI runs the tests on Ubuntu and Windows with Python 3.10, 3.12 and 3.13.

See [ROADMAP.md](ROADMAP.md) for planned work.

## License

MIT. See [LICENSE](LICENSE).
