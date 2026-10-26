#!/usr/bin/env python3
"""build.py — assemble catalogify's Cursor plugin.

Cursor installs plugins straight from a Git repository, so unlike the Spec Kit
extension the built plugin is committed: `plugins/catalogify/`, listed by the
repo-level `.cursor-plugin/marketplace.json`. Nothing in it is edited by hand.
Change the sources and rebuild; CI runs `--check` and fails on any drift.

What goes into the built plugin
-------------------------------
  .cursor-plugin/plugin.json      this directory; version stamped from
                                  pyproject.toml
  README.md, assets/logo.svg      this directory
  LICENSE                         the repo root
  skills/catalogify/              src/catalogify/_skill_assets, verbatim: the
                                  same SKILL.md, references and examples that
                                  `catalogify install` copies

The skill is not transformed. When the `catalogify` CLI is not on PATH, which
is the normal case after a plugin install, SKILL.md itself tells the agent to
run the commands through `uvx catalogify@<version>`.

Usage
-----
  integrations/cursor/build.py            # rewrite plugins/catalogify/
  integrations/cursor/build.py --check    # exit 1 if it is out of date
  ln -s "$PWD/plugins/catalogify" ~/.cursor/plugins/local/catalogify   # try it
"""

import argparse
import filecmp
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / "src" / "catalogify" / "_skill_assets"
OUT = ROOT / "plugins" / "catalogify"

# The same exclusions as installer._ASSET_EXCLUDES: package plumbing, not skill.
_ASSET_EXCLUDES = shutil.ignore_patterns("__init__.py", "__pycache__", "*.pyc")


def version():
    for line in (ROOT / "pyproject.toml").read_text().splitlines():
        if line.startswith("version"):
            return line.split('"')[1]
    raise SystemExit("build: no version in pyproject.toml")


def build(out):
    ver = version()
    root_skill = (ROOT / "SKILL.md").read_bytes()
    if root_skill != (ASSETS / "SKILL.md").read_bytes():
        raise SystemExit("build: SKILL.md and src/catalogify/_skill_assets/SKILL.md differ")
    if f'version: "{ver}"' not in root_skill.decode():
        raise SystemExit(f"build: SKILL.md metadata.version is not {ver} (pyproject.toml)")

    if out.exists():
        shutil.rmtree(out)
    (out / ".cursor-plugin").mkdir(parents=True)
    (out / "assets").mkdir()

    manifest = json.loads((HERE / "plugin.json").read_text())
    manifest["version"] = ver
    (out / ".cursor-plugin" / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy2(HERE / "README.md", out / "README.md")
    shutil.copy2(HERE / "logo.svg", out / "assets" / "logo.svg")
    shutil.copy2(ROOT / "LICENSE", out / "LICENSE")
    shutil.copytree(ASSETS, out / "skills" / "catalogify", ignore=_ASSET_EXCLUDES)
    return ver


def _diff(a, b, rel=""):
    """Paths that differ between two trees, relative to their roots."""
    cmp = filecmp.dircmp(a, b, ignore=[])
    found = [f"{rel}{n}" for n in cmp.left_only + cmp.right_only + cmp.funny_files]
    found += [f"{rel}{n}" for n in cmp.common_files if not filecmp.cmp(a / n, b / n, shallow=False)]
    for sub in cmp.common_dirs:
        found += _diff(a / sub, b / sub, f"{rel}{sub}/")
    return found


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help=f"Build to a temporary directory and fail if {OUT.relative_to(ROOT)} differs")
    args = ap.parse_args()

    if not args.check:
        ver = build(OUT)
        print(f"built Cursor plugin catalogify {ver} in {OUT.relative_to(ROOT)}")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "catalogify"
        build(fresh)
        stale = _diff(fresh, OUT) if OUT.exists() else ["(missing)"]
    if stale:
        print(f"{OUT.relative_to(ROOT)} is out of date; run integrations/cursor/build.py and commit:", file=sys.stderr)
        for path in stale:
            print(f"  {path}", file=sys.stderr)
        return 1
    print(f"{OUT.relative_to(ROOT)} is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
