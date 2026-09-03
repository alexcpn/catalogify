#!/usr/bin/env python3
"""validate_okf.py — conformance checker for OKF v0.1 bundles.

Implements OKF §9 conformance rules as ERRORs and the spec's soft
guidance as WARNINGs:

ERRORS (bundle is non-conformant):
  E1  Non-reserved .md file has no parseable YAML frontmatter block, or
      could not be read.
  E2  Frontmatter lacks a non-empty `type` field.
  E3  Reserved file structure violations:
      - index.md with frontmatter anywhere except the bundle root
        (root index.md may carry only okf_version per §11)
      - log.md date headings not in ISO 8601 YYYY-MM-DD form (§7)
  E4  log.md date block missing a required `Commit: \\`<sha>\\`` line, or
      the line is present but is neither a valid hex commit SHA nor the
      literal `none`. This is an ERROR because the update workflow depends
      on it to resume. Skipped entirely outside a git repository, where
      there is no commit to record.

WARNINGS (consumers must tolerate; reported for quality):
  W0  PyYAML not installed — using the lenient fallback parser.
  W1  Missing recommended frontmatter (title, description).
  W2  Broken bundle-internal links (may be not-yet-written knowledge).
  W3  Directory containing concepts but no index.md.
  W4  Concept body is empty.
  W5  Possible secret-looking string in a file.
  W6  A `source_files` entry does not exist on disk (may be pending
      reconciliation by the update workflow).
  W7  Possible duplicate concept: another file shares the same
      `type` + `title`.
  W8  Concept has unresolved `open_questions` (run the clarify workflow).

Usage: validate_okf.py <bundle_dir> [--config PATH] [--exclude GLOB]...
                        [--repo-root PATH] [--json]
Exit code 0 if conformant (warnings allowed), 1 if non-conformant, 2 on
bad usage.

Only stdlib is required; PyYAML is used if available for stricter YAML
parsing, with a lenient fallback otherwise.
"""

import argparse
import fnmatch
import json
import os
import re
import sys

try:
    import yaml  # type: ignore
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

RESERVED = {"index.md", "log.md"}
DATE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")
# A commit SHA, or the literal `none` for bundles generated outside a git
# repository, where there is no commit to record.
COMMIT_LINE = re.compile(r"^Commit:\s+`([0-9a-fA-F]{7,40}|none)`\s*$", re.I)
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SECRET_PATTERNS = [
    # key: "value" / key = 'value' (quoted)
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9+/_\-]{16,}['\"]"),
    # key: value / key = value (unquoted)
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[A-Za-z0-9+/_\-]{16,}\b"),
    # AWS-style access key ID
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # PEM private key block start
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
]

errors: list[str] = []
warnings: list[str] = []
concept_meta: list[tuple[str, str, str]] = []  # (rel, type, title)


def split_frontmatter(text: str):
    """Return (frontmatter_str or None, body)."""
    if not text.startswith("---"):
        return None, text
    parts = text.split("\n")
    if parts[0].strip() != "---":
        return None, text
    for i in range(1, len(parts)):
        if parts[i].strip() == "---":
            return "\n".join(parts[1:i]), "\n".join(parts[i + 1:])
    return None, text  # unterminated block


def parse_yaml(fm: str):
    """Parse frontmatter; return dict or None on failure."""
    if HAVE_YAML:
        try:
            data = yaml.safe_load(fm)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError:
            return None
    # Lenient fallback: top-level "key: value" lines only.
    data = {}
    for line in fm.splitlines():
        if not line.strip() or line.startswith(("#", " ", "\t", "-")):
            continue
        if ":" not in line:
            return None
        k, _, v = line.partition(":")
        data[k.strip()] = v.strip().strip("'\"")
    return data


def read_text(path: str) -> tuple[str, None] | tuple[None, str]:
    """Read a file as text; return (text, None) or (None, error_message)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(), None
    except OSError as e:
        return None, str(e)


def check_concept(path: str, rel: str, bundle: str, repo_root: str):
    text, err = read_text(path)
    if text is None:
        errors.append(f"E1 {rel}: could not read file ({err})")
        return
    fm, body = split_frontmatter(text)
    if fm is None:
        errors.append(f"E1 {rel}: missing or unterminated YAML frontmatter block")
        return
    data = parse_yaml(fm)
    if data is None:
        errors.append(f"E1 {rel}: frontmatter is not parseable YAML")
        return
    t = data.get("type")
    if not (isinstance(t, str) and t.strip()):
        errors.append(f"E2 {rel}: frontmatter has no non-empty `type` field")
    for field in ("title", "description"):
        if not data.get(field):
            warnings.append(f"W1 {rel}: missing recommended field `{field}`")
    if not body.strip():
        warnings.append(f"W4 {rel}: concept body is empty")
    check_links(body, rel, os.path.dirname(path), bundle)
    check_source_files(data, rel, repo_root)
    check_open_questions(data, rel)
    if isinstance(t, str) and t.strip() and data.get("title"):
        concept_meta.append((rel, t.strip(), str(data["title"]).strip()))
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            warnings.append(f"W5 {rel}: possible secret-looking value — review before sharing")
            break


def check_source_files(data: dict, rel: str, repo_root: str):
    sf = data.get("source_files")
    if not isinstance(sf, list):
        return
    for entry in sf:
        if not isinstance(entry, str) or not entry.strip():
            continue
        candidate = os.path.join(repo_root, entry)
        if not os.path.exists(candidate):
            warnings.append(f"W6 {rel}: source_files entry '{entry}' does not exist")


def check_open_questions(data: dict, rel: str):
    oq = data.get("open_questions")
    if not isinstance(oq, list):
        return
    pending = [q for q in oq if isinstance(q, str) and q.strip()]
    if pending:
        n = len(pending)
        warnings.append(
            f"W8 {rel}: {n} unresolved open question{'s' if n != 1 else ''} "
            f"— ask your agent to run the clarify workflow"
        )


def check_links(body: str, rel: str, filedir: str, bundle: str):
    for target in LINK.findall(body):
        target = target.split("#")[0].strip()
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        if target.startswith("/"):
            dest = os.path.join(bundle, target.lstrip("/"))
        else:
            dest = os.path.join(filedir, target)
        # Directory links (progressive disclosure) are fine if the dir exists.
        if not (os.path.exists(dest) or os.path.exists(dest.rstrip("/"))):
            warnings.append(f"W2 {rel}: broken link -> {target}")


def check_index(path: str, rel: str, is_root: bool, bundle: str):
    text, err = read_text(path)
    if text is None:
        errors.append(f"E1 {rel}: could not read file ({err})")
        return
    fm, body = split_frontmatter(text)
    if fm is not None:
        if not is_root:
            errors.append(f"E3 {rel}: index.md must not contain frontmatter (only the bundle root may, per §11)")
        else:
            data = parse_yaml(fm) or {}
            extra = set(data) - {"okf_version"}
            if extra:
                errors.append(f"E3 {rel}: root index.md frontmatter may only declare okf_version (found: {sorted(extra)})")
    check_links(body if fm is not None else text, rel, os.path.dirname(path), bundle)


def check_log(path: str, rel: str, require_commit: bool = True):
    text, err = read_text(path)
    if text is None:
        errors.append(f"E1 {rel}: could not read file ({err})")
        return
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if not ln.startswith("## "):
            continue
        stripped = ln.rstrip()
        if not DATE_HEADING.match(stripped):
            errors.append(f"E3 {rel}: log heading not ISO 8601 YYYY-MM-DD: '{stripped}'")
            continue
        # Look for a "Commit: `<sha>`" line before the next date heading.
        found_sha = None
        for j in range(i + 1, len(lines)):
            if lines[j].startswith("## "):
                break
            m = COMMIT_LINE.match(lines[j].strip())
            if m:
                found_sha = m.group(1)
                break
        if found_sha is None and require_commit:
            errors.append(f"E4 {rel}: date block '{stripped}' missing required 'Commit: `<sha>`' line")


def find_repo_root(bundle: str) -> str:
    p = bundle
    while True:
        if os.path.isdir(os.path.join(p, ".git")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return os.path.dirname(bundle)
        p = parent


def load_config_excludes(path: str) -> list[str]:
    if not path or not os.path.isfile(path):
        return []
    text, err = read_text(path)
    if err is not None or text is None:
        return []
    if HAVE_YAML:
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            return []
        excl = (data.get("okf") or {}).get("exclude") or []
        return [str(x) for x in excl if isinstance(x, str)]
    # Lenient fallback: scan for an `exclude:` block of `- "glob"` lines.
    globs = []
    in_exclude = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^exclude\s*:\s*$", stripped):
            in_exclude = True
            continue
        if in_exclude:
            m = re.match(r"^-\s*['\"]?([^'\"#]+)['\"]?\s*(#.*)?$", stripped)
            if m:
                globs.append(m.group(1).strip())
                continue
            if stripped and not stripped.startswith("#"):
                in_exclude = False
    return globs


def is_excluded(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pat) for pat in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Conformance checker for OKF v0.1 knowledge bundles.",
    )
    parser.add_argument("bundle_dir", help="Path to the knowledge bundle directory")
    parser.add_argument("--config", help="Path to okf-config.yml (exclude list is honored)")
    parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude (repeatable)")
    parser.add_argument("--repo-root", help="Repo root for resolving source_files (default: nearest .git above bundle_dir)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    args = parser.parse_args()

    if not os.path.isdir(args.bundle_dir):
        parser.error(f"{args.bundle_dir} is not a directory")

    bundle = os.path.abspath(args.bundle_dir)
    repo_root = os.path.abspath(args.repo_root) if args.repo_root else find_repo_root(bundle)
    # Bundles generated outside a git repository have no commit to record in
    # log.md, so E4 cannot apply to them.
    is_git_repo = os.path.isdir(os.path.join(repo_root, ".git"))
    exclude_patterns = load_config_excludes(args.config) + list(args.exclude)

    if not HAVE_YAML:
        warnings.append("W0 (global): PyYAML not installed — using lenient fallback parser, results may be less strict")

    concepts = 0
    for dirpath, dirnames, filenames in os.walk(bundle):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, bundle)
        mds = [
            f for f in filenames
            if f.endswith(".md") and not is_excluded(
                os.path.relpath(os.path.join(dirpath, f), bundle), exclude_patterns
            )
        ]
        if any(f not in RESERVED for f in mds) and "index.md" not in mds:
            warnings.append(f"W3 {rel_dir or '.'}: directory has concepts but no index.md")
        for f in mds:
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, bundle)
            if f == "index.md":
                check_index(path, rel, dirpath == bundle, bundle)
            elif f == "log.md":
                check_log(path, rel, require_commit=is_git_repo)
            else:
                concepts += 1
                check_concept(path, rel, bundle, repo_root)

    # W7: duplicate (type, title) pairs across the bundle.
    seen: dict[tuple[str, str], str] = {}
    for rel, t, title in concept_meta:
        key = (t.lower(), title.lower())
        if key in seen:
            warnings.append(f"W7 {rel}: possible duplicate concept — same type+title as {seen[key]}")
        else:
            seen[key] = rel

    if args.json:
        print(json.dumps({
            "concepts": concepts,
            "errors": errors,
            "warnings": warnings,
            "result": "NON-CONFORMANT" if errors else "CONFORMANT",
        }, indent=2))
    else:
        print(f"OKF validation of {bundle}")
        print(f"  concepts: {concepts}  errors: {len(errors)}  warnings: {len(warnings)}\n")
        for e in errors:
            print(f"  ERROR   {e}")
        for w in warnings:
            print(f"  WARNING {w}")
        print("\nRESULT:", "NON-CONFORMANT" if errors else "CONFORMANT (OKF v0.1)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
