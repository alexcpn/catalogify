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
#   - reverts/hotfixes touching the path (subjects matching revert/hotfix/fix),
#     each with the files the commit touched. A commit that changed ONLY test
#     files is marked [TEST-ONLY]: it is test hygiene, not a production
#     invariant, and must not be cited as a gotcha.

set -euo pipefail

LIMIT="${OKF_HISTORY_LIMIT:-20}"
# Files shown per flagged commit before "+N more". Keeps a 300-file refactor
# from flooding the agent's context.
FILES_SHOWN="${OKF_HISTORY_FILES_SHOWN:-8}"
PATCH=0
JSON=0
PATHS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit) LIMIT="${2:-20}"; shift 2 ;;
    --patch) PATCH=1; shift ;;
    --json) JSON=1; shift ;;
    -h|--help)
      sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
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

# A path is a test file if it matches any of these. Covers Go, Python,
# JS/TS, Java, C#, Rust, Ruby, and the usual fixture/testdata directories.
# One regex, shared by text and JSON modes so the two never disagree.
TEST_FILE_RE='(^|/)(tests?|testing|testdata|__tests__|fixtures?|spec)/|(^|/)test_[^/]*\.py$|_test\.(go|py|rs|rb)$|\.(test|spec)\.[jt]sx?$|Tests?\.(java|cs|kt|scala)$|_spec\.rb$'

# --- per-path collectors ---------------------------------------------------

path_count()   { git log --no-merges --follow --format='%h' -- "$1" 2>/dev/null | wc -l | tr -d ' '; }
path_created() { git log --no-merges --follow --diff-filter=A --format='%h%x09%cI%x09%an%x09%s' -- "$1" 2>/dev/null | tail -1; }
path_recent()  { git log --no-merges --follow -n "$LIMIT" --format='%h%x09%cI%x09%s' -- "$1" 2>/dev/null; }
path_fixes()   { git log --no-merges --follow -n 200 --format='%h%x09%cI%x09%s' -- "$1" 2>/dev/null \
                   | grep -iE $'\t''.*(revert|hotfix|regress|CVE-|security|race|deadlock|leak|corrupt|rollback)' || true; }
# Every file the commit touched, repo-wide — not limited to the queried path,
# because "test-only" is a property of the commit, not of the slice we asked for.
commit_files() { git show --name-only --format= "$1" 2>/dev/null | grep -v '^$' || true; }

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
  local fixes; fixes="$(path_fixes "$p")"
  if [[ -n "$fixes" ]]; then
    echo
    echo "reverts / hotfixes / risk-flagged commits (gotcha signals):"
    local test_only_seen=0
    while IFS=$'\t' read -r sha date subj; do
      local files total shown test_only=1 f
      files="$(commit_files "$sha")"
      total=0
      if [[ -n "$files" ]]; then
        while IFS= read -r f; do
          total=$((total + 1))
          if ! [[ "$f" =~ $TEST_FILE_RE ]]; then test_only=0; fi
        done <<<"$files"
      else
        test_only=0   # no file list (odd object); don't claim anything
      fi
      if [[ "$test_only" -eq 1 ]]; then
        printf '  %s  %s  %s  [TEST-ONLY]\n' "$sha" "$date" "$subj"
        test_only_seen=1
      else
        printf '  %s  %s  %s\n' "$sha" "$date" "$subj"
      fi
      if [[ "$total" -gt 0 ]]; then
        shown=0
        while IFS= read -r f; do
          shown=$((shown + 1))
          if [[ "$shown" -le "$FILES_SHOWN" ]]; then
            printf '      %s\n' "$f"
          fi
        done <<<"$files"
        if [[ "$total" -gt "$FILES_SHOWN" ]]; then
          printf '      +%d more file(s)\n' "$((total - FILES_SHOWN))"
        fi
      fi
    done <<<"$fixes"
    if [[ "$test_only_seen" -eq 1 ]]; then
      echo
      echo "  [TEST-ONLY] = every file in the commit is a test file. Test hygiene,"
      echo "  not a production invariant — do not cite these as gotchas."
    fi
  fi
  if [[ "$PATCH" -eq 1 ]]; then
    echo
    echo "recent diffs (truncated to 200 lines — SCRUB SECRETS before use):"
    git log --no-merges --follow -n 3 -p --format='--- %h %cI %s' -- "$p" 2>/dev/null | head -200 || true
  fi
  echo
}

emit_json() {
  # Build one JSON object per path via python for correct escaping.
  python3 - "$LIMIT" "$TEST_FILE_RE" "$@" <<'PYEOF'
import json, re, subprocess, sys

limit = sys.argv[1]
test_file_re = re.compile(sys.argv[2])
paths = sys.argv[3:]

RISK_RE = re.compile(r"revert|hotfix|regress|CVE-|security|race|deadlock|leak|corrupt|rollback", re.I)

def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=False).stdout
    except Exception:
        return ""

def rows(out):
    r = []
    for ln in out.splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        r.append(parts)
    return r

def commit_files(sha):
    out = run(["git", "show", "--name-only", "--format=", sha])
    return [ln for ln in out.splitlines() if ln.strip()]

result = []
for p in paths:
    count = run(["git", "log", "--no-merges", "--follow", "--format=%h", "--", p])
    created = rows(run(["git", "log", "--no-merges", "--follow", "--diff-filter=A",
                        "--format=%h\t%cI\t%an\t%s", "--", p]))
    recent = rows(run(["git", "log", "--no-merges", "--follow", "-n", str(limit),
                       "--format=%h\t%cI\t%s", "--", p]))
    scanned = rows(run(["git", "log", "--no-merges", "--follow", "-n", "200",
                        "--format=%h\t%cI\t%s", "--", p]))
    flagged = []
    for r in scanned:
        if len(r) < 3:
            continue
        subject = "\t".join(r[2:])
        if not RISK_RE.search(subject):
            continue
        files = commit_files(r[0])
        flagged.append({
            "sha": r[0], "date": r[1], "subject": subject,
            "files": files,
            # False when the file list is empty: never claim test-only without evidence.
            "test_only": bool(files) and all(test_file_re.search(f) for f in files),
        })
    obj = {
        "path": p,
        "commit_count": len([l for l in count.splitlines() if l.strip()]),
        "created": (lambda c: {"sha": c[0], "date": c[1], "author": c[2],
                               "subject": "\t".join(c[3:])} if c and len(c) >= 4 else None)(
                       created[-1] if created else None),
        "recent": [{"sha": r[0], "date": r[1], "subject": "\t".join(r[2:])}
                   for r in recent if len(r) >= 3],
        "flagged": flagged,
    }
    result.append(obj)

print(json.dumps(result, indent=2))
PYEOF
}

if [[ "$JSON" -eq 1 ]]; then
  emit_json "${PATHS[@]}"
else
  for p in "${PATHS[@]}"; do
    emit_text "$p"
  done
fi
