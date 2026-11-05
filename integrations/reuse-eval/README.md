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
python3 integrations/reuse-eval/run.py bundle  -s dagrun-note          # once: build the fixture with the skill
python3 integrations/reuse-eval/run.py trials  -s dagrun-note -n 3     # its tasks, both arms
python3 integrations/reuse-eval/run.py retry   -s dagrun-note --run <stamp>
python3 integrations/reuse-eval/run.py summary -s dagrun-note
```

Scenarios: `metrics` (apache/airflow#70517, feature + "why" tasks) and `dagrun-note`
(apache/airflow#69403, an implementation plan). Set `REUSE_EVAL_MODEL` to change the model, for
example `anthropic/claude-haiku-5.5`.

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

## Second result: an implementation plan for a complex feature, 2026-11-05

Scenario `dagrun-note`, on Haiku 5.5 because credit was short; the whole run cost about $0.45.
The agent plans apache/airflow#69403 from issue #64890. That change crosses the Task SDK runtime,
the supervisor protocol and its versioned schema, the SDK client and generated models, the core
Execution API with a Cadwyn version, and the TypeScript SDK. The bundle covers the Execution API
and the Task SDK runtime (17 concepts, `verify` 0 findings), and it documents every one of those
parts. Plans are graded on 11 parts of the real change.

| Arm | Attempts | Score (mean, range) | Turns | Input tokens | Seconds |
| --- | ---: | --- | ---: | ---: | ---: |
| bundle | 3 | 0.79 (0.73–0.82) | 16.3 | 652,244 | 89 |
| none | 3 | 0.76 (0.64–0.91) | 17.3 | 642,007 | 93 |

The bundle didn't improve the plans or save tokens. The agent cited it, then explored the code as
much as it did without it. The parts the bundle documents were missed at about the same rate:
the supervisor schema version in 2 of 3 plans, and the TypeScript SDK in 3 of 3. Details and
caveats are in `EXPERIMENTS.md` §13a, including a grader change made after the first scoring and
applied to both arms.

A third arm, `bundle-trust`, keeps the bundle and changes only the `AGENTS.md` text. The new text
says the bundle is verified, tells the agent to plan from it, and to open code only to confirm a
path. That arm scored the same (0.79, range 0.73–0.91), but used 25.7 turns and 1,430,409 input
tokens on average, more than twice either other arm. Reading the bundle wholesale costs more than
it saves. See `EXPERIMENTS.md` §13a.

## Third result: the typed bundle through `catalogify find`, 2026-11-05

Scenario `dagrun-note-v2`, Haiku 5.5. catalogify 0.11.0 rebuilt the bundle with typed relations, one
playbook and one guardrail, and the `bundle-find` arm's pointer sends the agent to
`catalogify find` instead of the bundle. Score 0.76 (0.73–0.82), 23.0 turns, 1,002,154 input
tokens: no better than without a bundle, at 56% more tokens. The agents did use `find` and the
playbook. But the generated playbook left out two partners that `cochange` ranks high (the
TypeScript SDK and the supervisor schema), so every plan still missed the TypeScript SDK. Details
in `EXPERIMENTS.md` §13b.

## Fourth result: mitmproxy, which doesn't document its procedures, 2026-11-05

Scenario `mitmproxy-tcp-timeout` (mitmproxy#7910, a new `tcp_timeout` option), Haiku 5.5. The
typed bundle with `find` scored 1.00 (3/3) against 0.93 without (one plan left out the generated
`_options_gen.ts`), at the same input tokens (244k against 240k). It's the first result in the
bundle's favour, and too small to count: three attempts per arm, and a gap of one plan. Details in
`EXPERIMENTS.md` §13c.
