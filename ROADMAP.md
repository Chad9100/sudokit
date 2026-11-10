# Roadmap

Estimates are rough working hours for one person.

## v0.1 (done)

- [x] `sudokit solve`: 81-character strings, drawn grid files, stdin (BOM-safe),
      batch files with one puzzle per line, `--format grid|line`, `--explain`
- [x] Propagation plus search solver that reports no solution / several solutions
- [x] Human-style logic: singles, locked candidates, naked/hidden pairs and
      triples, X-wing, XY-wing, each step explained in words
- [x] `sudokit rate` (easy / medium / hard / expert)
- [x] `sudokit generate --difficulty --seed --count` with unique, symmetric puzzles
- [x] `sudokit hint` with the chain of eliminations leading to the next digit
- [x] `sudokit play`: placements, pencil marks, undo, hint, check, timer, reveal
- [x] pytest suite; CI on Ubuntu and Windows

## v0.2: saved games and stats (about 4 h)

- [x] `save` command and `sudokit resume`, JSON in a per-user data dir with a
      `SUDOKIT_HOME` override
- [ ] Finished games logged (difficulty, seed, time, hints, checks)
- [ ] `sudokit stats`: games per level, best and median times, hint-free streak

## v0.3: more techniques (about 5 h)

- [ ] Swordfish and finned X-wing
- [ ] XYZ-wing and simple colouring (single-digit chains)
- [ ] Hidden/naked quads
- [ ] An `expert` generator level built on these, with a time budget and a
      clear message when no puzzle is found in time
- [ ] A fixed benchmark set of rated puzzles to catch rating regressions

## v0.4: nicer terminal play (about 4 h)

- [ ] Colour (givens, your entries, clashes) with `--color auto|always|never`
      and `NO_COLOR`
- [ ] Highlight every cell holding the digit you just placed
- [ ] `marks` drawn as 3x3 mini-grids per cell when the terminal is wide enough
- [ ] `redo` to go with `undo`

## v0.5: import and export (about 3 h)

- [ ] Read the common `.sdk` and `.ss` puzzle file formats
- [ ] `sudokit print`: a plain-text sheet of several puzzles, with the
      solutions on a separate page, ready for a printer
- [ ] `--json` output for `solve`, `rate` and `hint` for use from scripts

## v1.0: release (about 4 h)

- [ ] Publish to PyPI with a trusted-publishing GitHub workflow
- [ ] Daily puzzle (`sudokit play --daily`) seeded from the date
- [ ] Shell completion scripts and a review of every `--help` text
- [ ] Profile the generator and cut hard-puzzle time in half

**Total for v0.2 to v1.0: about 20 hours.**
