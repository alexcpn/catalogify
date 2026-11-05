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
  V8  A `source_files` entry is not tracked by git. Vendored, imported or
      generated code sitting in the working tree is not part of this
      repository: it has no history to mine, it is not yours to document,
      and describing it produces confident prose backed by nothing. When
      *no* entry is tracked, the concept is reported once and its other
      checks are skipped, because git cannot see those files to check them.

Ontology layer (typed relations, playbooks, guardrails; see okf_bundle.py):
  V9  A relation is malformed, uses a kind outside the fixed vocabulary
      (changes_with, generated_from, versioned_by, calls, reads_config,
      requires), uses `requires` outside a Playbook, or cites evidence that
      is not a commit SHA (a branch name, a revision, an unquoted number).
  V10 A relation target or an `applies_to` path is not tracked by git.
  V11 A relation is unsupported: none of its `evidence` commits touches
      both ends (the concept's source_files, or a Playbook/Guardrail's
      applies_to, and the target), with a different file on each side.
      `calls` may instead be backed by a qualified import of the target,
      `reads_config` by a mention of the target's file name (with its
      extension). Every evidence SHA is checked, not just the first.
  V13 A Guardrail is violated or unfounded: a `forbids` pattern occurs in
      non-test code, a `motivated_by` commit touches none of applies_to,
      or an `enforced_by` file is not tracked.

Notes (probably wrong, legitimately arguable):
  V6  A `# Dependencies` link to another concept that no import backs, in
      either direction. Import lines are matched against several forms of
      the target path — as written, without its extension, and dotted — so
      `import libs.lib_util` backs a link to `libs/lib_util.py`. Runtime
      coupling (queues, RPC, shared storage) is a real reason for an
      unbacked link, so it is reported rather than failed.
  V7  The body claims an "import cycle" between Go packages. Go forbids
      them; what is almost always meant is a shared leaf sub-package.
  V12 A Playbook has no `# Steps`, or states no `requires` relation.
  V14 A Guardrail has neither `enforced_by` nor `forbids`: documented,
      not enforced. Real enforcement lives in tests, CI and sandboxes;
      `forbids` only catches literal patterns, never semantic leaks.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_bundle import (  # noqa: E402  (sibling module, shared with okf_find.py)
    GUARDRAIL, HAVE_YAML, PLAYBOOK, RELATION_KINDS, SHA as SHA_HEX, as_list, concept_type,
    forbids, relations, sections, str_list, under, walk,
)
# Backtick-quoted hex token: how generate.md tells the agent to cite a commit.
SHA_TOKEN = re.compile(r"`([0-9a-f]{7,40})`")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Shared with okf-history.sh — keep the two in step.
TEST_FILE = re.compile(
    r"(^|/)(tests?|testing|testdata|__tests__|fixtures?|spec)/"
    r"|(^|/)test_[^/]*\.py$"
    r"|_test\.(go|py|rs|rb)$"
    r"|\.(test|spec)\.[jt]sx?$"
    r"|Tests?\.(java|cs|kt|scala)$"
    r"|_spec\.rb$"
)

# Import-looking lines: a keyword form, or Go's bare quoted path inside a
# grouped `import ( ... )` block.
IMPORT_LINE = (
    r'^[[:space:]]*(import|from|#include|require|use|using)[[:space:]]'
    r'|^[[:space:]]*(_[[:space:]]+|[A-Za-z_][A-Za-z0-9_]*[[:space:]]+)?"[^"]{3,}"[[:space:]]*$'
)

findings = []
notes = []


def import_needles(path):
    """Forms of a path that could appear in an import statement.

    Go writes the directory path ("…/pkg/kubelet/cm"), Python writes a
    dotted module (`import libs.lib_util`), JS writes a relative path with
    no extension. Matching only the literal filesystem path finds the first
    and misses every other language.
    """
    p = path.rstrip("/")
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", p)
    parts = [x for x in stem.split("/") if x]
    forms = {p, stem, stem.replace("/", ".")}
    if len(parts) >= 2:
        forms.add("/".join(parts[-2:]))
        forms.add(".".join(parts[-2:]))
    if parts:
        forms.add(parts[-1])
    return {f for f in forms if len(f) >= 3}


# --- repo access -----------------------------------------------------------

class Repo:
    """Thin cached wrapper over the git commands the checks need."""

    def __init__(self, root):
        self.root = root
        self._files = {}      # sha -> [paths] | None when the sha is unknown
        self._grep = {}       # (needle, word, paths) -> [paths]
        self._tracked = {}    # path -> bool
        self._imports = {}    # (paths) -> import-looking lines

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

    def tracked(self, path):
        """True when git has this path, or anything under it, in the index."""
        if path not in self._tracked:
            code, out = self._git(["ls-files", "--", path])
            self._tracked[path] = code == 0 and bool(out.strip())
        return self._tracked[path]

    def import_lines(self, paths):
        """Every import-looking line under `paths`, as one blob of text.

        Covers keyword imports (Python, JS/TS, Rust, C/C++, Java, C#) and
        Go's grouped form, where lines inside `import ( ... )` are bare
        quoted paths with no keyword at all.
        """
        key = tuple(paths)
        if key not in self._imports:
            code, out = self._git(
                ["grep", "--no-color", "-h", "-E", "-e", IMPORT_LINE, "--", *paths]
            )
            self._imports[key] = out if code in (0, 1) else ""
        return self._imports[key]

    def has_go(self, paths):
        code, out = self._git(["ls-files", "--", *[f"{p}/*.go" if not p.endswith(".go") else p for p in paths]])
        return code == 0 and bool(out.strip())


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


# Extensions that make a dotted token a filename, not a Type.method chain.
FILE_EXT = {
    "yaml", "yml", "json", "toml", "ini", "cfg", "conf", "xml", "csv", "lock",
    "md", "rst", "txt", "html", "css", "scss", "svg", "png", "jpg", "gif",
    "go", "py", "js", "jsx", "ts", "tsx", "java", "cs", "rb", "rs", "kt", "php",
    "sh", "bash", "sql", "proto", "tf", "gradle", "properties", "env", "cast",
}
HTTP_VERBS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}
# Words that appear in a first column as a category or a type, not as a symbol
# anyone could grep for. Skipping a real one costs a missed check; accepting a
# false one costs trust, which is worth more.
NON_SYMBOLS = {
    "class", "func", "function", "def", "type", "struct", "interface", "enum",
    "const", "var", "let", "public", "private", "protected", "static", "void",
    "string", "int", "bool", "float", "double", "byte", "char", "error", "any",
    "null", "nil", "none", "true", "false", "import", "package", "module",
    "return", "new", "this", "self", "super", "async", "await", "yield",
    "symbol", "method", "field", "contract", "surface", "endpoint", "route",
    "name", "path", "purpose", "value", "key", "file", "manifest", "command",
}


def symbols_in(cell):
    """Identifiers a cell unambiguously claims exist.

    Deliberately conservative: this feeds V4, and a false positive there
    accuses an author of inventing an API they did not invent. A check that
    fires rarely and is right is worth more than one that fires often and is
    half noise, because noise teaches people to ignore the tool.

    So a span is judged only when it is plainly a single identifier. Anything
    ambiguous is skipped rather than guessed at: HTTP routes (`GET /cart`),
    filenames (`frontend.yaml`), generics (`Map<String, Foo>`), CLI flags,
    prose, and bare type names that are really column headings.
    """
    spans = re.findall(r"`([^`]+)`", cell)
    if not spans:
        return []  # no code span at all: prose, or a category label
    out = []
    for span in spans:
        span = span.strip()
        if not span:
            continue
        span = re.sub(r"^\([^)]*\)\s*", "", span)   # Go receiver: (m *T) Sync -> Sync
        span = span.split("(")[0].strip()           # call args: Sync(a, b) -> Sync
        if not span or " " in span or "\t" in span:
            continue  # `GET /cart`, `Pod sources (apiserver, ...)`, prose
        if span[0] in "/-.@#$":
            continue  # route, CLI flag, decorator, template variable
        if any(c in span for c in "<>[]{}|\\\"'"):
            continue  # generics, arrays, unions, quoted text
        # `/` and `,` separate sibling symbols and all are kept;
        # `::` and `.` qualify one symbol, so only the last segment is taken.
        for part in re.split(r"[/,;]+", span):
            part = part.strip().strip("*")
            if not part:
                continue
            if "::" in part:
                part = part.rsplit("::", 1)[-1]   # Ns::Class::method -> method
            if "." in part:
                head, _, tail = part.rpartition(".")
                if tail.lower() in FILE_EXT or not head:
                    continue  # frontend.yaml, .gitignore
                part = tail   # Type.Method -> Method
            if len(part) <= 2 or part.upper() in HTTP_VERBS or part.lower() in NON_SYMBOLS:
                continue
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part):
                out.append(part)
    return out




def source_paths(data, repo_root):
    raw = data.get("source_files") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(p) for p in raw if isinstance(p, str) and os.path.exists(os.path.join(repo_root, str(p)))]


# --- checks ----------------------------------------------------------------

def verify_concept(rel, data, body, bundle_rel, repo_root, repo, concept_sources):
    if not isinstance(data, dict):
        return  # validate_okf.py owns malformed frontmatter (E1)

    all_paths = source_paths(data, repo_root)
    paths = [p for p in all_paths if repo.tracked(p)]
    untracked = [p for p in all_paths if p not in paths]

    # --- V8: code git does not know about is not this repository's to describe.
    if all_paths and not paths:
        shown = ", ".join(untracked[:3]) + ("…" if len(untracked) > 3 else "")
        findings.append(
            f"V8 {rel}: no source_files entry is tracked by git ({shown}) — vendored, "
            f"generated or imported code, not part of this repository. Remaining checks "
            f"skipped: git cannot see these files, so nothing here can be verified"
        )
        return
    for u in untracked:
        findings.append(
            f"V8 {rel}: source_files entry '{u}' is not tracked by git — vendored, "
            f"generated or imported code; it is excluded from every check below"
        )

    secs = sections(body)
    gotchas = next((v for k, v in secs.items() if k.startswith("gotcha")), "")
    # A Playbook or Guardrail usually has no source_files; what it is about is
    # its applies_to, so prose citations are checked against that instead.
    anchors = paths
    if not anchors and concept_type(data) in (PLAYBOOK, GUARDRAIL):
        anchors = [a.rstrip("/") for a in str_list(data.get("applies_to")) if repo.tracked(a.rstrip("/"))]

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
        if anchors and not any(under(f, p) for f in files for p in anchors):
            findings.append(
                f"V2 {rel}: cited commit `{sha}` touches none of this concept's "
                f"{'source_files' if paths else 'applies_to'} "
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
                    scope = " (git-tracked entries only)" if untracked else ""
                    findings.append(
                        f"V4 {rel}: `{sym}` in # Interfaces appears in no non-test file "
                        f"under source_files{scope}"
                    )

    # --- V6: a dependency link no import backs.
    deps = next((v for k, v in secs.items() if k.startswith("dependenc")), "")
    if deps and paths:
        my_imports = repo.import_lines(paths)
        for target in LINK.findall(deps):
            target = target.split("#")[0].strip()
            if not target or "://" in target or not target.endswith(".md"):
                continue
            if target.startswith("/"):
                # OKF bundle-relative: resolve against the bundle root.
                tgt_rel = os.path.normpath(target.lstrip("/"))
            else:
                # Relative: resolve against this concept's own directory,
                # then express it bundle-relative to match concept_sources.
                tgt_rel = os.path.normpath(os.path.join(os.path.dirname(rel), target))
            tgt_paths = [t for t in (concept_sources.get(tgt_rel) or []) if repo.tracked(t)]
            if not tgt_paths:
                continue  # unwritten concept, no source_files, or untracked (V8 covers it)
            # forward: this concept imports the target
            backed = any(n in my_imports for t in tgt_paths for n in import_needles(t))
            if not backed:
                # reverse: the target imports this one ("consumed by", "read by")
                their_imports = repo.import_lines(tgt_paths)
                backed = any(n in their_imports for sp in paths for n in import_needles(sp))
            if not backed:
                notes.append(
                    f"V6 {rel}: links to {target} under # Dependencies but no import in "
                    f"either direction mentions {tgt_paths[0]} — runtime coupling, or invented?"
                )

    # --- V7: Go has no import cycles.
    if re.search(r"import cycle", body, re.I) and paths and repo.has_go(paths):
        notes.append(
            f"V7 {rel}: claims an \"import cycle\" in Go code — the compiler forbids them; "
            f"this is normally a shared leaf sub-package"
        )

    verify_ontology(rel, data, secs, paths, bundle_rel, repo)


# --- ontology layer: relations, playbooks, guardrails ------------------------

def commit_links(files, ends, target):
    """True when a commit's `files` include one under `ends` AND a different one under `target`.

    A file inside both (a target nested in the concept's own source tree) is
    counted only on the target side, so one file can never back both ends of
    a relation by itself.
    """
    in_target = [f for f in files if under(f, target)]
    in_ends = [f for f in files if any(under(f, e) for e in ends) and not under(f, target)]
    return bool(in_target) and bool(in_ends)


# A bare word on the import side ("utils") would match `import myutils`; only
# qualified forms ("lib/utils", "lib.utils") count, and only as whole tokens.
def import_backs(target, import_blob):
    for needle in import_needles(target):
        if "/" not in needle and "." not in needle:
            continue
        if re.search(r"(?<![\w.])" + re.escape(needle) + r"(?![\w])", import_blob):
            return True
    return False


def evidence_commits(rel, label, values, repo):
    """{sha: files} for valid, existing evidence; V9 for non-SHA values, V1 for unknown commits.

    Every value is checked, so an invented SHA cannot hide behind a real one.
    Branch names and revision expressions (`main`, `HEAD~3`) are rejected: they
    resolve to a different commit tomorrow, which is not a citation.
    """
    out = {}
    for v in values:
        if isinstance(v, bool) or not isinstance(v, str):
            findings.append(f"V9 {rel}: {label} value {v!r} is not a quoted commit SHA — YAML reads "
                            f"bare all-digit SHAs as numbers; write it as a string")
            continue
        sha = v.strip().lower()
        if not SHA_HEX.match(sha):
            findings.append(f"V9 {rel}: {label} value '{v}' is not a commit SHA (7-40 hex digits); "
                            f"branch names and revisions are not evidence")
            continue
        files = repo.commit_files(sha)
        if files is None:
            findings.append(f"V1 {rel}: cited commit `{sha}` does not exist in this repository")
            continue
        out[sha] = files
    return out


def verify_ontology(rel, data, secs, paths, bundle_rel, repo):
    """V9-V14. Typed claims are checked like prose claims: each one must resolve."""
    if not HAVE_YAML:
        if data.get("relations") or data.get("forbids"):
            notes.append(f"V9 {rel}: relations/forbids not checked — install PyYAML to parse them")
        return
    ctype = concept_type(data)
    applies = [a.rstrip("/") for a in str_list(data.get("applies_to"))]
    for a in applies:
        if not repo.tracked(a):
            findings.append(f"V10 {rel}: applies_to '{a}' is not tracked by git")
    applies = [a for a in applies if repo.tracked(a)]
    # What a relation's evidence must connect the target to: a playbook or a
    # guardrail is about its applies_to paths, anything else about its source_files.
    ends = applies if ctype in (PLAYBOOK, GUARDRAIL) else paths

    rels, problems = relations(data)
    for problem in problems:
        findings.append(f"V9 {rel}: malformed relation — {problem}")
    for r in rels:
        kind, target, evidence = r["kind"], r["target"], r["raw_evidence"]
        if kind not in RELATION_KINDS:
            findings.append(f"V9 {rel}: relation kind '{kind}' is not one of "
                            f"{', '.join(sorted(RELATION_KINDS))}")
            continue
        if kind == "requires" and ctype != PLAYBOOK:
            findings.append(f"V9 {rel}: 'requires' belongs to a Playbook, not a {data.get('type')}")
            continue
        if not repo.tracked(target):
            findings.append(f"V10 {rel}: {kind} target '{target}' is not tracked by git")
            continue
        if not ends:
            findings.append(f"V11 {rel}: {kind} -> {target} has nothing to anchor it — the concept "
                            f"has no tracked source_files{' or applies_to' if ctype in (PLAYBOOK, GUARDRAIL) else ''}")
            continue
        commits = evidence_commits(rel, f"{kind} -> {target} evidence", evidence, repo)
        backed = any(commit_links(files, ends, target) for files in commits.values())
        if not backed and kind == "calls":
            backed = import_backs(target, repo.import_lines(ends))
        if not backed and kind == "reads_config":
            # Only a file name with an extension is specific enough to grep for:
            # `config` or `settings` as a bare word matches half the code base.
            name = os.path.basename(target)
            backed = ("." in name.strip(".") and
                      bool([h for h in repo.grep_files(name, ends, word=False)
                            if not under(h, target)]))
        if not backed:
            why = ("no cited commit touches both ends" if evidence else "it cites no evidence")
            findings.append(f"V11 {rel}: {kind} -> {target} is unsupported: {why}")

    if ctype == PLAYBOOK:
        if not next((v for k, v in secs.items() if k.startswith("step")), "").strip():
            notes.append(f"V12 {rel}: Playbook has no # Steps")
        if not any(r["kind"] == "requires" for r in rels):
            notes.append(f"V12 {rel}: Playbook states no `requires` relation")

    if ctype == GUARDRAIL:
        for sha, files in evidence_commits(rel, "motivated_by", as_list(data.get("motivated_by")),
                                           repo).items():
            if applies and not any(under(f, a) for f in files for a in applies):
                findings.append(f"V13 {rel}: motivated_by `{sha}` touches none of applies_to")
        enforced = str_list(data.get("enforced_by"))
        for e in enforced:
            if not repo.tracked(e):
                findings.append(f"V13 {rel}: enforced_by '{e}' is not tracked by git")
        trips, trip_problems = forbids(data)
        for problem in trip_problems:
            findings.append(f"V9 {rel}: malformed guardrail — {problem}")
        for trip in trips:
            scope = [p for p in trip["in"] if repo.tracked(p)]
            if not scope:
                continue
            hits = [h for h in repo.grep_files(trip["pattern"], scope, word=False)
                    if not TEST_FILE.search(h) and not under(h, bundle_rel)]
            if hits:
                shown = ", ".join(hits[:3]) + ("…" if len(hits) > 3 else "")
                findings.append(f"V13 {rel}: guardrail violated — forbidden `{trip['pattern']}` "
                                f"found in {shown}")
        if not enforced and not trips:
            notes.append(f"V14 {rel}: Guardrail is documented but not enforced — no enforced_by, "
                         f"no forbids")


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
    concepts = walk(bundle)
    concept_sources = {rel: source_paths(data, repo_root)
                       for rel, (_, data, _) in concepts.items() if data}
    bundle_rel = os.path.relpath(bundle, repo_root)

    # Pass 2: verify.
    for rel in sorted(concepts):
        _, data, body = concepts[rel]
        verify_concept(rel, data, body, bundle_rel, repo_root, repo, concept_sources)

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
