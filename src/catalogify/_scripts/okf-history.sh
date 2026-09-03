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
#   - reverts/hotfixes touching the path (subjects matching revert/hotfix/fix)

set -euo pipefail

LIMIT="${OKF_HISTORY_LIMIT:-20}"
PATCH=0
JSON=0
PATHS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit) LIMIT="${2:-20}"; shift 2 ;;
    --patch) PATCH=1; shift ;;
    --json) JSON=1; shift ;;
    -h|--help)
      sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'
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

# --- per-path collectors ---------------------------------------------------

path_count()   { git log --no-merges --follow --format='%h' -- "$1" 2>/dev/null | wc -l | tr -d ' '; }
path_created() { git log --no-merges --follow --diff-filter=A --format='%h%x09%cI%x09%an%x09%s' -- "$1" 2>/dev/null | tail -1; }
path_recent()  { git log --no-merges --follow -n "$LIMIT" --format='%h%x09%cI%x09%s' -- "$1" 2>/dev/null; }
path_fixes()   { git log --no-merges --follow -n 200 --format='%h%x09%cI%x09%s' -- "$1" 2>/dev/null \
                   | grep -iE $'\t''.*(revert|hotfix|regress|CVE-|security|race|deadlock|leak|corrupt|rollback)' || true; }

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
    printf '%s\n' "$fixes" | while IFS=$'\t' read -r sha date subj; do
      printf '  %s  %s  %s\n' "$sha" "$date" "$subj"
    done
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
  python3 - "$LIMIT" "$@" <<'PYEOF'
import json, subprocess, sys

limit = sys.argv[1]
paths = sys.argv[2:]

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
