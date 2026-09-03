"""Console-script wrappers around the bundled OKF tools.

The heavy lifting lives in `_scripts/` as two bash scripts and one Python
script; these wrappers put them on PATH under stable names and forward every
argument through, so the Agent Skill can call `okf-inventory` / `okf-history` /
`okf-validate` without knowing where the package was installed.

The bash scripts need `bash` and `git`. On Windows both ship with Git for
Windows, so we look for its `bash.exe` when `bash` is not already on PATH.
"""
import os
import shutil
import subprocess
import sys
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path

# Git for Windows installs bash here; checked only when PATH has no bash.
_WINDOWS_BASH_CANDIDATES = (
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
)


def _find_bash() -> str:
    found = shutil.which("bash")
    if found:
        return found
    for candidate in _WINDOWS_BASH_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    sys.exit(
        "okf: `bash` was not found on PATH.\n"
        "The inventory and history tools are bash scripts that shell out to git.\n"
        "On Windows, install Git for Windows (https://git-scm.com/download/win),\n"
        "which provides both git and bash."
    )


def _run_script(name: str, argv: list, interpreter: list) -> int:
    """Materialize a bundled script to a real path and exec it with argv."""
    with ExitStack() as stack:
        resource = files("catalogify._scripts").joinpath(name)
        path = stack.enter_context(as_file(resource))
        try:
            completed = subprocess.run([*interpreter, str(path), *argv], check=False)
        except OSError as exc:
            sys.exit(f"okf: could not run {name}: {exc}")
    return completed.returncode


def inventory(argv: list = None) -> int:
    """`okf-inventory` — deterministic repo inventory (+ git churn) as JSON."""
    return _run_script("okf-inventory.sh", list(sys.argv[1:] if argv is None else argv), [_find_bash()])


def history(argv: list = None) -> int:
    """`okf-history` — bounded per-path git history: the "why" behind a concept."""
    return _run_script("okf-history.sh", list(sys.argv[1:] if argv is None else argv), [_find_bash()])


def validate(argv: list = None) -> int:
    """`okf-validate` — OKF v0.1 §9 conformance checker for a bundle directory."""
    return _run_script("validate_okf.py", list(sys.argv[1:] if argv is None else argv), [sys.executable])


def main_inventory() -> int:
    return inventory()


def main_history() -> int:
    return history()


def main_validate() -> int:
    return validate()
