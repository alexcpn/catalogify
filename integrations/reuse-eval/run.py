#!/usr/bin/env python3
"""Does an existing catalogify bundle help an agent? A/B runner.

catalogify is meant to be run once per repository and then reused: the bundle
is committed next to the code and every later agent session reads it. This
measures that use. Claude Code runs headless in Docker on an Airflow checkout
with the same prompt, in two arms:

  bundle  the scenario's fixture bundle is committed as knowledge/, and a short
          section in AGENTS.md points at it
  none    the checkout as it is

Neither arm has the catalogify skill installed, so the bundle is the only
difference. Each scenario pins its own Airflow commit (the parent of a real
upstream change), its bundle scope and its tasks.

  run.py bundle  -s SCENARIO           build the scenario's fixture bundle once (catalogify skill)
  run.py trials  -s SCENARIO [-n 3]    run its tasks in both arms, n attempts each
  run.py retry   -s SCENARIO --run X   re-run attempts that ended in an API error
  run.py summary -s SCENARIO [--run X] aggregate results/SCENARIO/X into SUMMARY.md

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
RESULTS = HERE / "results"
ENV_DIR = ROOT / "integrations" / "skillevaluator" / "evals" / "environment"
SKILL_DIR = ROOT / "plugins" / "catalogify" / "skills" / "catalogify"

MODEL = os.environ.get("REUSE_EVAL_MODEL", "anthropic/claude-sonnet-5-5")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
KEY_FILE = Path(os.environ.get("REUSE_EVAL_KEY_FILE", "~/.openrouter.key")).expanduser()


def pointer(what: str) -> str:
    return (
        "\n## Knowledge bundle\n\n"
        f"`knowledge/` is an OKF knowledge bundle for {what}, generated from the code and its git "
        "history. Start with `knowledge/index.md` and `knowledge/architecture/overview.md` before "
        "exploring that code.\n"
    )


def bundle_prompt(scope: str) -> str:
    return (
        f"Use the catalogify skill to build an OKF knowledge bundle in `knowledge/` for {scope} "
        "Do not change any source code. When the bundle passes `catalogify validate` and "
        "`catalogify verify`, stop."
    )


# --------------------------------------------------------------- scenarios

METRICS_FEATURE = (
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
)

METRICS_WHY = (
    "Answer from this Airflow checkout, without changing any files. Why does the task SDK have "
    "its own metrics wrapper (`task-sdk/src/airflow/sdk/observability/metrics/`) instead of "
    "importing airflow-core's, and what does that mean for someone changing how the StatsD "
    "client is configured? Cite the commit that introduced the split. Keep the answer under "
    "200 words."
)

# apache/airflow#64890, as the user filed it.
DAGRUN_NOTE_ISSUE = """\
> **Support updating DagRun note from notifier/callback context in Airflow 3**
>
> In Airflow 2, a common notifier/callback pattern was:
>
> 1. Post an alert to an external system such as Slack.
> 2. Persist a backlink or correlation identifier on the `DagRun` note.
> 3. Reuse that stored link later to update the original alert if the DagRun is cleared and eventually succeeds.
>
> That migration path is not straightforward in Airflow 3.
>
> In Airflow 3 callback/notifier code, `context["dag_run"]` is no longer the old SQLAlchemy `DagRun` contract that many Airflow 2 implementations relied on, and the Task SDK client does not appear to expose a supported helper for updating `DagRun.note` from callback/notifier runtime code.
>
> There is already public API support for DagRun note patching, so this request is specifically about having a supported callback-safe/runtime-safe way to do that from Airflow 3 notifier code.
>
> In Airflow 2 this was commonly done with ORM/session access such as `DagRunNote`, `dag_run.dag_run_note`, and `provide_session`. In Airflow 3 that pattern is not portable, but I could not find a supported replacement in notifier/callback context.
"""

DAGRUN_NOTE_PLAN = (
    "You are working in a checkout of Apache Airflow. A user filed this feature request "
    "(apache/airflow#64890):\n\n" + DAGRUN_NOTE_ISSUE + "\n"
    "Write an implementation plan for a maintainer to follow: every file that has to change or be "
    "created, and what changes in each, in the order the work should be done. Use repository-"
    "relative paths. Include generated files and any versioning the change requires. Do not "
    "write the code and do not change any files; reply with the plan only.\n\n"
    "Work only from this checkout: do not fetch from the remote or look up the upstream change."
)

# What apache/airflow#69403 (merge 0b6c38502a) actually changed, one entry per
# part of the change. Written from the upstream diff before any trial ran. A plan
# covers a part when it mentions any of the patterns (case-insensitive).
DAGRUN_NOTE_PARTS = {
    "execution_api_route": [r"execution_api/routes/task_instances"],
    "execution_api_datamodel": [r"execution_api/datamodels/taskinstance"],
    "cadwyn_version": [r"execution_api/versions", r"\bcadwyn\b"],
    "sdk_api_client": [r"sdk/api/client\.py"],
    "sdk_generated_models": [r"_generated\.py", r"datamodel-codegen"],
    "supervisor_comms_message": [r"execution_time/comms\.py"],
    "supervisor_relay": [r"execution_time/supervisor\.py", r"request_handlers\.py"],
    "runtime_helper": [r"execution_time/task_runner\.py", r"sdk/types\.py"],
    "supervisor_schema_version": [r"execution_time/schema"],
    "ts_sdk_generated": [r"ts-sdk"],
    "note_without_user": [r"services/public/dag_run", r"user[_ ]id\b.{0,80}(none|null)",
                          r"(without|no) (a )?user attribution"],
}

SCENARIOS = {
    "metrics": {
        "base": "f44bb16d825edcb533b5819c152c4d6a23a0ffd9",
        "upstream": "b03e48a875d991ad42b9d81efb7e75e001879404",
        "fixture": "airflow-metrics-knowledge",
        "pointer": pointer("the metrics code (shared/observability, airflow-core and task-sdk "
                           "metrics clients)"),
        "bundle_prompt": bundle_prompt(
            "the metrics code of this Apache Airflow checkout. Scope it to the StatsD, Datadog and "
            "OpenTelemetry metrics clients in "
            "`shared/observability/src/airflow_shared/observability/metrics/`, "
            "`airflow-core/src/airflow/observability/metrics/` and "
            "`task-sdk/src/airflow/sdk/observability/metrics/`."),
        "tasks": {"feature": METRICS_FEATURE, "why": METRICS_WHY},
    },
    "dagrun-note": {
        "base": "8d4ab8a94db291a359b686ac545211f4c440cb3e",       # parent of apache/airflow#69403
        "upstream": "0b6c38502abb6a152ab6a6334910f171c75c4e5f",
        "fixture": "airflow-execution-api-knowledge",
        "pointer": pointer("the Execution API and the Task SDK runtime that talks to it "
                           "(execution_api in airflow-core; api/ and execution_time/ in task-sdk)"),
        "bundle_prompt": bundle_prompt(
            "the Execution API and the Task SDK runtime that talks to it, in this Apache Airflow "
            "checkout. Scope it to `airflow-core/src/airflow/api_fastapi/execution_api/`, "
            "`task-sdk/src/airflow/sdk/api/` and `task-sdk/src/airflow/sdk/execution_time/`."),
        "tasks": {"plan": DAGRUN_NOTE_PLAN},
    },
}


# ----------------------------------------------------------------- docker

def images(scn: str) -> tuple[str, str]:
    return f"catalogify-eval-airflow:{scn}", f"catalogify-reuse-eval:{scn}"


def build_images(scn: str) -> None:
    base, image = images(scn)
    subprocess.run(["docker", "build", "-q", "-t", base, "--build-arg",
                    f"AIRFLOW_BASE={SCENARIOS[scn]['base']}", str(ENV_DIR)],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["docker", "build", "-q", "-t", image, "--build-arg", f"BASE={base}", str(HERE)],
                   check=True, stdout=subprocess.DEVNULL)


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
  git add knowledge AGENTS.md && git commit -qm "Add knowledge bundle"
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


def run_container(scn: str, task: str, arm: str, prompt: str, out: Path) -> None:
    cfg = SCENARIOS[scn]
    _, image = images(scn)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ev = Path(tmp)
        (ev / "prompt.txt").write_text(prompt)
        (ev / "pointer.md").write_text(cfg["pointer"])
        (ev / "run.sh").write_text(CONTAINER_SCRIPT)
        shutil.copy(HERE / "grade_feature.py", ev / "grade_feature.py")
        if arm == "bundle":
            shutil.copytree(HERE / "fixtures" / cfg["fixture"], ev / "fixture")
        if arm == "skill":
            shutil.copytree(SKILL_DIR, ev / "skill")
        cmd = ["docker", "run", "--rm", "-v", f"{ev}:/eval:ro", "-v", f"{out}:/out",
               "-e", "ANTHROPIC_BASE_URL", "-e", "ANTHROPIC_API_KEY",
               "-e", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "-e", "ANTHROPIC_SMALL_FAST_MODEL",
               "-e", "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
               "-e", f"MODEL={MODEL}", "-e", f"ARM={arm}", "-e", f"TASK={task}",
               "-e", f"UPSTREAM_SHA={cfg['upstream']}", image, "bash", "/eval/run.sh"]
        subprocess.run(cmd, env=agent_env(), timeout=3600, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # files written as root inside the container; make them readable/removable here
    subprocess.run(["docker", "run", "--rm", "-v", f"{out}:/out", image, "chmod", "-R", "a+rwX", "/out"],
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


def grade_plan(plan: str) -> dict[str, float]:
    text = plan.lower()
    return {part: 1.0 if any(re.search(p, text) for p in pats) else 0.0
            for part, pats in DAGRUN_NOTE_PARTS.items()}


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
        "cost_usd": res.get("total_cost_usd"),
        "turns": res.get("num_turns"),
        "seconds": round((res.get("duration_ms") or 0) / 1000, 1),
        "input_tokens": sum(usage.get(k) or 0 for k in
                            ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
        "output_tokens": usage.get("output_tokens"),
        "fetched_upstream": (out / "fetched_upstream").read_text().strip() == "1"
        if (out / "fetched_upstream").exists() else None,
        "changed_files": bool((out / "status.txt").exists() and (out / "status.txt").read_text().strip()),
    })
    answer = res.get("result") or ""
    if task == "feature":
        try:
            g = json.loads((out / "grade.json").read_text())
            rec["score"] = g["passed"] / g["total"]
            rec["missed"] = [k for k, v in g["checks"].items() if not v["pass"]]
        except (OSError, json.JSONDecodeError, KeyError):
            rec["score"] = 0.0
    else:
        m = grade_plan(answer) if task == "plan" else grade_why(answer)
        rec["score"] = sum(m.values()) / len(m)
        rec["missed"] = [k for k, v in m.items() if not v]
        rec["answer_chars"] = len(answer)
    (out / "answer.md").write_text(answer)
    (out / "record.json").write_text(json.dumps(rec, indent=2))
    return rec


# ------------------------------------------------------------- subcommands

def cmd_bundle(args: argparse.Namespace) -> None:
    cfg = SCENARIOS[args.scenario]
    fixture = HERE / "fixtures" / cfg["fixture"]
    build_images(args.scenario)
    out = RESULTS / args.scenario / "bundle-build" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"building the fixture bundle with the catalogify skill -> {out}", flush=True)
    run_container(args.scenario, "bundle", "skill", cfg["bundle_prompt"], out)
    rec = collect(out, "bundle")
    if not (out / "knowledge" / "index.md").is_file():
        sys.exit(f"no bundle produced; see {out}/claude.json and claude.stderr")
    if fixture.exists():
        shutil.rmtree(fixture)
    shutil.copytree(out / "knowledge", fixture)
    print(json.dumps({k: rec.get(k) for k in ("cost_usd", "turns", "seconds", "input_tokens", "output_tokens")}, indent=2))
    for name in ("validate.json", "verify.json"):
        if (out / name).exists():
            d = json.loads((out / name).read_text() or "{}")
            print(name, d.get("result"), "errors" if "errors" in d else "findings",
                  len(d.get("errors", d.get("findings", []))))
    print(f"fixture written to {fixture.relative_to(ROOT)}")


def report(task: str, arm: str, i: int, rec: dict) -> None:
    if rec.get("error"):
        print(f"  {task:8} {arm:6} #{i}: ERROR {rec['error'][:100]}", flush=True)
    else:
        print(f"  {task:8} {arm:6} #{i}: score {rec['score']:.2f}  ${rec['cost_usd'] or 0:.2f}  "
              f"{rec['turns']} turns  {rec['seconds']}s  {rec['input_tokens']:,} in", flush=True)


def cmd_trials(args: argparse.Namespace) -> None:
    cfg = SCENARIOS[args.scenario]
    if not (HERE / "fixtures" / cfg["fixture"] / "index.md").is_file():
        sys.exit(f"no fixture bundle; run `run.py bundle -s {args.scenario}` first")
    tasks = args.tasks or list(cfg["tasks"])
    build_images(args.scenario)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    jobs = [(task, arm, i) for i in range(1, args.n + 1) for task in tasks for arm in ("bundle", "none")]
    print(f"{len(jobs)} trials, {args.parallel} at a time -> results/{args.scenario}/{stamp}", flush=True)

    def one(job):
        task, arm, i = job
        out = RESULTS / args.scenario / stamp / task / arm / f"attempt-{i}"
        run_container(args.scenario, task, arm, cfg["tasks"][task], out)
        rec = collect(out, task)
        report(task, arm, i, rec)
        return rec

    with cf.ThreadPoolExecutor(max_workers=args.parallel) as pool:
        list(pool.map(one, jobs))
    cmd_summary(argparse.Namespace(scenario=args.scenario, run=stamp))


def cmd_retry(args: argparse.Namespace) -> None:
    """Re-run attempts of an earlier run that ended in an API error."""
    cfg = SCENARIOS[args.scenario]
    run = RESULTS / args.scenario / args.run
    build_images(args.scenario)
    for rec_path in sorted(run.glob("*/*/attempt-*/record.json")):
        out = rec_path.parent
        task, arm, i = out.parent.parent.name, out.parent.name, int(out.name.split("-")[1])
        if collect(out, task).get("error"):
            for f in out.iterdir():
                if f.is_file():
                    f.unlink()
            run_container(args.scenario, task, arm, cfg["tasks"][task], out)
            report(task, arm, i, collect(out, task))
    cmd_summary(argparse.Namespace(scenario=args.scenario, run=args.run))


def cmd_summary(args: argparse.Namespace) -> None:
    base = RESULTS / args.scenario
    runs = sorted(p for p in base.iterdir() if p.is_dir() and re.match(r"\d{8}-\d{6}$", p.name)) \
        if base.is_dir() else []
    if not runs:
        sys.exit(f"no trial runs in {base}")
    run = base / (args.run or runs[-1].name)
    lines = [f"# Bundle reuse: {args.scenario}, {run.name}", "",
             f"Model `{MODEL}`, Claude Code in Docker.", "",
             "| Task | Arm | Attempts | Score (mean) | Cost $ (mean) | Turns (mean) | "
             "Seconds (mean) | Input tokens (mean) | Output tokens (mean) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
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

            lines.append(f"| {task_dir.name} | {arm} | {len(recs)}"
                         f"{f' (+{errors} errored)' if errors else ''} | {mean('score'):.2f} | "
                         f"{mean('cost_usd'):.2f} | {mean('turns'):.1f} | {mean('seconds'):.0f} | "
                         f"{mean('input_tokens'):,.0f} | {mean('output_tokens'):,.0f} |")
    lines += ["", "Per attempt:", ""]
    for rec_path in sorted(run.glob("*/*/attempt-*/record.json")):
        r = json.loads(rec_path.read_text())
        if r.get("error"):
            lines.append(f"- `{r['dir']}`: excluded, API error: {r['error'][:120]}")
            continue
        lines.append(f"- `{r['dir']}`: score {r['score']:.2f}, ${r.get('cost_usd') or 0:.2f}, "
                     f"{r.get('turns')} turns, {r.get('input_tokens'):,} input tokens, "
                     f"fetched upstream: {r.get('fetched_upstream')}, changed files: "
                     f"{r.get('changed_files')}; missed: {r.get('missed')}")
    (run / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def scenario_arg(p):
        p.add_argument("-s", "--scenario", required=True, choices=list(SCENARIOS))

    b = sub.add_parser("bundle")
    scenario_arg(b)
    b.set_defaults(func=cmd_bundle)
    t = sub.add_parser("trials")
    scenario_arg(t)
    t.add_argument("-n", type=int, default=3, help="attempts per task and arm")
    t.add_argument("--tasks", nargs="+")
    t.add_argument("--parallel", type=int, default=2)
    t.set_defaults(func=cmd_trials)
    r = sub.add_parser("retry", help="re-run attempts that ended in an API error")
    scenario_arg(r)
    r.add_argument("--run", required=True)
    r.set_defaults(func=cmd_retry)
    s = sub.add_parser("summary")
    scenario_arg(s)
    s.add_argument("--run")
    s.set_defaults(func=cmd_summary)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
