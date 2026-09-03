#!/usr/bin/env bash
# okf-inventory.sh — deterministic repository inventory for the OKF
# enrichment agent. Emits JSON (default: a per-repo temp path, printed to
# stdout) and a short human-readable summary to stdout.
#
# The agent uses this as the factual substrate for concept planning so it
# doesn't have to guess the repo layout.
#
# Usage: okf-inventory.sh [output_path] [--config <okf-config.yml>]

set -euo pipefail

OUT=""
CONFIG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG="${2:-}"
      shift 2
      ;;
    *)
      OUT="$1"
      shift
      ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

OUT="${OUT:-${TMPDIR:-/tmp}/okf-inventory-$(basename "$ROOT")-$$.json}"
CAP="${OKF_INVENTORY_CAP:-150}"

# Default excludes, aligned with okf-config.template.yml's `exclude:` list.
DEFAULT_EXCLUDE='^(node_modules|\.git|dist|build|vendor|\.specify|specs)/|(^|/)[^/]*\.min\.js$'

# --- helpers ---------------------------------------------------------------

# Reads `okf.exclude` glob list from a config YAML (best-effort, no PyYAML
# dependency) and prints one alternation-ready regex fragment per line.
# Silent no-op (empty output) if $CONFIG is unset or unreadable.
config_exclude_regex() {
  if [[ -z "$CONFIG" || ! -f "$CONFIG" ]]; then
    return 0
  fi
  python3 - "$CONFIG" <<'PYEOF'
import re, sys

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
except OSError:
    sys.exit(0)

in_exclude = False
globs = []
for line in lines:
    stripped = line.strip()
    if re.match(r"^exclude\s*:\s*$", stripped):
        in_exclude = True
        continue
    if in_exclude:
        m = re.match(r"^-\s*[\"']?([^\"'#]+)[\"']?\s*(#.*)?$", stripped)
        if m:
            globs.append(m.group(1).strip())
            continue
        if stripped and not stripped.startswith("#"):
            # A non-list, non-comment line ends the exclude block.
            in_exclude = False

def glob_to_regex(g):
    # Minimal glob->regex: ** -> .*, * -> [^/]*, escape the rest.
    out = []
    i = 0
    while i < len(g):
        if g[i:i+2] == "**":
            out.append(".*")
            i += 2
        elif g[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(g[i]))
            i += 1
    return "^" + "".join(out) + "$"

for g in globs:
    print(glob_to_regex(g))
PYEOF
}

EXCLUDE_FRAGMENTS="$(config_exclude_regex || true)"
if [[ -n "$EXCLUDE_FRAGMENTS" ]]; then
  CONFIG_EXCLUDE_RE="$(printf '%s\n' "$EXCLUDE_FRAGMENTS" | paste -sd '|' -)"
else
  CONFIG_EXCLUDE_RE=""
fi

list_matching() {
  # $1 = regex on path; respects .gitignore via git ls-files when available.
  # Always applies the default exclude list, plus config excludes if present.
  local raw
  if git rev-parse --git-dir >/dev/null 2>&1; then
    raw="$(git ls-files || true)"
  else
    raw="$(find . -type f | sed 's|^\./||' || true)"
  fi
  printf '%s\n' "$raw" \
    | grep -vE "$DEFAULT_EXCLUDE" \
    | { if [[ -n "$CONFIG_EXCLUDE_RE" ]]; then grep -vE "$CONFIG_EXCLUDE_RE"; else cat; fi; } \
    | grep -E "$1" || true
}

to_json_array() { python3 -c '
import json, sys
print(json.dumps([l for l in sys.stdin.read().splitlines() if l.strip()]))'; }

# --- collect ---------------------------------------------------------------
# Whether this is a git repo at all. Everything git-derived below is empty
# when it is not, and consumers should branch on this rather than on an
# empty string that could equally mean "no remote configured".
# Python literals: this value is interpolated into the emitter heredoc below.
if git rev-parse --git-dir >/dev/null 2>&1; then IS_GIT_REPO=True; else IS_GIT_REPO=False; fi
REMOTE="$(git remote get-url origin 2>/dev/null || echo "")"
BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo "")"
HEAD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo "")"

# --- git history signals ---------------------------------------------------
# Bounded, deterministic history to inform *significance* (churn) and the
# *why* (recent commit subjects). All heavy scans are capped so this stays
# cheap on large repos. Skipped cleanly when not a git repo.
HIST_COMMITS="${OKF_HISTORY_COMMITS:-2000}"   # how many recent commits to scan for churn
HIST_RECENT="${OKF_HISTORY_RECENT:-20}"       # how many recent subjects to surface
CHURN_TOP="${OKF_CHURN_TOP:-30}"              # top-N hottest files to report

# Take the first N lines WITHOUT closing the pipe early.
#
# `head -N` exits as soon as it has N lines, which sends SIGPIPE to whatever is
# still writing upstream. Under `set -o pipefail` that surfaces as exit 141 and
# `set -e` then aborts the whole script. It only bites on repositories large
# enough that the upstream producer is still writing when head leaves — which is
# exactly the case this tool is for (first reproduced on kubernetes/kubernetes:
# 500k LOC, 140k commits). awk drains its input to EOF, so nothing upstream ever
# sees a closed pipe.
take() {
  awk -v n="$1" 'NR<=n'
}

apply_excludes() {
  grep -vE "$DEFAULT_EXCLUDE" \
    | { if [[ -n "$CONFIG_EXCLUDE_RE" ]]; then grep -vE "$CONFIG_EXCLUDE_RE"; else cat; fi; }
}

CHURN=""
RECENT_COMMITS=""
COMMITS_SCANNED="0"
if git rev-parse --git-dir >/dev/null 2>&1; then
  # Churn: commit-count per file across the last $HIST_COMMITS non-merge
  # commits. A proxy for "which files carry the most history/gotchas".
  CHURN="$(git log --no-merges -n "$HIST_COMMITS" --pretty=format: --name-only 2>/dev/null \
    | sed '/^$/d' \
    | apply_excludes \
    | sort | uniq -c | sort -rn | take "$CHURN_TOP" \
    | awk '{c=$1; $1=""; sub(/^ /,""); printf "%s\t%s\n", c, $0}')"
  # Recent commit subjects (no merges) — cheap signal for the "why".
  RECENT_COMMITS="$(git log --no-merges -n "$HIST_RECENT" --pretty=format:'%h%x09%cI%x09%s' 2>/dev/null || true)"
  COMMITS_SCANNED="$(git rev-list --no-merges --count -n "$HIST_COMMITS" HEAD 2>/dev/null || echo 0)"
fi

ALL_FILES="$(list_matching '.')"
FILE_COUNT="$(printf '%s\n' "$ALL_FILES" | sed '/^$/d' | wc -l | tr -d ' ')"

# Language histogram by extension (top 15)
LANG_HIST="$(printf '%s\n' "$ALL_FILES" | sed '/^$/d' \
  | awk -F. 'NF>1 {print $NF}' | sort | uniq -c | sort -rn | take 15 \
  | awk '{printf "%s:%s\n", $2, $1}')"

# Each category: raw match count vs capped count, so the caller can detect
# truncation. take "$CAP" applied uniformly across every category.
raw_count() { list_matching "$1" | sed '/^$/d' | wc -l | tr -d ' '; }

MANIFESTS_RE='(^|/)(package\.json|pyproject\.toml|setup\.py|requirements[^/]*\.txt|go\.mod|Cargo\.toml|pom\.xml|build\.gradle(\.kts)?|Gemfile|composer\.json|\.csproj)$'
ENTRYPOINTS_RE='(^|/)(main|app|index|server|cli|manage|__main__)\.(py|js|ts|go|rs|rb|java|cs)$'
API_DEFS_RE='\.(proto|avsc|graphql|gql)$|(^|/)(openapi|swagger)[^/]*\.(ya?ml|json)$'
ROUTES_RE='(rout|controller|endpoint|handler|view|resource)s?[^/]*\.(py|js|ts|go|rb|java|cs|php)$'
DB_FILES_RE='(^|/)(migrations?|alembic|db/migrate)/|(model|schema|entit)[^/]*\.(py|js|ts|go|rb|java|cs|sql|prisma)$'
OPS_FILES_RE='(^|/)(Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|Makefile|Procfile|[^/]*\.tf|helm/.*|k8s/.*\.ya?ml|\.github/workflows/.*\.ya?ml|\.gitlab-ci\.yml|Jenkinsfile|cloudbuild\.ya?ml)$'
DOCS_RE='(^|/)(README[^/]*|CONTRIBUTING[^/]*|CHANGELOG[^/]*|ARCHITECTURE[^/]*|docs?/.*)\.(md|rst|txt)$'
CONFIGS_RE='(^|/)(config|settings|conf)[^/]*\.(py|js|ts|ya?ml|json|toml|ini|env\.example)$'
# ADR / design-decision docs (rationale goldmine) — matched separately from
# generic docs so the planner can seed `references/` and Design Decision concepts.
ADR_RE='(^|/)(adr|adrs|decisions?|rfcs?)/|(^|/)(ADR|RFC)[-_0-9]'

MANIFESTS="$(list_matching "$MANIFESTS_RE" | take "$CAP")"
ENTRYPOINTS="$(list_matching "$ENTRYPOINTS_RE" | take "$CAP")"
API_DEFS="$(list_matching "$API_DEFS_RE" | take "$CAP")"
ROUTES="$(list_matching "$ROUTES_RE" | take "$CAP")"
DB_FILES="$(list_matching "$DB_FILES_RE" | take "$CAP")"
OPS_FILES="$(list_matching "$OPS_FILES_RE" | take "$CAP")"
DOCS="$(list_matching "$DOCS_RE" | take "$CAP")"
CONFIGS="$(list_matching "$CONFIGS_RE" | take "$CAP")"
ADR_DOCS="$(list_matching "$ADR_RE" | take "$CAP")"

MANIFESTS_RAW="$(raw_count "$MANIFESTS_RE")"
ENTRYPOINTS_RAW="$(raw_count "$ENTRYPOINTS_RE")"
API_DEFS_RAW="$(raw_count "$API_DEFS_RE")"
ROUTES_RAW="$(raw_count "$ROUTES_RE")"
DB_FILES_RAW="$(raw_count "$DB_FILES_RE")"
OPS_FILES_RAW="$(raw_count "$OPS_FILES_RE")"
DOCS_RAW="$(raw_count "$DOCS_RE")"
CONFIGS_RAW="$(raw_count "$CONFIGS_RE")"
ADR_DOCS_RAW="$(raw_count "$ADR_RE")"

# Top-level directory sizes (proxy for module significance)
TOPDIRS="$(printf '%s\n' "$ALL_FILES" | sed '/^$/d' | awk -F/ 'NF>1 {print $1}' | sort | uniq -c | sort -rn | take 20 | awk '{printf "%s:%s\n", $2, $1}')"

# --- emit ------------------------------------------------------------------
python3 - "$OUT" "$CAP" <<PYEOF
import json, sys, os

def lines(s): return [l for l in s.splitlines() if l.strip()]

cap = int(sys.argv[2])

def category(name_lines, raw_count):
    items = lines(name_lines)
    return {"items": items, "truncated": raw_count > len(items)}

categories = {
  "dependency_manifests": category("""$MANIFESTS""", int("$MANIFESTS_RAW" or 0)),
  "entrypoints": category("""$ENTRYPOINTS""", int("$ENTRYPOINTS_RAW" or 0)),
  "api_definitions": category("""$API_DEFS""", int("$API_DEFS_RAW" or 0)),
  "route_like_files": category("""$ROUTES""", int("$ROUTES_RAW" or 0)),
  "data_layer_files": category("""$DB_FILES""", int("$DB_FILES_RAW" or 0)),
  "ops_files": category("""$OPS_FILES""", int("$OPS_FILES_RAW" or 0)),
  "docs": category("""$DOCS""", int("$DOCS_RAW" or 0)),
  "config_files": category("""$CONFIGS""", int("$CONFIGS_RAW" or 0)),
  "adr_docs": category("""$ADR_DOCS""", int("$ADR_DOCS_RAW" or 0)),
}

def churn_list(raw):
    out = []
    for ln in lines(raw):
        parts = ln.split("\t", 1)
        if len(parts) == 2:
            count, path = parts
            try:
                out.append({"file": path.strip(), "commits": int(count.strip())})
            except ValueError:
                pass
    return out

def recent_list(raw):
    out = []
    for ln in lines(raw):
        parts = ln.split("\t")
        if len(parts) >= 3:
            out.append({"sha": parts[0], "date": parts[1], "subject": "\t".join(parts[2:])})
    return out

churn = churn_list("""$CHURN""")

inv = {
  "root": os.getcwd(),
  "git": {
    "is_git_repo": $IS_GIT_REPO,
    "remote": """$REMOTE""",
    "branch": """$BRANCH""",
    "head": """$HEAD_SHA""",
    "history": {
      "commits_scanned": int("$COMMITS_SCANNED" or 0),
      "churn": churn,                              # hottest files (commit count desc)
      "recent_commits": recent_list("""$RECENT_COMMITS"""),
      "churn_truncated": len(churn) >= int("$CHURN_TOP" or 0) > 0,
    },
  },
  "file_count": int("$FILE_COUNT" or 0),
  "cap": cap,
  "language_histogram": dict(x.split(":") for x in lines("""$LANG_HIST""")),
  "top_level_dirs": dict(x.split(":") for x in lines("""$TOPDIRS""")),
  **{k: v["items"] for k, v in categories.items()},
  "truncated": {k: v["truncated"] for k, v in categories.items() if v["truncated"]},
}
with open(sys.argv[1], "w") as f:
    json.dump(inv, f, indent=2)

print(f"Inventory written to {sys.argv[1]}")
if inv["git"]["is_git_repo"]:
    print(f"  files: {inv['file_count']}  head: {inv['git']['head']}  branch: {inv['git']['branch']}")
else:
    print(f"  files: {inv['file_count']}  (not a git repository - no history signals)")
hist = inv["git"]["history"]
print(f"  git history: {hist['commits_scanned']} commits scanned, "
      f"{len(hist['churn'])} hot files, {len(hist['recent_commits'])} recent subjects")
for k in ("dependency_manifests","entrypoints","api_definitions","route_like_files",
          "data_layer_files","ops_files","docs","config_files","adr_docs"):
    flag = " (truncated)" if k in inv["truncated"] else ""
    print(f"  {k}: {len(inv[k])}{flag}")
PYEOF
