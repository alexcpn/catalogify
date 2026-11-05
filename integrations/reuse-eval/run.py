#!/usr/bin/env python3
"""Does an existing catalogify bundle help an agent? A/B runner.

catalogify is meant to be run once per repository and then reused: the bundle
is committed next to the code and every later agent session reads it. This
measures that use. Claude Code runs headless in Docker on the same Airflow
checkout with the same prompt, in two arms:

  bundle  knowledge/ from fixtures/ is committed in the repo, and one line in
          AGENTS.md points at it
  none    the checkout as it is

Neither arm has the catalogify skill installed, so the bundle is the only
difference. Subcommands:

  run.py bundle              build the fixture bundle once (catalogify skill, in Docker)
  run.py trials [-n 3]       run every task in both arms, n attempts each
  run.py summary             aggregate results/ into results/SUMMARY.md

Credentials: an Anthropic-compatible key read from the file in $REUSE_EVAL_KEY_FILE
(default ~/.openrouter.key) and passed to the container through the environment.
ANTHROPIC_BASE_URL defaults to OpenRouter; the model to anthropic/claude-sonnet-5-5.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMAGE = "catalogify-reuse-eval:latest"
BASE_IMAGE = "catalogify-eval-airflow:base"
FIXTURE = HERE / "fixtures" / "airflow-metrics-knowledge"
RESULTS = HERE / "results"
UPSTREAM_SHA = "b03e48a875d991ad42b9d81efb7e75e001879404"

MODEL = os.environ.get("REUSE_EVAL_MODEL", "anthropic/claude-sonnet-5-5")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
KEY_FILE = Path(os.environ.get("REUSE_EVAL_KEY_FILE", "~/.openrouter.key")).expanduser()

POINTER = (
    "\n## Knowledge bundle\n\n"
    "`knowledge/` is an OKF knowledge bundle for the metrics code (shared/observability, "
    "airflow-core and task-sdk metrics clients), generated from the code and its git history. "
    "Start with `knowledge/index.md` and `knowledge/architecture/overview.md` before exploring "
    "that code.\n"
)

BUNDLE_PROMPT = (
    "Use the catalogify skill to build an OKF knowledge bundle in `knowledge/` for the metrics "
    "code of this Apache Airflow checkout. Scope it to the StatsD, Datadog and OpenTelemetry "
    "metrics clients in `shared/observability/src/airflow_shared/observability/metrics/`, "
    "`airflow-core/src/airflow/observability/metrics/` and "
    "`task-sdk/src/airflow/sdk/observability/metrics/`. Do not change any source code. When the "
    "bundle passes `catalogify validate` and `catalogify verify`, stop."
)

TASKS = {
    "feature": (
        "You are working in a checkout of Apache Airflow. Implement this feature request "
        "(apache/airflow#70666):\n\n"
        "> Airflow submits metrics through a network connection defined by host and port. However, "
        "the existing backends also support using an UDS socket but there is no way to configure "
        "that at the moment. A new `[metrics] statsd_socket_path` will be very useful to unlock "
        "this.\n\n"
        "The option is `[metrics] statsd_socket_path`, unset by default. When it is set, metrics go "
        "to that Unix Domain Socket instead of `statsd_host`/`statsd_port`, for both the StatsD "
        "backend and the Datadog backend. With it unset, behaviour must not change. Add unit tests. "
        "The test dependencies are installed in /opt/afvenv, for example "
        "`cd shared/observability && /opt/afvenv/bin/python -m pytest tests/observability/metrics/`.\n\n"
        "Work only from this checkout: do not fetch from the remote or look up the upstream change. "
        "Do not commit."
    ),
    "why": (
        "Answer from this Airflow checkout, without changing any files. Why does the task SDK have "
        "its own metrics wrapper (`task-sdk/src/airflow/sdk/observability/metrics/`) instead of "
        "importing airflow-core's, and what does that mean for someone changing how the StatsD "
        "client is configured? Cite the commit that introduced the split. Keep the answer under "
        "200 words."
    ),
}


# ----------------------------------------------------------------- docker

def build_images() -> None:
    env_dir = ROOT / "integrations" / "skillevaluator" / "evals" / "environment"
    subprocess.run(["docker", "build", "-q", "-t", BASE_IMAGE, str(env_dir)], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["docker", "build", "-q", "-t", IMAGE, "--build-arg", f"BASE={BASE_IMAGE}",
                    str(HERE)], check=True, stdout=subprocess.DEVNULL)


def agent_env() -> dict[str, str]:
    if not KEY_FILE.is_file():
        sys.exit(f"key file {KEY_FILE} not found (set REUSE_EVAL_KEY_FILE)")
    key = KEY_FILE.read_text().strip()
    return {
        **os.environ,
        "ANTHROPIC_BASE_URL": BASE_URL,
        "ANTHROPIC_API_KEY": key,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,   # side calls must also resolve on the gateway
        "ANTHROPIC_SMALL_FAST_MODEL": MODEL,
        # Claude Code reserves up to 128k output tokens per request by default, and a
        # gateway with a small balance refuses it (HTTP 402). No task here needs that.
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "16000",
    }


CONTAINER_SCRIPT = r"""
set -u
cd /workspace/airflow
if [ "$ARM" = bundle ]; then
  cp -R /eval/fixture knowledge
  cat /eval/pointer.md >> AGENTS.md
  git add knowledge AGENTS.md && git commit -qm "Add knowledge bundle for the metrics code"
fi
if [ "$ARM" = skill ]; then
  mkdir -p /root/.claude/skills && cp -R /eval/skill /root/.claude/skills/catalogify
fi
start=$(git rev-parse HEAD)
claude -p "$(cat /eval/prompt.txt)" --model "$MODEL" --output-format json \
  --dangerously-skip-permissions > /out/claude.json 2> /out/claude.stderr
echo $? > /out/claude.exit
GIT_NO_LAZY_FETCH=1 git cat-file -e "$UPSTREAM_SHA^{commit}" 2>/dev/null && echo 1 > /out/fetched_upstream || echo 0 > /out/fetched_upstream
git diff --stat "$start" > /out/diffstat.txt
git status --porcelain --untracked-files=all > /out/status.txt
git diff "$start" -- . ':(exclude)knowledge' > /out/diff.patch
if [ "$TASK" = feature ]; then
  python3 /eval/grade_feature.py /opt/afvenv/bin/python > /out/grade.json 2> /out/grade.stderr
fi
if [ "$ARM" = skill ] && [ -d knowledge ]; then
  rm -rf /out/knowledge && cp -R knowledge /out/knowledge
  uvx catalogify@0.10.1 validate knowledge --json > /out/validate.json 2>/dev/null
  uvx catalogify@0.10.1 verify knowledge --json > /out/verify.json 2>/dev/null
fi
"""


def run_container(task: str, arm: str, prompt: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ev = Path(tmp)
        (ev / "prompt.txt").write_text(prompt)
        (ev / "pointer.md").write_text(POINTER)
        (ev / "run.sh").write_text(CONTAINER_SCRIPT)
        shutil.copy(HERE / "grade_feature.py", ev / "grade_feature.py")
        if arm == "bundle":
            shutil.copytree(FIXTURE, ev / "fixture")
        if arm == "skill":
            shutil.copytree(ROOT / "plugins" / "catalogify" / "skills" / "catalogify", ev / "skill")
        cmd = ["docker", "run", "--rm", "-v", f"{ev}:/eval:ro", "-v", f"{out}:/out",
               "-e", "ANTHROPIC_BASE_URL", "-e", "ANTHROPIC_API_KEY",
               "-e", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "-e", "ANTHROPIC_SMALL_FAST_MODEL",
               "-e", "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
               "-e", f"MODEL={MODEL}", "-e", f"ARM={arm}", "-e", f"TASK={task}",
               "-e", f"UPSTREAM_SHA={UPSTREAM_SHA}", IMAGE, "bash", "/eval/run.sh"]
        subprocess.run(cmd, env=agent_env(), timeout=3600, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # files written as root inside the container; make them readable/removable here
    subprocess.run(["docker", "run", "--rm", "-v", f"{out}:/out", IMAGE, "chmod", "-R", "a+rwX", "/out"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ grading

def grade_why(answer: str) -> dict[str, float]:
    text = answer.lower()
    return {
        # Two commits split the metrics code: 337aee896a (#56187) created the task-sdk
        # package, 0d294caab3 (#62127) removed the airflow-core imports from shared/.
        "cites_split_commit": 1.0 if any(s in text for s in ("337aee8", "56187", "0d294ca", "62127")) else 0.0,
        "names_three_places": 1.0 if ("shared" in text and ("task-sdk" in text or "task sdk" in text)
                                      and "core" in text) else 0.0,
    }


def collect(out: Path, task: str) -> dict:
    rec: dict = {"dir": str(out.relative_to(HERE))}
    try:
        res = json.loads((out / "claude.json").read_text())
    except (OSError, json.JSONDecodeError):
        res = {}
    usage = res.get("usage") or {}
    if res.get("is_error") or not res:
        # An API or harness failure says nothing about the arm; keep it out of the means.
        rec.update({"error": (res.get("result") or "no result")[:300], "score": None})
        (out / "record.json").write_text(json.dumps(rec, indent=2))
        return rec
    rec.update({
        "ok": not res.get("is_error", True),
        "cost_usd": res.get("total_cost_usd"),
        "turns": res.get("num_turns"),
        "seconds": round((res.get("duration_ms") or 0) / 1000, 1),
        "input_tokens": sum(usage.get(k) or 0 for k in
                            ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
        "output_tokens": usage.get("output_tokens"),
        "fetched_upstream": (out / "fetched_upstream").read_text().strip() == "1"
        if (out / "fetched_upstream").exists() else None,
    })
    if task == "feature":
        try:
            g = json.loads((out / "grade.json").read_text())
            rec["score"] = g["passed"] / g["total"]
            rec["failed_checks"] = [k for k, v in g["checks"].items() if not v["pass"]]
        except (OSError, json.JSONDecodeError, KeyError):
            rec["score"] = 0.0
    else:
        m = grade_why(res.get("result") or "")
        rec.update(m)
        rec["score"] = sum(m.values()) / len(m)
        rec["answer"] = (res.get("result") or "")[:2000]
        rec["changed_files"] = bool((out / "status.txt").exists() and (out / "status.txt").read_text().strip())
    (out / "record.json").write_text(json.dumps(rec, indent=2))
    return rec


# ------------------------------------------------------------- subcommands

def cmd_bundle(_: argparse.Namespace) -> None:
    build_images()
    out = RESULTS / "bundle-build" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"building the fixture bundle with the catalogify skill -> {out}", flush=True)
    run_container("bundle", "skill", BUNDLE_PROMPT, out)
    rec = collect(out, "bundle")
    if not (out / "knowledge" / "index.md").is_file():
        sys.exit(f"no bundle produced; see {out}/claude.stderr")
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    shutil.copytree(out / "knowledge", FIXTURE)
    print(json.dumps({k: rec[k] for k in ("cost_usd", "turns", "seconds")}, indent=2))
    for name in ("validate.json", "verify.json"):
        if (out / name).exists():
            d = json.loads((out / name).read_text() or "{}")
            print(name, d.get("result"), "errors" if "errors" in d else "findings",
                  len(d.get("errors", d.get("findings", []))))
    print(f"fixture written to {FIXTURE.relative_to(ROOT)}")


def report(task: str, arm: str, i: int, rec: dict) -> None:
    if rec.get("error"):
        print(f"  {task:8} {arm:6} #{i}: ERROR {rec['error'][:100]}", flush=True)
    else:
        print(f"  {task:8} {arm:6} #{i}: score {rec['score']:.2f}  ${rec['cost_usd'] or 0:.2f}  "
              f"{rec['turns']} turns  {rec['seconds']}s", flush=True)


def cmd_retry(args: argparse.Namespace) -> None:
    """Re-run attempts of an earlier run that ended in an API error."""
    run = RESULTS / args.run
    build_images()
    for rec_path in sorted(run.glob("*/*/attempt-*/record.json")):
        out = rec_path.parent
        task, arm, i = out.parent.parent.name, out.parent.name, int(out.name.split("-")[1])
        if collect(out, task).get("error"):
            for f in out.iterdir():
                if f.is_file():
                    f.unlink()
            run_container(task, arm, TASKS[task], out)
            report(task, arm, i, collect(out, task))
    cmd_summary(argparse.Namespace(run=args.run))


def cmd_trials(args: argparse.Namespace) -> None:
    if not (FIXTURE / "index.md").is_file():
        sys.exit("no fixture bundle; run `run.py bundle` first")
    build_images()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    jobs = [(task, arm, i) for i in range(1, args.n + 1) for task in args.tasks for arm in ("bundle", "none")]
    print(f"{len(jobs)} trials, {args.parallel} at a time -> results/{stamp}", flush=True)

    def one(job):
        task, arm, i = job
        out = RESULTS / stamp / task / arm / f"attempt-{i}"
        run_container(task, arm, TASKS[task], out)
        rec = collect(out, task)
        report(task, arm, i, rec)
        return rec

    with cf.ThreadPoolExecutor(max_workers=args.parallel) as pool:
        list(pool.map(one, jobs))
    cmd_summary(argparse.Namespace(run=stamp))


def cmd_summary(args: argparse.Namespace) -> None:
    runs = sorted(p for p in RESULTS.iterdir() if p.is_dir() and re.match(r"\d{8}-\d{6}$", p.name))
    if not runs:
        sys.exit("no trial runs in results/")
    run = RESULTS / (args.run or runs[-1].name)
    lines = [f"# Bundle reuse: {run.name}", "", f"Model `{MODEL}`, Claude Code in Docker.", ""]
    lines += ["| Task | Arm | Attempts | Score (mean) | Cost $ (mean) | Turns (mean) | "
              "Seconds (mean) | Input tokens (mean) |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for task_dir in sorted(p for p in run.iterdir() if p.is_dir()):
        for arm in ("bundle", "none"):
            # Re-grade from the raw outputs so grader fixes apply to earlier runs.
            recs = [collect(p, task_dir.name) for p in sorted((task_dir / arm).glob("attempt-*"))]
            errors = sum(1 for r in recs if r.get("error"))
            recs = [r for r in recs if not r.get("error")]
            if not recs:
                continue

            def mean(key):
                vals = [r[key] for r in recs if isinstance(r.get(key), (int, float))]
                return statistics.mean(vals) if vals else float("nan")

            lines.append(f"| {task_dir.name} | {arm} | {len(recs)}{f' (+{errors} errored)' if errors else ''} | {mean('score'):.2f} | "
                         f"{mean('cost_usd'):.2f} | {mean('turns'):.1f} | {mean('seconds'):.0f} | "
                         f"{mean('input_tokens'):,.0f} |")
    lines += ["", "Per attempt:", ""]
    for rec_path in sorted(run.glob("*/*/attempt-*/record.json")):
        r = json.loads(rec_path.read_text())
        if r.get("error"):
            lines.append(f"- `{r['dir']}`: excluded, API error: {r['error'][:120]}")
            continue
        extra = r.get("failed_checks") or {k: r[k] for k in ("cites_split_commit", "names_three_places") if k in r}
        lines.append(f"- `{r['dir']}`: score {r['score']:.2f}, ${r.get('cost_usd') or 0:.2f}, "
                     f"{r.get('turns')} turns, fetched upstream: {r.get('fetched_upstream')}; {extra}")
    (run / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bundle").set_defaults(func=cmd_bundle)
    t = sub.add_parser("trials")
    t.add_argument("-n", type=int, default=3, help="attempts per task and arm")
    t.add_argument("--tasks", nargs="+", default=list(TASKS), choices=list(TASKS))
    t.add_argument("--parallel", type=int, default=2)
    t.set_defaults(func=cmd_trials)
    r = sub.add_parser("retry", help="re-run attempts that ended in an API error")
    r.add_argument("--run", required=True)
    r.set_defaults(func=cmd_retry)
    s = sub.add_parser("summary")
    s.add_argument("--run")
    s.set_defaults(func=cmd_summary)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
