"""Saved games: where they live and how they are read and written.

A game in progress is kept as one JSON file, ``saved.json``, in a per-user
data directory, and every finished game is appended as one JSON line to
``history.jsonl`` next to it. ``SUDOKIT_HOME`` overrides the directory (handy
for tests and for keeping several sets of saves apart).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

FORMAT_VERSION = 1
SAVE_NAME = "saved.json"
HISTORY_NAME = "history.jsonl"


class SaveError(Exception):
    """A saved game is missing, unreadable or does not make sense."""


def data_dir(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    """The directory sudokit keeps its files in (not created here)."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if env.get("SUDOKIT_HOME"):
        return Path(env["SUDOKIT_HOME"])
    home = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    if platform.startswith("win"):
        base = env.get("LOCALAPPDATA") or env.get("APPDATA")
        return Path(base) / "sudokit" if base else home / "AppData" / "Local" / "sudokit"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "sudokit"
    xdg = env.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else home / ".local" / "share") / "sudokit"


def save_path(env: Mapping[str, str] | None = None) -> Path:
    return data_dir(env) / SAVE_NAME


def history_path(env: Mapping[str, str] | None = None) -> Path:
    return data_dir(env) / HISTORY_NAME


def write_save(data: dict[str, Any], path: Path) -> None:
    """Write ``data`` to ``path`` atomically (a half-written save never replaces a good one)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = {"version": FORMAT_VERSION, **data}
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def read_save(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SaveError(f"no saved game (looked for {path})")
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise SaveError(f"cannot read the saved game in {path}: {exc}") from None
    if not isinstance(data, dict):
        raise SaveError(f"cannot read the saved game in {path}: not a JSON object")
    if data.get("version") != FORMAT_VERSION:
        raise SaveError(f"the saved game in {path} has unknown format version {data.get('version')!r}")
    return data


def remove_save(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def append_history(record: dict[str, Any], path: Path) -> None:
    """Add one finished game to the history file (one JSON object per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"version": FORMAT_VERSION, **record}, separators=(",", ":"))
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")


def read_history(path: Path) -> tuple[list[dict[str, Any]], int]:
    """The logged games, oldest first, and how many lines were unreadable.

    A missing file is an empty history. Damaged or foreign lines (for example
    a line cut short when the disk filled up) are skipped and counted, so one
    bad line never hides the rest.
    """
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return [], 0
    records, bad = [], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION:
            bad += 1
            continue
        records.append(data)
    return records, bad
