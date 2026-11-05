# Live evaluation with NVIDIA SkillEvaluator

The security scanners (SkillSpector, Snyk) only show the skill is safe to install. They don't show
it helps. This directory holds a [SkillEvaluator](https://docs.nvidia.com/skills/skillevaluator)
Tier 3 eval. It runs Claude Code (Sonnet 5.5) on real tasks in Apache Airflow twice, once with
catalogify and once without, and scores the difference.

## The sample: Airflow's metrics clients

All cases run in a checkout of [apache/airflow](https://github.com/apache/airflow) at
`f44bb16d82`, the parent of [#70517](https://github.com/apache/airflow/pull/70517), "Support a
Unix Domain Socket for the metrics clients". That change touched one metrics client in three
places: `shared/observability`, `airflow-core` and `task-sdk`. No import ties them together. Each
component reads its own config, a rule set down in `337aee896a`. So a newcomer can easily change
one copy and miss the others. That is the kind of hidden coupling a catalogify bundle is supposed
to surface.

| Case | Bucket | What it asks | Custom metrics from `evals/grader.py` |
| --- | --- | --- | --- |
| `airflow-metrics-bundle-explicit` | explicit | "Use catalogify to build a bundle for the metrics code" | bundle present; `catalogify validate` clean; `catalogify verify` findings per concept; how many of the three copies the bundle cites |
| `airflow-metrics-bundle-implicit` | implicit | A newcomer asks for a git-grounded knowledge base, without naming the skill | same as above |
| `airflow-uds-feature-contextual` | contextual | Implement the feature from issue #70666, with the interface the upstream tests expect | upstream tests from the merge commit that the feature fixes (18); no regressions in the rest (83); task-sdk copy updated; config option declared; agent did not fetch the upstream fix |
| `airflow-negative-question` | negative | "What is the default `statsd_port`?" | no bundle written; no files changed |

The feature case is graded against upstream's own tests, fetched only after the agent finishes.
Those tests don't cover task-sdk, so an implementation that skips it still passes 18/18. The
`task_sdk_reads_socket_path` metric covers that gap. SkillEvaluator's standard dimensions
(security, correctness, discoverability, effectiveness, efficiency) and Skill Lift are scored as
usual. The custom metrics appear next to them with their own lift.

## Run it

Needs Docker with Compose 5.0.2 or later (`docker compose version`). SkillEvaluator adds
`HEALTHCHECK NONE` to every task image, and Harbor starts containers with `up --wait`. Older
Compose releases, 2.29 for example, fail that pair with "container ... has no healthcheck
configured" ([docker/compose#13522](https://github.com/docker/compose/issues/13522)). Then install
SkillEvaluator with the Tier 3 extra:

```bash
uv tool install --python 3.13 "skillevaluator[llm,tier3] @ git+https://github.com/NVIDIA/SkillEvaluator.git"
```

With an Anthropic key:

```bash
export SKILL_EVAL_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=...
./integrations/skillevaluator/run.sh
```

With an OpenRouter key, through its Anthropic-compatible API (not yet tried):

```bash
export SKILL_EVAL_LLM_PROVIDER=anthropic
export ANTHROPIC_BASE_URL=https://openrouter.ai/api
export ANTHROPIC_API_KEY="$(cat ~/.openrouter.key)"
export SKILL_EVAL_LLM_MODEL=anthropic/claude-sonnet-5-5
./integrations/skillevaluator/run.sh --agent-model claude-code=anthropic/claude-sonnet-5-5
```

`run.sh` copies the published skill (`plugins/catalogify/skills/catalogify`) and `evals/` into
`.stage/`, validates the eval contract, and runs `tier3 evaluate`. Any extra arguments are passed
through. Try `--max-cases 1 --n-attempts 1` for a cheap first run. The evals live here rather than
inside the skill so they never ship to users.

A full run is 4 cases × 3 attempts × 2 arms = 24 agent sessions plus judge calls. The two bundle
cases are the expensive ones.

## What has been checked

These were checked on 2026-11-05, without running SkillEvaluator itself:

- The image builds (about 1 GB) with full Airflow history (40,638 commits, not shallow), and
  `catalogify history` works on that partial clone.
- `uvx catalogify@0.10.1` resolves in the container. catalogify is not preinstalled, so the
  baseline arm has no trace of it.
- The grader was run in these states:

  | State | Result |
  | --- | --- |
  | Untouched checkout | 0/18 feature tests pass, 83/83 existing tests still pass |
  | Real upstream change applied | 18/18 feature tests, task-sdk updated, config option declared |
  | Upstream change without the task-sdk copy | 18/18 feature tests, but task-sdk 0/2 |
  | Hand-made bundle | validate and verify scored. A bundle citing a nonexistent commit scores 0 on verify |
  | Negative case after writing files | Flagged |

## Limits

- The container needs network access. Older Airflow file contents are fetched on demand, and the
  grader fetches the upstream tests. That same access means the agent could look up the real
  change. The prompt forbids it, and `upstream_fix_not_fetched` drops to 0 if the merge commit
  shows up in the repository. Browsing GitHub over the web would go unnoticed.
- The feature prompt states the function names and error message the upstream tests expect. A
  correct design with different names would otherwise fail.
- `expected_skill` is `catalogify` for the feature case. Whether the agent reaches for the skill
  unprompted is part of what is measured, under discoverability.
