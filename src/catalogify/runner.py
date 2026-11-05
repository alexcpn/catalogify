"""Console-script wrappers around the bundled OKF tools.

The heavy lifting lives in `_scripts/` as two bash scripts and one Python
script; these wrappers put them on PATH under stable names and forward every
argument through, so the Agent Skill can call `okf-inventory` / `okf-history` /
`okf-validate` without knowing where the package was installed.

The bash scripts need `bash` and `git`. On Windows both ship with Git for
Windows, so we look for its `bash.exe` when `bash` is not already on PATH.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path

# Git for Windows installs bash in one of these when git's own location does
# not give it away.
_WINDOWS_BASH_CANDIDATES = (
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
)

# C:\Windows\System32\bash.exe and the WindowsApps alias are WSL launchers, not
# a bash. With no Linux distribution installed they fail with
# "execvpe(/bin/bash) failed"; with one, the script runs inside WSL against a
# different git and python. They usually come first on PATH.
_WSL_LAUNCHER = re.compile(r"[\\/](system32|windowsapps)[\\/]", re.I)


def _git_for_windows_bash():
    """<Git for Windows root>/bin/bash.exe, found from where git.exe is.

    git.exe lives in <root>/cmd, <root>/bin or <root>/mingw64/bin, so the root
    is one of its first three ancestors.
    """
    git = shutil.which("git")
    if not git:
        return None
    for root in list(Path(git).resolve().parents)[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def _find_windows_bash():
    for candidate in (_git_for_windows_bash(), *_WINDOWS_BASH_CANDIDATES):
        if candidate and Path(candidate).is_file():
            return candidate
    found = shutil.which("bash")
    if found and not _WSL_LAUNCHER.search(found):
        return found
    return None


def _find_bash() -> str:
    found = _find_windows_bash() if os.name == "nt" else shutil.which("bash")
    if found:
        return found
    sys.exit(
        "okf: no usable `bash` was found.\n"
        "The inventory and history tools are bash scripts that shell out to git.\n"
        "On Windows, install Git for Windows (https://git-scm.com/download/win),\n"
        "which provides both git and bash. The bash.exe in System32 is a WSL\n"
        "launcher and is not used."
    )


# Scripts that import okf_bundle.py as a sibling module.
_NEEDS_BUNDLE_MODULE = {"verify_okf.py", "validate_okf.py", "okf_find.py"}


def _run_script(name: str, argv: list, interpreter: list) -> int:
    """Materialize a bundled script to a real path and exec it with argv.

    From an ordinary install the scripts are already files and run in place.
    From a zip or another non-filesystem loader, `as_file` would extract the
    one script alone, and a script that imports okf_bundle.py as a sibling
    would fail. So those are copied into one temporary directory together.
    """
    with ExitStack() as stack:
        package = files("catalogify._scripts")
        resource = package.joinpath(name)
        if name in _NEEDS_BUNDLE_MODULE and not isinstance(resource, Path):
            tmp = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            for part in (name, "okf_bundle.py"):
                (tmp / part).write_bytes(package.joinpath(part).read_bytes())
            path = tmp / name
        else:
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


def cochange(argv: list = None) -> int:
    """`okf-cochange` — directories that change together, mined from history."""
    return _run_script("okf-cochange.py", list(sys.argv[1:] if argv is None else argv), [sys.executable])


def find(argv: list = None) -> int:
    """`okf-find` — what the bundle knows about a file: guardrails, relations, playbooks."""
    return _run_script("okf_find.py", list(sys.argv[1:] if argv is None else argv), [sys.executable])


def verify(argv: list = None) -> int:
    """`okf-verify` — check a bundle's claims against the repository."""
    return _run_script("verify_okf.py", list(sys.argv[1:] if argv is None else argv), [sys.executable])


def validate(argv: list = None) -> int:
    """`okf-validate` — OKF v0.1 §9 conformance checker for a bundle directory."""
    return _run_script("validate_okf.py", list(sys.argv[1:] if argv is None else argv), [sys.executable])


def main_inventory() -> int:
    return inventory()


def main_history() -> int:
    return history()


def main_validate() -> int:
    return validate()


def main_cochange() -> int:
    return cochange()


def main_verify() -> int:
    return verify()


def main_find() -> int:
    return find()
