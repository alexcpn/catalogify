#!/usr/bin/env bash
# Run SkillEvaluator's live (Tier 3) evaluation of the catalogify skill.
#
# SkillEvaluator expects evals/ inside the skill directory. The evals are kept
# here instead, so they never ship in the wheel, the Cursor plugin or a user's
# installed skill. This script stages the published skill plus these evals in
# .stage/ and runs the evaluator there. Extra arguments go to `tier3 evaluate`.
#
#   ./integrations/skillevaluator/run.sh
#   ./integrations/skillevaluator/run.sh --max-cases 1 --n-attempts 1
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
stage="$here/.stage/catalogify"

rm -rf "$stage"
mkdir -p "$stage"
cp -R "$root/plugins/catalogify/skills/catalogify/." "$stage/"
cp -R "$here/evals" "$stage/evals"
chmod +x "$stage/evals/grader.py"

skillevaluator tier3 validate "$stage" --harbor-contract
skillevaluator tier3 evaluate "$stage" --agents claude-code --env-mode docker "$@"

echo "Results: $stage/evals/results"
