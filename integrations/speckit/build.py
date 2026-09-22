#!/usr/bin/env python3
"""build.py — assemble catalogify's Spec Kit extension.

The Spec Kit extension (`specify extension add okf`) is catalogify packaged as
slash commands: /speckit.okf.generate, update, clarify, validate and verify.
Everything it runs and says comes from this repository — the scripts in
src/catalogify/_scripts and the workflow documents in
src/catalogify/_skill_assets — so a fix lands in the CLI, the skill and the
extension in one commit. Nothing generated here is committed.

What goes into the built extension
----------------------------------
  extension.yml, commands/verify.md    this directory; version stamped from
                                       pyproject.toml
  commands/{generate,update,clarify,validate}.md
                                       the workflow documents, transformed
  scripts/bash/*.sh, scripts/python/*.py
                                       the scripts, verbatim
  okf-config.template.yml              the template, with a Spec Kit header
  README.md, LICENSE                   from this directory and the repo root

How the transform works
-----------------------
The body of each workflow document is the same for the skill and the
extension. Only the wrapper differs: frontmatter, the H1, how arguments arrive,
and how a script or sibling workflow is named. Those differences are an ordered
list of literal substitutions.

Two safety nets, and either one stops the build loudly instead of emitting a
half-translated command:

  * **File rules must match.** A rule that targets a specific passage (config
    resolution, the producer stamp, a CLI mention) fails if that passage has
    been reworded. Common rules rename tokens and may not apply.
  * **No skill-only text may survive.** After the rules run, each command is
    scanned for `catalogify`, `SKILL.md`, `$BUNDLE_DIR` and the like
    (LEFTOVERS). New wording that no rule anticipated lands here.

When the build fails, fix the rules below, or reword the source document.

Usage
-----
  integrations/speckit/build.py                   # -> build/speckit-okf/
  integrations/speckit/build.py --zip             # ...and build/speckit-okf-<version>.zip
  specify extension add --dev build/speckit-okf   # try it in a Spec Kit project
"""

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / "src" / "catalogify" / "_skill_assets"
SCRIPTS_DIR = ROOT / "src" / "catalogify" / "_scripts"
# Not dist/: scripts/publish.sh uploads everything in dist/ to PyPI.
DEFAULT_OUT = ROOT / "build" / "speckit-okf"

# Scripts are copied byte for byte: the extension runs exactly what catalogify
# runs. Source name -> destination in the built extension.
SCRIPTS = {
    "okf-inventory.sh": "scripts/bash/okf-inventory.sh",
    "okf-history.sh": "scripts/bash/okf-history.sh",
    "okf-cochange.py": "scripts/python/okf-cochange.py",
    "validate_okf.py": "scripts/python/validate_okf.py",
    "verify_okf.py": "scripts/python/verify_okf.py",
}

WORKFLOWS = ["generate", "update", "clarify", "validate"]

# Where the scripts live once installed in a Spec Kit project.
EXT = ".specify/extensions/okf"


def _cmd(name):
    """How a script is invoked from a Spec Kit project.

    Always through an interpreter: Spec Kit extracts a zip install without
    file modes, so the installed .sh files are not executable.
    """
    sub = "bash" if name.endswith(".sh") else "python"
    call = "bash " if name.endswith(".sh") else "python3 "
    return f"{call}{EXT}/scripts/{sub}/{name}"


def version():
    for line in (ROOT / "pyproject.toml").read_text().splitlines():
        if line.startswith("version"):
            return line.split('"')[1]
    raise SystemExit("build: no version in pyproject.toml")


# --- Command wrappers ---------------------------------------------------------

COMMAND_DESCRIPTIONS = {
    "generate": "Generate an Open Knowledge Format (OKF v0.1) knowledge bundle from this repository's source code",
    "update": "Incrementally refresh an existing OKF knowledge bundle from changes since the last logged commit",
    "clarify": "Resolve the open questions an OKF knowledge bundle has parked for a human",
    "validate": "Validate the OKF knowledge bundle against the OKF v0.1 conformance rules and report findings",
}

COMMAND_TITLES = {
    "generate": "# /speckit.okf.generate — Bootstrap an OKF knowledge bundle",
    "update": "# /speckit.okf.update — Refresh an OKF knowledge bundle",
    "clarify": "# /speckit.okf.clarify — Resolve open questions with the user",
    "validate": "# /speckit.okf.validate — Conformance check",
}

COMMAND_ARGS = {
    "generate": "User input (optional focus/scope hints):",
    "update": "User input (optional scope hints):",
    "clarify": "User input (optional focus hints):",
    "validate": "User input (optional path override):",
}

# The skill's scope-hint paragraph becomes $ARGUMENTS.
SCOPE_HINTS = [
    "Scope hints: use any focus/scope the user gave (a subdirectory, a\n"
    "subsystem, a granularity preference); otherwise cover the whole repo.",
    "Scope hints: if the user named a bundle path, validate that one.",
    "Scope hints: if the user named a subdirectory or a concept, focus\nthere; otherwise cover the whole bundle.",
]


# --- Substitution rules -------------------------------------------------------
# A *file rule* targets a passage in one workflow document and must match
# there. A *common rule* renames a token that may or may not appear. Literal,
# not regex: a literal that stops matching is a signal worth stopping for.

_RESOLVE = f"Read `bundle_dir` from `{EXT}/okf-config.yml`"

FILE_RULES = {
    "generate": [
        ("1. Resolve `CONFIG` and `BUNDLE_DIR` as described in `SKILL.md`. If no\n"
         "   config file exists, use the defaults documented in\n"
         "   `okf-config.template.yml`, installed next to `SKILL.md`\n"
         "   (`bundle_dir: knowledge/`, `granularity: medium`).",
         f"1. Load configuration from `{EXT}/okf-config.yml` if\n"
         "   it exists; otherwise use the defaults in `okf-config.template.yml`\n"
         "   (`bundle_dir: knowledge/`, `granularity: medium`)."),
        ("`catalogify inventory`", "the inventory script"),
        ("that `catalogify clarify` walks", "that `/speckit.okf.clarify` walks"),
        # Bundles record which form produced them.
        ("generated_by: catalogify/0.9.0", "generated_by: speckit-okf/{version}"),
        ("with catalogify. <N> concepts", "with speckit-okf. <N> concepts"),
    ],
    "update": [
        ("Resolve `BUNDLE_DIR` and `CONFIG` as described in\n"
         "   `SKILL.md` (default bundle dir `knowledge/`). Read\n",
         _RESOLVE + "\n   (default `knowledge/`). Read\n"),
    ],
    "clarify": [
        ("Resolve `BUNDLE_DIR` and `CONFIG` as described in\n"
         "   `SKILL.md` (default bundle dir `knowledge/`). If it",
         _RESOLVE + "\n   (default `knowledge/`). If it"),
    ],
    "validate": [
        ("1. Resolve `CONFIG` and `BUNDLE_DIR` as described in\n"
         "   `SKILL.md`; a bundle path named by the user wins over the config.",
         "1. " + _RESOLVE + "\n"
         "   (default `knowledge/`); a bundle path named by the user wins over the\n"
         "   config."),
    ],
}

# Applied after the file rules, in order. Longer literals first.
COMMON_RULES = [
    ("catalogify inventory --config \"$CONFIG\"", f'{_cmd("okf-inventory.sh")} --config {EXT}/okf-config.yml'),
    ("catalogify inventory", _cmd("okf-inventory.sh")),
    ("catalogify history", _cmd("okf-history.sh")),
    ("catalogify cochange", _cmd("okf-cochange.py")),
    ("catalogify verify", _cmd("verify_okf.py")),
    ("catalogify validate", _cmd("validate_okf.py")),
    # Sibling workflows are slash commands here.
    ("the **generate** workflow", "`/speckit.okf.generate`"),
    ("the **update** workflow", "`/speckit.okf.update`"),
    ("the **clarify** workflow", "`/speckit.okf.clarify`"),
    ("the **validate** workflow", "`/speckit.okf.validate`"),
    ("**clarify** workflow", "`/speckit.okf.clarify`"),
    ("**update** workflow", "`/speckit.okf.update`"),
    ("the generate workflow", "`/speckit.okf.generate`"),
    # Config/bundle variables are lowercase config keys in the extension.
    ('"$CONFIG"', f"{EXT}/okf-config.yml"),
    ('"$BUNDLE_DIR"', "<bundle_dir>"),
    ("$BUNDLE_DIR", "<bundle_dir>"),
    ("`BUNDLE_DIR`", "`bundle_dir`"),
    ("`CONFIG`", "`okf-config.yml`"),
    ("$SKILL_DIR/", f"{EXT}/"),
]

# Skill-only text that must not survive into a command.
LEFTOVERS = ["catalogify", "SKILL.md", "$SKILL_DIR", "$BUNDLE_DIR", "$CONFIG", "`CONFIG`", "`BUNDLE_DIR`"]

# The template is written for the CLI and skill; the extension reads its config
# from its own install directory.
TEMPLATE_RULES = [
    ("# Configuration for catalogify.\n"
     "# Copy to .okf-config.yml in your repo root (or leave defaults).\n",
     "# Configuration for the OKF Spec Kit extension (built from catalogify).\n"
     f"# Copy to {EXT}/okf-config.yml (or leave defaults).\n"),
    ("  # clarify workflow behavior.", "  # /speckit.okf.clarify behavior."),
]


def apply_rules(text, label, required, common, leftovers):
    """Apply required then common substitutions; fail on a miss or a leftover."""
    missed = [old for old, _ in required if old not in text]
    if missed:
        raise SystemExit(
            f"build: {label} — {len(missed)} required substitution(s) no longer match.\n"
            "A passage this transform depends on has been reworded. Update the rules\n"
            "in integrations/speckit/build.py to match.\n\n"
            + "\n".join(f"  missing: {m[:90]!r}" for m in missed))
    for old, new in [*required, *common]:
        text = text.replace(old, new)
    left = [f"  line {n}: {token!r} in {line.strip()[:80]!r}"
            for n, line in enumerate(text.splitlines(), 1)
            for token in leftovers if token in line]
    if left:
        raise SystemExit(
            f"build: {label} — skill-only text survived the transform.\n"
            "Add or fix a rule in integrations/speckit/build.py.\n\n" + "\n".join(left))
    return text


def transform(text, name, ver):
    """Workflow document -> Spec Kit slash command."""
    required = [(old, new.replace("{version}", ver)) for old, new in FILE_RULES[name]]
    text = apply_rules(text, f"commands/{name}.md", required, COMMON_RULES, LEFTOVERS)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines[i] = COMMAND_TITLES[name]
            break
    text = "\n".join(lines)
    args_line = COMMAND_ARGS[name]
    for s in SCOPE_HINTS:
        if s in text:
            text = text.replace(s, f"{args_line}\n\n$ARGUMENTS")
            break
    else:
        # No scope paragraph: insert $ARGUMENTS before the first section.
        idx = text.index("\n## ")
        text = text[:idx] + f"\n{args_line}\n\n$ARGUMENTS\n" + text[idx:]
    return f'---\ndescription: "{COMMAND_DESCRIPTIONS[name]}"\n---\n\n{text}'


def build(out):
    ver = version()
    if out.exists():
        # Only ever clear something that is recognisably a previous build.
        if any(out.iterdir()) and not (out / "extension.yml").exists():
            raise SystemExit(f"build: {out} exists and is not a previous build; refusing to clear it")
        shutil.rmtree(out)
    (out / "commands").mkdir(parents=True)

    manifest = (HERE / "extension.yml").read_text()
    if "@VERSION@" not in manifest:
        raise SystemExit("build: extension.yml has no @VERSION@ placeholder")
    (out / "extension.yml").write_text(manifest.replace("@VERSION@", ver))
    shutil.copy2(HERE / "commands" / "verify.md", out / "commands" / "verify.md")
    shutil.copy2(HERE / "README.md", out / "README.md")
    shutil.copy2(ROOT / "LICENSE", out / "LICENSE")

    for name in WORKFLOWS:
        text = (ASSETS / "references" / f"{name}.md").read_text()
        (out / "commands" / f"{name}.md").write_text(transform(text, name, ver))

    for src, dst in SCRIPTS.items():
        path = out / dst
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SCRIPTS_DIR / src, path)
        path.chmod(0o755 if src.endswith(".sh") else 0o644)

    template = (ASSETS / "okf-config.template.yml").read_text()
    (out / "okf-config.template.yml").write_text(
        apply_rules(template, "okf-config.template.yml", TEMPLATE_RULES, [], []))
    return ver


def make_zip(out, ver):
    """Spec Kit expects extension.yml at the top of the archive."""
    archive = out.parent / f"speckit-okf-{ver}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(out)))
                info.external_attr = (path.stat().st_mode & 0o777) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
    return archive


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output directory (default {DEFAULT_OUT.relative_to(ROOT)})")
    ap.add_argument("--zip", action="store_true", help="Also write speckit-okf-<version>.zip next to it")
    args = ap.parse_args()

    out = args.out.resolve()
    ver = build(out)
    print(f"built Spec Kit extension okf {ver} in {out}")
    if args.zip:
        print(f"  {make_zip(out, ver)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
