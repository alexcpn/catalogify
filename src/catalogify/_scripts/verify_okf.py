#!/usr/bin/env python3
"""verify_okf.py — check what a bundle CLAIMS against what the repo CONTAINS.

`validate_okf.py` answers "is this bundle well-formed?". This answers the
harder question: "is any of it true?". Every check here resolves a claim in
the prose back to something in the repository, so an agent that wrote a
confident sentence with nothing behind it gets caught by a tool rather than
by a reader.

Findings (a claim is unsupported):
  V1  A cited commit SHA does not exist in this repository.
  V2  A cited commit touches none of the concept's `source_files` — the
      evidence belongs to a different concept.
  V3  A commit cited under `# Gotchas` changed only test files. Test
      hygiene is not a production invariant. (Elsewhere in the body this
      is a NOTE rather than a finding.)
  V4  A symbol in the `# Interfaces` table does not appear in any
      non-test file under `source_files`.
  V5  A `# Gotchas` section states invariants but cites no commit at all.

Notes (probably wrong, legitimately arguable):
  V6  A `# Dependencies` link to another concept that no import backs.
      Runtime coupling (queues, RPC, shared storage) is a real reason for
      this, so it is reported rather than failed.
  V7  The body claims an "import cycle" between Go packages. Go forbids
      them; what is almost always meant is a shared leaf sub-package.

Usage: verify_okf.py <bundle_dir> [--repo-root PATH] [--json] [--strict]
Exit 0 when no findings (notes allowed), 1 when findings exist, 2 on bad
usage. --strict also fails on notes.

Requires git and a git repository; stdlib only, PyYAML used when present.
"""

import argparse
import json
import os
import re
import subprocess
import sys

try:
    import yaml  # type: ignore
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

RESERVED = {"index.md", "log.md"}
# Backtick-quoted hex token: how generate.md tells the agent to cite a commit.
SHA_TOKEN = re.compile(r"`([0-9a-f]{7,40})`")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,3}\s+(.*?)\s*$", re.M)
# Shared with okf-history.sh — keep the two in step.
TEST_FILE = re.compile(
    r"(^|/)(tests?|testing|testdata|__tests__|fixtures?|spec)/"
    r"|(^|/)test_[^/]*\.py$"
    r"|_test\.(go|py|rs|rb)$"
    r"|\.(test|spec)\.[jt]sx?$"
    r"|Tests?\.(java|cs|kt|scala)$"
    r"|_spec\.rb$"
)

findings = []
notes = []


# --- repo access -----------------------------------------------------------

class Repo:
    """Thin cached wrapper over the git commands the checks need."""

    def __init__(self, root):
        self.root = root
        self._files = {}      # sha -> [paths] | None when the sha is unknown
        self._grep = {}       # (needle, word, paths) -> [paths]

    def _git(self, args):
        try:
            done = subprocess.run(
                ["git", *args], cwd=self.root,
                capture_output=True, text=True, check=False,
            )
        except OSError:
            return 1, ""
        return done.returncode, done.stdout

    def commit_files(self, sha):
        """Files a commit touched, or None when the sha is not a commit."""
        if sha not in self._files:
            code, out = self._git(["cat-file", "-t", sha])
            if code != 0 or out.strip() != "commit":
                self._files[sha] = None
            else:
                _, names = self._git(["show", "--name-only", "--format=", sha])
                self._files[sha] = [ln for ln in names.splitlines() if ln.strip()]
        return self._files[sha]

    def grep_files(self, needle, paths, word=True):
        """Files under `paths` containing `needle` (whole word by default)."""
        key = (needle, word, tuple(paths))
        if key not in self._grep:
            args = ["grep", "--no-color", "-l", "-F"]
            if word:
                args.append("-w")
            args += ["-e", needle, "--", *paths]
            code, out = self._git(args)
            # git grep exits 1 for "no match", which is not an error here.
            self._grep[key] = [ln for ln in out.splitlines() if ln.strip()] if code in (0, 1) else []
        return self._grep[key]

    def has_go(self, paths):
        code, out = self._git(["ls-files", "--", *[f"{p}/*.go" if not p.endswith(".go") else p for p in paths]])
        return code == 0 and bool(out.strip())


# --- parsing ---------------------------------------------------------------

def split_frontmatter(text):
    if not text.startswith("---"):
        return None, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def parse_yaml(fm):
    if HAVE_YAML:
        try:
            data = yaml.safe_load(fm)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError:
            return None
    data, key = {}, None
    for line in fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s*(.*)$", line)
        if item and key:
            data.setdefault(key, []).append(item.group(1).strip().strip("'\""))
            continue
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            key = k.strip()
            v = v.strip().strip("'\"")
            data[key] = v if v else []
    return data


def sections(body):
    """Split a body into {heading: text} by markdown heading."""
    out, current, buf = {}, None, []
    for line in body.splitlines():
        m = HEADING.match(line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf)
            current, buf = m.group(1).strip().lower(), []
        else:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf)
    return out


def table_first_column(text):
    """First-column data cells of every markdown table in `text`.

    The row above a `|---|` separator is the header, so it names columns
    rather than symbols; it is dropped.
    """
    cells = []
    prev_was_row = False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            prev_was_row = False
            continue
        parts = [p.strip() for p in s.strip("|").split("|")]
        if not parts:
            prev_was_row = False
            continue
        if parts[0] and set(parts[0]) <= set("-: "):
            if prev_was_row and cells:
                cells.pop()  # that was the header row
            prev_was_row = False
            continue
        cells.append(parts[0])
        prev_was_row = True
    return cells


def symbols_in(cell):
    """Identifiers a cell claims exist. Endpoints and prose are skipped."""
    spans = re.findall(r"`([^`]+)`", cell) or [cell]
    out = []
    for span in spans:
        span = span.strip()
        if not span or span.startswith(("/", "-")):
            continue  # HTTP route or a dash placeholder, not a symbol
        span = span.split("(")[0].strip()          # drop call args
        span = re.sub(r"^\([^)]*\)\s*", "", span)  # drop a Go receiver
        for part in re.split(r"[/,]", span):
            part = part.strip().rstrip("*.").strip()
            if "." in part:
                part = part.rsplit(".", 1)[-1]     # Type.Method -> Method
            if not part or " " in part:
                continue  # prose, not an identifier
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) and len(part) > 2:
                out.append(part)
    return out


def under(filepath, prefix):
    """True when `filepath` is `prefix` itself or sits inside it."""
    prefix = prefix.rstrip("/")
    return filepath == prefix or filepath.startswith(prefix + "/")


def source_paths(data, repo_root):
    raw = data.get("source_files") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(p) for p in raw if isinstance(p, str) and os.path.exists(os.path.join(repo_root, str(p)))]


# --- checks ----------------------------------------------------------------

def verify_concept(rel, text, bundle, repo_root, repo, concept_sources):
    fm, body = split_frontmatter(text)
    data = parse_yaml(fm) if fm else None
    if not isinstance(data, dict):
        return  # validate_okf.py owns malformed frontmatter (E1)

    paths = source_paths(data, repo_root)
    secs = sections(body)
    gotchas = next((v for k, v in secs.items() if k.startswith("gotcha")), "")

    # --- V1/V2/V3: every cited commit must exist, be relevant, and be real code.
    cited = []
    seen = set()
    for section_name, section_text in secs.items():
        for sha in SHA_TOKEN.findall(section_text):
            if sha in seen:
                continue
            seen.add(sha)
            cited.append((sha, section_name))

    for sha, section_name in cited:
        files = repo.commit_files(sha)
        if files is None:
            findings.append(f"V1 {rel}: cited commit `{sha}` does not exist in this repository")
            continue
        if paths and not any(under(f, p) for f in files for p in paths):
            findings.append(
                f"V2 {rel}: cited commit `{sha}` touches none of this concept's source_files "
                f"— it belongs to another concept"
            )
        if files and all(TEST_FILE.search(f) for f in files):
            where = "under # Gotchas" if section_name.startswith("gotcha") else f"under # {section_name}"
            msg = (f"{rel}: cited commit `{sha}` changed only test files {where} "
                   f"— test hygiene, not a production invariant")
            (findings if section_name.startswith("gotcha") else notes).append(
                ("V3 " if section_name.startswith("gotcha") else "V3 ") + msg
            )

    # --- V5: a gotcha section that asserts invariants but cites nothing.
    if gotchas.strip() and not SHA_TOKEN.search(gotchas):
        findings.append(f"V5 {rel}: # Gotchas states invariants but cites no commit")

    # --- V4: every symbol in the interfaces table must exist in non-test code.
    interfaces = next((v for k, v in secs.items() if k.startswith("interface")), "")
    if interfaces and paths:
        checked = set()
        for cell in table_first_column(interfaces):
            for sym in symbols_in(cell):
                if sym in checked:
                    continue
                checked.add(sym)
                hits = [h for h in repo.grep_files(sym, paths) if not TEST_FILE.search(h)]
                if not hits:
                    findings.append(
                        f"V4 {rel}: `{sym}` in # Interfaces appears in no non-test file under source_files"
                    )

    # --- V6: a dependency link no import backs.
    deps = next((v for k, v in secs.items() if k.startswith("dependenc")), "")
    if deps and paths:
        for target in LINK.findall(deps):
            if not target.startswith("/") or not target.endswith(".md"):
                continue
            tgt_rel = os.path.normpath(target.lstrip("/"))
            tgt_paths = concept_sources.get(tgt_rel)
            if not tgt_paths:
                continue  # unwritten concept, or one with no source_files
            backed = False
            for tp in tgt_paths:
                # forward: this concept imports the target
                if any(not TEST_FILE.search(h) for h in repo.grep_files(tp.rstrip("/"), paths, word=False)):
                    backed = True
                    break
            if not backed:
                for sp in paths:
                    # reverse: the target imports this concept ("consumed by", "read by")
                    if any(not TEST_FILE.search(h) for h in repo.grep_files(sp.rstrip("/"), tgt_paths, word=False)):
                        backed = True
                        break
            if not backed:
                notes.append(
                    f"V6 {rel}: links to {target} under # Dependencies but no import mentions "
                    f"{tgt_paths[0]} — runtime coupling, or invented?"
                )

    # --- V7: Go has no import cycles.
    if re.search(r"import cycle", body, re.I) and paths and repo.has_go(paths):
        notes.append(
            f"V7 {rel}: claims an \"import cycle\" in Go code — the compiler forbids them; "
            f"this is normally a shared leaf sub-package"
        )


def find_repo_root(bundle):
    p = bundle
    while True:
        if os.path.isdir(os.path.join(p, ".git")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return os.path.dirname(bundle)
        p = parent


def main():
    ap = argparse.ArgumentParser(description="Verify a bundle's claims against the repository.")
    ap.add_argument("bundle_dir")
    ap.add_argument("--repo-root", help="Repo root (default: nearest .git above bundle_dir)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="Fail on notes as well as findings")
    args = ap.parse_args()

    if not os.path.isdir(args.bundle_dir):
        ap.error(f"{args.bundle_dir} is not a directory")

    bundle = os.path.abspath(args.bundle_dir)
    repo_root = os.path.abspath(args.repo_root) if args.repo_root else find_repo_root(bundle)
    if not os.path.isdir(os.path.join(repo_root, ".git")):
        print("okf-verify: not a git repository — every check here resolves claims "
              "against git, so there is nothing to verify against.", file=sys.stderr)
        return 0

    repo = Repo(repo_root)

    # Pass 1: every concept's source_files, so dependency links can resolve.
    concepts = {}
    concept_sources = {}
    for dirpath, dirnames, filenames in os.walk(bundle):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            if not f.endswith(".md") or f in RESERVED:
                continue
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, bundle)
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            concepts[rel] = text
            fm, _ = split_frontmatter(text)
            data = parse_yaml(fm) if fm else None
            if isinstance(data, dict):
                concept_sources[rel] = source_paths(data, repo_root)

    # Pass 2: verify.
    for rel in sorted(concepts):
        verify_concept(rel, concepts[rel], bundle, repo_root, repo, concept_sources)

    if args.json:
        print(json.dumps({
            "concepts": len(concepts),
            "findings": findings,
            "notes": notes,
            "result": "UNSUPPORTED CLAIMS" if findings else "VERIFIED",
        }, indent=2))
    else:
        print(f"OKF claim verification of {bundle}")
        print(f"  concepts: {len(concepts)}  findings: {len(findings)}  notes: {len(notes)}\n")
        for f in findings:
            print(f"  FINDING {f}")
        for n in notes:
            print(f"  NOTE    {n}")
        if not findings and not notes:
            print("  every cited commit, symbol and dependency resolves.\n")
        print("\nRESULT:", "UNSUPPORTED CLAIMS" if findings else "VERIFIED")

    return 1 if findings or (args.strict and notes) else 0


if __name__ == "__main__":
    sys.exit(main())
