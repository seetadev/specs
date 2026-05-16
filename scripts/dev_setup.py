"""Helpers for libp2p specs local development setup scripts."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Sequence

MIN_PYTHON = (3, 10)

PYTHON_CANDIDATES: Sequence[str] = (
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
    "python3",
    "python",
)


def python_version_for(command: str) -> tuple[int, int] | None:
    path = shutil.which(command)
    if path is None:
        return None
    try:
        completed = subprocess.run(
            [path, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    major_s, _, minor_s = completed.stdout.strip().partition(".")
    try:
        return int(major_s), int(minor_s)
    except ValueError:
        return None


def is_compatible(version: tuple[int, int], minimum: tuple[int, int] = MIN_PYTHON) -> bool:
    return version >= minimum


def find_compatible_python(
    candidates: Sequence[str] = PYTHON_CANDIDATES,
    minimum: tuple[int, int] = MIN_PYTHON,
) -> str | None:
    for command in candidates:
        version = python_version_for(command)
        if version is not None and is_compatible(version, minimum):
            return shutil.which(command) or command
    return None


def main() -> int:
    found = find_compatible_python()
    if found is None:
        print("No Python >= 3.10 found. Install Python 3.10+ or set PATH.", file=sys.stderr)
        return 1
    print(found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
