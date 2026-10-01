#!/usr/bin/env bash
# okf-history.sh — per-path git history for the OKF enrichment agent.
#
# The inventory script gives repo-wide churn signals; this gives the *why*
# for ONE concept: how a file/dir came to be and how it has changed. The
# agent calls it while writing or refreshing a concept to ground the
# "purpose / invariants / gotchas / why it is shaped this way" narrative
# and to cite commits (OKF §8).
#
# Deliberately bounded and diff-free by default so it stays cheap and never
# leaks secrets from historical diffs. Use --patch only when you explicitly
# need the change content, and still scrub secrets before writing them into
# the bundle.
#
# Usage:
#   okf-history.sh <path> [<path> ...]        # summary for each path
#   okf-history.sh --limit 30 <path>          # cap recent commits (default 20)
#   okf-history.sh --patch <path>             # include truncated diffs (careful)
#   okf-history.sh --json <path>              # machine-readable output
#
# Output (text mode) per path:
#   - creation commit (first time the path appears, follows renames)
#   - total non-merge commit count touching the path
#   - most recent non-merge commits (sha, ISO date, subject)
#   - flagged commits touching the path, each with the files it touched:
#       risk    subject mentions revert/hotfix/regression/race/deadlock/leak/...
#       closes  message closes an issue ("Fixes #842", "Closes org/repo#12",
#               "Resolves https://.../issues/12") — read from the full message,
#               not just the subject
#       fixes   message carries a "Fixes: <sha>" trailer naming the commit
#               that introduced the bug
#     plus the issue/PR refs in the message and a short excerpt of its body,
#     where the rationale usually lives. A commit that changed ONLY test
#     files is marked [TEST-ONLY]: it is test hygiene, not a production
#     invariant, and must not be cited as a gotcha.
#
#   OKF_HISTORY_BODY_CHARS caps the body excerpt (default 240; 0 omits it).

set -euo pipefail

LIMIT="${OKF_HISTORY_LIMIT:-20}"
# Files shown per flagged commit before "+N more". Keeps a 300-file refactor
# from flooding the agent's context.
FILES_SHOWN="${OKF_HISTORY_FILES_SHOWN:-8}"
BODY_CHARS="${OKF_HISTORY_BODY_CHARS:-240}"
PATCH=0
JSON=0
PATHS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit) LIMIT="${2:-20}"; shift 2 ;;
    --patch) PATCH=1; shift ;;
    --json) JSON=1; shift ;;
    -h|--help)
      sed -n '2,37p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    --) shift; while [[ $# -gt 0 ]]; do PATHS+=("$1"); shift; done ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) PATHS+=("$1"); shift ;;
  esac
done

if [[ ${#PATHS[@]} -eq 0 ]]; then
  echo "usage: okf-history.sh [--limit N] [--patch] [--json] <path> [<path> ...]" >&2
  exit 2
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "okf-history: not a git repository — no history available." >&2
  exit 0
fi

# A shallow clone has no history to mine, and says so nowhere: `git log`
# simply returns the few commits that were fetched. Every risk-flagged
# commit, every revert, every rule this script exists to surface is absent,
# and the output looks like a quiet repository rather than a truncated one.
# Warn loudly, because a bundle generated here will be honest and hollow.
if [[ "$(git rev-parse --is-shallow-repository 2>/dev/null)" == "true" ]]; then
  cat >&2 <<'SHALLOW'
okf-history: WARNING — this is a SHALLOW clone. Git has only the most recent
  commits, so history mining will find little or nothing, and any concept
  written from it will have no gotchas and no citations. That is a truncated
  repository, not a quiet one.

  Fix it before generating:  git fetch --unshallow
  Or fetch enough depth:     git fetch --deepen=2000
SHALLOW
fi

# A path is a test file if it matches any of these. Covers Go, Python,
# JS/TS, Java, C#, Rust, Ruby, and the usual fixture/testdata directories.
# One regex, shared by text and JSON modes so the two never disagree.
TEST_FILE_RE='(^|/)(tests?|testing|testdata|__tests__|fixtures?|spec)/|(^|/)test_[^/]*\.py$|_test\.(go|py|rs|rb)$|\.(test|spec)\.[jt]sx?$|Tests?\.(java|cs|kt|scala)$|_spec\.rb$'

# --- per-path collectors ---------------------------------------------------

path_count()   { git log --no-merges --follow --format='%h' -- "$1" 2>/dev/null | wc -l | tr -d ' '; }
path_created() { git log --no-merges --follow --diff-filter=A --format='%h%x09%cI%x09%an%x09%s' -- "$1" 2>/dev/null | tail -1; }
path_recent()  { git log --no-merges --follow -n "$LIMIT" --format='%h%x09%cI%x09%s' -- "$1" 2>/dev/null; }

# The flagged-commit scan is shared by text and JSON modes, so it lives in one
# place. Messages are read in full (subject + body): "Fixes #842" and the
# rationale are usually in the body, which a subject-only grep never sees.
read -r -d '' FLAG_PY <<'PYEOF' || true
import re, subprocess

RISK_RE = re.compile(r"revert|hotfix|regress|CVE-|security|race|deadlock|leak|corrupt|rollback", re.I)
# GitHub/GitLab closing keywords followed by an issue ref.
CLOSES_RE = re.compile(
    r"(?:^|[^A-Za-z])(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):? +"
    r"((?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?#[0-9]+|https?://\S+/issues/[0-9]+)", re.I)
# Linux-kernel style trailer naming the commit that introduced the bug.
FIXES_TRAILER_RE = re.compile(r"^fixes: *([0-9a-f]{7,40})\b", re.I | re.M)
# Any issue/PR reference, closing or not: #12, org/repo#12, tracker URLs.
REF_RE = re.compile(
    r"(?:^|(?<=[^A-Za-z0-9_&]))((?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?#[0-9]+)"
    r"|(https?://[^\s)>]+/(?:issues|pull|merge_requests)/[0-9]+)")
TRAILER_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: ")
CLOSING_LINE_RE = re.compile(r"^\s*(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):? +\S+[\s,.]*$", re.I)

def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=False).stdout
    except Exception:
        return ""

def rows(out):
    return [ln.split("\t") for ln in out.splitlines() if ln.strip()]

# Every file the commit touched, repo-wide — not limited to the queried path,
# because "test-only" is a property of the commit, not of the slice we asked for.
def commit_files(sha):
    out = run(["git", "show", "--name-only", "--format=", sha])
    return [ln for ln in out.splitlines() if ln.strip()]

def excerpt(body, limit):
    if limit <= 0:
        return ""
    # Lines that only close an issue ("Fixes #842") are already in `refs`.
    lines = [l for l in body.strip().splitlines() if not CLOSING_LINE_RE.match(l)]
    paras = [p for p in re.split(r"\n\s*\n", "\n".join(lines)) if p.strip()]
    # Drop the trailer block (Signed-off-by:, Co-Authored-By:, Fixes:, ...).
    if paras and all(TRAILER_LINE_RE.match(l) for l in paras[-1].splitlines() if l.strip()):
        paras = paras[:-1]
    text = " ".join(" ".join(paras).split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"

def dedupe(xs):
    seen = []
    for x in xs:
        if x not in seen:
            seen.append(x)
    return seen

def scan_flagged(path, test_file_re, body_chars):
    out = run(["git", "log", "--no-merges", "--follow", "-n", "200", "-z",
               "--format=%h%x1f%cI%x1f%s%x1f%b", "--", path])
    flagged = []
    for rec in out.split("\0"):
        parts = rec.strip("\n").split("\x1f", 3)
        if len(parts) < 3:
            continue
        sha, date, subject = parts[0], parts[1], parts[2]
        body = parts[3] if len(parts) > 3 else ""
        message = subject + "\n\n" + body
        closes = dedupe(CLOSES_RE.findall(message))
        fixes = dedupe(FIXES_TRAILER_RE.findall(body))
        reasons = (["risk"] if RISK_RE.search(subject) else []) \
            + (["closes"] if closes else []) + (["fixes"] if fixes else [])
        if not reasons:
            continue
        files = commit_files(sha)
        flagged.append({
            "sha": sha, "date": date, "subject": subject,
            "reasons": reasons,
            "closes": closes,
            "refs": dedupe(a or b for a, b in REF_RE.findall(message)),
            "fixes_commits": fixes,
            "message_excerpt": excerpt(body, body_chars),
            "files": files,
            # False when the file list is empty: never claim test-only without evidence.
            "test_only": bool(files) and all(test_file_re.search(f) for f in files),
        })
    return flagged
PYEOF

# Text rendering of the flagged section for one path.
read -r -d '' FLAG_TEXT_PY <<'PYEOF' || true
import sys
test_file_re, files_shown, body_chars, path = re.compile(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
flagged = scan_flagged(path, test_file_re, body_chars)
if flagged:
    print()
    print("flagged commits (gotcha signals: risk / closes issue / fixes commit):")
    for c in flagged:
        tag = "  [TEST-ONLY]" if c["test_only"] else ""
        print(f"  {c['sha']}  {c['date']}  {c['subject']}{tag}")
        print(f"      flagged: {', '.join(c['reasons'])}")
        if c["refs"]:
            print(f"      refs:    {', '.join(c['refs'])}")
        if c["fixes_commits"]:
            print(f"      fixes commit: {', '.join(c['fixes_commits'])}")
        if c["message_excerpt"]:
            print(f"      message: {c['message_excerpt']}")
        for f in c["files"][:files_shown]:
            print(f"      {f}")
        if len(c["files"]) > files_shown:
            print(f"      +{len(c['files']) - files_shown} more file(s)")
    if any(c["test_only"] for c in flagged):
        print()
        print("  [TEST-ONLY] = every file in the commit is a test file. Test hygiene,")
        print("  not a production invariant — do not cite these as gotchas.")
PYEOF

emit_text() {
  local p="$1"
  echo "=============================================================="
  echo "PATH: $p"
  echo "--------------------------------------------------------------"
  local count created
  count="$(path_count "$p")"
  created="$(path_created "$p")"
  echo "commits (non-merge, --follow): ${count:-0}"
  if [[ -n "$created" ]]; then
    IFS=$'\t' read -r c_sha c_date c_author c_subj <<<"$created"
    echo "created:  $c_sha  $c_date  by $c_author"
    echo "          $c_subj"
  fi
  echo
  echo "recent commits (up to $LIMIT):"
  local recent; recent="$(path_recent "$p")"
  if [[ -n "$recent" ]]; then
    printf '%s\n' "$recent" | while IFS=$'\t' read -r sha date subj; do
      printf '  %s  %s  %s\n' "$sha" "$date" "$subj"
    done
  else
    echo "  (none)"
  fi
  python3 -c "$FLAG_PY"$'\n'"$FLAG_TEXT_PY" "$TEST_FILE_RE" "$FILES_SHOWN" "$BODY_CHARS" "$p"
  if [[ "$PATCH" -eq 1 ]]; then
    echo
    echo "recent diffs (truncated to 200 lines — SCRUB SECRETS before use):"
    git log --no-merges --follow -n 3 -p --format='--- %h %cI %s' -- "$p" 2>/dev/null | head -200 || true
  fi
  echo
}

emit_json() {
  # Build one JSON object per path via python for correct escaping.
  python3 -c "$FLAG_PY"$'\n'"$(cat <<'PYEOF'
import json, sys

limit = sys.argv[1]
test_file_re = re.compile(sys.argv[2])
body_chars = int(sys.argv[3])
paths = sys.argv[4:]

result = []
for p in paths:
    count = run(["git", "log", "--no-merges", "--follow", "--format=%h", "--", p])
    created = rows(run(["git", "log", "--no-merges", "--follow", "--diff-filter=A",
                        "--format=%h\t%cI\t%an\t%s", "--", p]))
    recent = rows(run(["git", "log", "--no-merges", "--follow", "-n", str(limit),
                       "--format=%h\t%cI\t%s", "--", p]))
    obj = {
        "path": p,
        "commit_count": len([l for l in count.splitlines() if l.strip()]),
        "created": (lambda c: {"sha": c[0], "date": c[1], "author": c[2],
                               "subject": "\t".join(c[3:])} if c and len(c) >= 4 else None)(
                       created[-1] if created else None),
        "recent": [{"sha": r[0], "date": r[1], "subject": "\t".join(r[2:])}
                   for r in recent if len(r) >= 3],
        "flagged": scan_flagged(p, test_file_re, body_chars),
    }
    result.append(obj)

print(json.dumps(result, indent=2))
PYEOF
)" "$LIMIT" "$TEST_FILE_RE" "$BODY_CHARS" "$@"
}

if [[ "$JSON" -eq 1 ]]; then
  emit_json "${PATHS[@]}"
else
  for p in "${PATHS[@]}"; do
    emit_text "$p"
  done
fi
