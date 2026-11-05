# Does an existing bundle help? A/B on Apache Airflow

catalogify is meant to run once per repository. The bundle is committed next to the code, and
every later agent session reads it. SkillEvaluator can't measure that: its with-skill and
without-skill arms share one workspace, so a committed bundle would help both. This directory
measures reuse directly.

Claude Code runs headless in Docker on the Airflow checkout from
[`../skillevaluator`](../skillevaluator) (the parent of apache/airflow#70517). Both arms get the
same prompt:

| Arm | Workspace |
| --- | --- |
| `bundle` | `fixtures/airflow-metrics-knowledge/` committed as `knowledge/`, plus four lines in Airflow's `AGENTS.md` pointing at it |
| `none` | the checkout unchanged |

Neither arm has the catalogify skill installed, so the bundle is the only difference.

## Tasks

- **`feature`**: implement `[metrics] statsd_socket_path` (apache/airflow#70666) from the issue
  text, with no interface spelled out. `grade_feature.py` checks behaviour through the public
  `get_statsd_logger()` and `get_dogstatsd_logger()` wrappers in airflow-core and task-sdk:
  socket used when set, UDP unchanged when unset, Datadog given the socket. That makes six checks.
  Against the real upstream change it scores 6/6. The untouched checkout scores 2/6, and upstream
  without its task-sdk part scores 3/6.
- **`why`**: why does task-sdk have its own metrics wrapper, and which commit split it out?
  The grader checks that the answer cites a commit that split the code (`337aee896a` or
  `0d294caab3`) and names all three locations.

## Run it

```bash
python3 integrations/reuse-eval/run.py bundle          # once: build the fixture with the skill
python3 integrations/reuse-eval/run.py trials -n 3     # both tasks, both arms
python3 integrations/reuse-eval/run.py retry --run <stamp>   # re-run attempts that hit API errors
python3 integrations/reuse-eval/run.py summary
```

The key is read from `~/.openrouter.key` (override with `REUSE_EVAL_KEY_FILE`) and passed to the
container through the environment. `ANTHROPIC_BASE_URL` defaults to OpenRouter, and the model to
`anthropic/claude-sonnet-5-5`. Results go to `results/`, which is not committed.

## First result, 2026-11-05

The fixture bundle was built once by Sonnet 5.5 with catalogify 0.10.1. It has 9 concepts,
`validate` reports 0 errors and `verify` reports 0 findings. The build took 19 turns, 2 min 38 s,
and about 963k tokens, nearly all cache reads; Claude Code estimated $0.47. It was not reviewed
by a human, and its 8 `open_questions` are unanswered.

| Task | Arm | Valid attempts | Score | Cost (mean) | Turns (mean) | Seconds (mean) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| feature | bundle | 2 | 1.00 | $0.18 | 12.0 | 106 |
| feature | none | 2 | 1.00 | $0.14 | 10.5 | 49 |
| why | bundle | 2 | 1.00 | $0.08 | 4.5 | 19 |
| why | none | 2 | 1.00 | $0.05 | 3.0 | 13 |

Costs are Claude Code's own estimates, not the OpenRouter bill. The third attempt of every
task-arm pair failed with HTTP 402 because the OpenRouter balance ran out, and those attempts are
excluded.

**The bundle made no difference to correctness on these two tasks, and the agent spent more when
it had one.** Without the bundle, Sonnet 5.5 found all three places the feature had to change and
named the right commit for the "why" question, using grep and `git log`. With the bundle, it read
the bundle first, then the code anyway. That added turns, tokens and time.

What this does not show:

- Two valid attempts per arm is a smoke test, not a measurement.
- The coupling in this feature can be found by grep, because all three copies share names. The
  answer to the "why" question sits in commit messages a single `git log` reaches. A task whose
  knowledge is not recoverable from the tree and one log query is where a bundle should pay. This
  pair of tasks is not that.
- The bundle was not curated. It parked "why are these adapters copied per distribution?" as an
  open question instead of answering it. Answering that is the job of `catalogify clarify`, and a
  clarified bundle is the fairer test.

The first grader for `why` accepted only `337aee896a`. Every valid answer from both arms named
`0d294caab3`, which is also correct: that commit removed the airflow-core imports from
`shared/`. The grader now accepts both, and the table above uses it.
