#!/usr/bin/env bash
# Build and upload a release to PyPI, in an isolated environment.
#
# Why this exists rather than "python3 -m build && twine upload dist/*":
# pyproject declares `license = "MIT"` (PEP 639 / SPDX), so setuptools>=77
# emits Metadata 2.4 with License-Expression and License-File. twine hands
# metadata parsing to `packaging`, and anything older than 24.2 rejects those
# fields with:
#
#   InvalidDistribution: unrecognized or malformed field 'license-file';
#   unrecognized or malformed field 'license-expression'
#
# The failure is in the *uploader's* dependencies, not in the artifact. A
# throwaway venv with current tools sidesteps whatever is installed globally.
#
# Usage:  ./scripts/publish.sh [--test]     # --test uploads to TestPyPI
set -euo pipefail
cd "$(dirname "$0")/.."

REPO_ARGS=()
[[ "${1:-}" == "--test" ]] && REPO_ARGS=(--repository testpypi)

VERSION="$(python3 -c 'import tomllib,sys; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null \
        || grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "catalogify $VERSION on branch $BRANCH"

if [[ "$BRANCH" != "main" ]]; then
  echo "  ! not on main. A published version should match main." >&2
  read -r -p "  continue anyway? [y/N] " ok; [[ "$ok" == "y" ]] || exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "  ! working tree is dirty; the upload would not match any commit." >&2
  read -r -p "  continue anyway? [y/N] " ok; [[ "$ok" == "y" ]] || exit 1
fi
if git ls-remote --tags origin | grep -q "refs/tags/v$VERSION$"; then
  echo "  note: tag v$VERSION already exists on origin."
fi

echo "==> building"
rm -rf dist build ./*.egg-info
python3 -m venv /tmp/catalogify-build
/tmp/catalogify-build/bin/pip install -q --upgrade pip build
/tmp/catalogify-build/bin/python -m build

echo "==> checking (isolated twine; your global one is probably too old)"
python3 -m venv /tmp/catalogify-publish
/tmp/catalogify-publish/bin/pip install -q --upgrade twine packaging
/tmp/catalogify-publish/bin/twine check dist/*

echo
ls -la dist/
echo
echo "A version cannot be reused once uploaded."
read -r -p "upload catalogify $VERSION to ${REPO_ARGS[*]:-PyPI}? [y/N] " ok
[[ "$ok" == "y" ]] || { echo "stopped."; exit 0; }

/tmp/catalogify-publish/bin/twine upload "${REPO_ARGS[@]}" dist/*
echo "==> uploaded. Remember: uv caches the index, so upgrading needs --refresh:"
echo "    uv tool install catalogify --force --refresh && catalogify install"
