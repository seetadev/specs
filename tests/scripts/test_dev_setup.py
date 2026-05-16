import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from dev_setup import (  # noqa: E402
    MIN_PYTHON,
    find_compatible_python,
    is_compatible,
    python_version_for,
)


def test_is_compatible_accepts_minimum() -> None:
    assert is_compatible((3, 10), MIN_PYTHON)
    assert is_compatible((3, 12), MIN_PYTHON)


def test_is_compatible_rejects_older_python() -> None:
    assert not is_compatible((3, 9), MIN_PYTHON)


def test_find_compatible_python_returns_current_interpreter() -> None:
    found = find_compatible_python(candidates=("python",))
    assert found is not None
    version = python_version_for("python")
    assert version is not None
    assert is_compatible(version)
