# OKF catalog generation runs — the log

Every `catalogify generate` run made on a public repository, with the cost it
incurred and the errors it made. **Add new runs here rather than re-measuring
old ones.** Every figure below was measured at the time; nothing needs
repeating to be cited.

## Runs at a glance

| # | Repository | Version | Agent | Concepts | Tokens | Wall clock | Findings |
|---|---|---|---|---:|---:|---|---:|
| 0 | `kubernetes/kubernetes`, `pkg/kubelet` | speckit-okf 0.4.0 | not recorded | 9 | not recorded | not recorded | 5 |
| 1 | Online Boutique | catalogify 0.5.0 | Codex `gpt-5.5` | 20 | 1,394,136 | 6 min 43 s | 17 |
| 2 | Online Boutique | catalogify 0.7.0 | Codex `gpt-5.5` | 21 | 1,600,683 | 8 min 19 s | 0 |
| 3 | `apache/airflow` | catalogify 0.8.0 | Codex `gpt-5.5` | 17 | 1,207,172 | 6 min 29 s | 0 |
| 4 | `apache/airflow`, metrics clients | catalogify 0.10.1 | Claude Code, Sonnet 5.5 | 9 | 962,725 | 2 min 38 s | 0 |
| 5 | `apache/airflow`, Execution API + Task SDK runtime | catalogify 0.10.1 | Claude Code, Haiku 5.5 | 17 | 3,369,260 | 6 min 58 s | 0 |
| 7 | `mitmproxy/mitmproxy`, options + proxy core | `ontology-layer` branch (unreleased) | Claude Code, Haiku 5.5 | 14 | 3,524,660 | 6 min 4 s | 0 |

Findings are `catalogify verify` results on the finished bundle. Run 0 predates
`verify` and was judged retrospectively. Runs 1 and 2 are the same repository
and commit, regenerated under a later version.

Detail sections: run 1 in §1–§8, run 2 in §9, run 3 in §11, run 0 in §12, run 4 in §13, run 5 in §13a, run 6 in §13b, run 7 in §13c.

---

Sections 1 to 8 describe run 1 in full.
Written to be cited from the README and the blog post. Every number below was
measured, not estimated, except where it says otherwise.

**Date:** 7 September 2026

---

## 1. Subject

| | |
|---|---|
| Upstream | `GoogleCloudPlatform/microservices-demo` (Online Boutique) |
| Fork under test | `github.com/agentic-ai-demos/microservices-demo` |
| Commit | `b9a978db9e01f4ad3dca9494a22cb9edc17548fe` ("Add GKE labels", 3 Sep 2026) |
| Licence | Apache-2.0 |
| Tracked files | 364 |
| Commits in history | 2,690 |
| Deployable services | 12 |
| Languages under `src/` | Go (29 files), Python (12), C# (9), plus Node and Java services |

Chosen because it is small enough to read end to end, genuinely polyglot in one
tree, and shaped like the routing problem: twelve independent services where
"which one does this spec touch" is a real question.

## 2. Tooling

| | |
|---|---|
| Generator | Codex CLI, `gpt-5.5`, reasoning effort `medium` |
| Plan | ChatGPT Plus (flat rate; no metered credits, balance 0) |
| Context window | 258,400 tokens (from the usage record) |
| Skill version | **catalogify 0.5.0** (from `generated_by` in every concept) |
| Granularity | medium (recorded in `log.md`) |

**The version matters.** 0.5.0 predates all three corrections made in this
project: test-only commit marking (PR #1), the `verify` command and co-change
mining (PR #2), and the tracked-sources rule and per-language import matching
(PR #3). In particular, 0.5.0's `generate.md` had no Phase 3 verification step,
so the agent was never told to check its own claims. Section 5 should be read
with that in mind.

## 3. Cost

From the Codex `token_count` record for the generating turn.

| Measure | Tokens |
|---|---:|
| Total | 1,394,136 |
| Input | 1,376,581 |
| — of which served from cache | 1,256,320 |
| — fresh input | 120,261 |
| Output | 17,555 |
| — of which reasoning | 185 |

Cache hit rate 91.3%. Total equals input plus output; cached input is a subset
of input, following the usual OpenAI accounting, so billed cost is well below
the headline figure.

**Wall clock:** 402,889 ms (6 min 43 s), time to first token 3,144 ms.

**Money:** none. The run was on a flat-rate ChatGPT Plus plan with no metered
credits, so the marginal dollar cost was zero. What it actually consumed was
quota: 34% of the 5-hour rate-limit window and 5% of the weekly one. Any dollar
figure quoted for this run is therefore a hypothetical repricing at API rates,
and must be marked as such. If you do quote one, price the 120,261 fresh input
tokens and the 1,256,320 cached input tokens separately, because cached input
is billed at a large discount and 91.3% of this run was cache hits.

Source of all figures: the Codex session log at
`~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread-id>.jsonl`, in the
last `token_count` event.

## 4. Output

27 markdown files, 20 concepts, in `knowledge/`.

| | Bytes | Tokens (bytes ÷ 4) |
|---|---:|---:|
| 12 service entries | 25,683 | ~6,400 |
| All 20 concepts | 43,445 | ~10,900 |
| Bundle directory incl. indexes | 71,569 | ~17,900 |
| **Mean per service entry** | **2,140** | **535** |

Concepts by area: 1 architecture overview, 12 services, 1 shared gRPC contract,
1 data model, 5 operations (Kubernetes manifests, Kustomize, Helm, Terraform,
CI/release).

### The economic result

535 tokens per service is **below** the 676 measured on the Kubernetes kubelet,
so the per-service figure holds on a second, independent repository of a
different shape and language mix. The whole twelve-service estate reads for
about 10,900 tokens.

Build cost was 1.39M tokens once; a routing question against the finished
catalog costs about 10,900. The catalog pays for itself against roughly 128
repeat readings, and far sooner against agentic exploration, which re-derives
the answer at full cost on every question.

## 5. Correctness

`catalogify validate` and `catalogify verify` (0.7.0) were run on the same
bundle. They disagree, which is the point of having both.

```
validate:  concepts: 20  errors: 0  warnings: 0   -> CONFORMANT (OKF v0.1)
verify:    concepts: 20  findings: 17  notes: 39  -> UNSUPPORTED CLAIMS
```

Findings by rule:

| Rule | Count | What it means |
|---|---:|---|
| V5 | 9 | `# Gotchas` asserts invariants and cites no commit |
| V4 | 4 | A symbol in `# Interfaces` is in no non-test source file |
| V2 | 4 | A cited commit touches none of that concept's `source_files` |
| V6 (note) | 39 | A dependency link no import backs in either direction |

### The nine V5 findings are the real result

Nine of twenty concepts state invariants with nothing behind them. This is the
failure the whole project exists to catch, and it is exactly what 0.5.0 would
be expected to produce: that version's workflow never asked the agent to verify
its own claims. Re-running under 0.7.0, whose Phase 3 requires a `verify` pass
and fixing every finding, is the obvious next experiment.

### Two of the four V4 findings are a bug in the checker, not the catalog

Recorded here because an honest experiment records its instrument errors.

- `frontend.md` lists routes as `` `GET /cart` `` and `` `POST /setCurrency` ``.
  The extractor splits the cell on `/` and then searches for a function named
  `GET`. False positive.
- `kubernetes-manifests.md` lists `` `frontend.yaml` ``. The extractor strips
  the last dotted segment expecting `Type.Method` and searches for a symbol
  named `yaml`. False positive.

Both come from `symbols_in()` in `verify_okf.py` treating a free-text table cell
as an identifier chain. It was written and tested against Go symbol tables only.
See section 6, and [#4](https://github.com/alexcpn/catalogify/issues/4).

## 6. What this says about the checker's design

V4 tries to pull an identifier out of prose written by a language model. That is
an open-ended parsing problem, and the two false positives above are not the
last two. Foreseeable cases include generics (`Map<String, Foo>`), C++
qualified names (`Ns::Class::method`), dunder and operator names, decorated
symbols, CLI flags (`--max-files`), protobuf `rpc` signatures, and SQL
identifiers. Adding an exception per case is a losing game.

The fix is to narrow what the check is willing to judge rather than to widen the
regex: only rule on cells that are unambiguously a single identifier, and stay
silent on everything else. A check that fires rarely and is right is worth more
than one that fires often and is half noise, because noise teaches people to
ignore the tool. That is the same failure this project set out to fix.

## 7. Reproduction

```bash
git clone https://github.com/agentic-ai-demos/microservices-demo
cd microservices-demo
git checkout b9a978db

uv tool install catalogify
catalogify install

# then ask the agent for a knowledge bundle, and check it:
catalogify validate knowledge/
catalogify verify   knowledge/
```

Measurements in section 4:

```bash
find knowledge -name '*.md' ! -name index.md ! -name log.md -exec wc -c {} +
du -sb knowledge
```

Tokens are bytes ÷ 4 throughout, matching the convention used in the Kubernetes
measurements so the two are comparable.

## 8. Caveats

- One run, one repository, one agent. Nothing here establishes variance.
- The generator was catalogify 0.5.0. Sections 4 and 5 measure the workflow
  *before* the corrections in PRs #1 to #3, not the current one.
- The verifier was catalogify 0.7.0, so the instrument is newer than the thing
  it measures. This is deliberate: the point was to see what the old workflow
  produced, judged by the new checks.
- Token counts come from the agent's own usage record and include the whole
  turn, not only the generation. Cost attributable purely to writing concepts
  is lower and was not isolated.
- `bytes ÷ 4` is an approximation of tokenisation, consistent across all
  figures but not exact for any single file.
- The 128-reading break-even in section 4 assumes a reader loads the whole
  catalog each time and ignores prompt caching, which would shorten it.

## 9. Run 2 — the same repository under catalogify 0.7.0

The obvious follow-up, run the same day: regenerate from the same commit with
the corrected skill installed, and judge it with the same checker. 0.7.0's
`generate.md` adds a Phase 3 that requires a `verify` pass and the fixing of
every finding, which 0.5.0 had no equivalent of.

### Cost

| Measure | Run 1 (0.5.0) | Run 2 (0.7.0) |
|---|---:|---:|
| Total tokens | 1,394,136 | 1,600,683 |
| Fresh input | 120,261 | 117,850 |
| Cached input | 1,256,320 | 1,462,144 |
| Cache hit rate | 91.3% | 92.5% |
| Output | 17,555 | 20,689 |
| Quota, 5-hour window | 34% | 45% |
| **Wall clock** | **6 min 43 s** | **8 min 19 s** |
| Time to first token | 3,144 ms | 4,592 ms |

15% more tokens and 24% more wall clock, an extra 1 min 36 s. Fresh input
barely moved and actually fell slightly, from 120,261 to 117,850: the whole
increase is cache hits and output, which is what a verify-and-fix loop looks
like. It re-reads what it has already written, checks it, and rewrites the
parts that fail.

Both runs were a single turn (`task_complete`, `duration_ms` 402,889 and
499,298 respectively).

Cost of the correctness, stated plainly: **1 minute 36 seconds and 206,547
mostly-cached tokens to go from 17 unsupported claims to none.**

### Result

| | Run 1 (0.5.0) | Run 2 (0.7.0) |
|---|---:|---:|
| Concepts | 20 | 21 |
| Concept bytes | 43,445 | 53,126 |
| Mean per service entry | 535 tokens | 615 tokens |
| `validate` errors / warnings | 0 / 0 | 0 / 21 |
| **`verify` findings** | **17** | **0** |
| `verify` notes | 39 | 54 |

**Every finding is gone.** The nine uncited gotcha sections, the four
misattributed commits and the four `# Interfaces` symbol failures all cleared.
The bundle is 22% larger, which is what citing your evidence costs.

All 21 new warnings are W8, unresolved `open_questions` — one per concept. That
is the intended behaviour, not a regression: the agent parked what it could not
establish instead of writing a plausible sentence.

Spot-checking one of the new citations, `cartservice.md` now says Docker
platform support was reverted across all services, citing `ed7b9419`. That
commit is real, is titled `Revert "Add support for arm64 (#2589)"`, dates from
27 June 2025, and does touch `cartservice`. It is the revert-archaeology
mechanism working on a repository nobody chose for it.

### What zero findings does and does not mean

The agent was told to run `verify` and fix what it reported, so it optimised
against the metric. Zero findings means every cited commit exists and belongs
to its concept, every listed symbol exists in non-test code, and no invariant is
asserted without evidence. It does **not** mean the gotchas are the *right*
gotchas or that the prose is correct. What the corrections demonstrably removed
is a class of error, mechanically, on a repository the tooling had never seen.

That is also the honest limit of this experiment: it shows the checks change
behaviour, not that the resulting catalog is true.

## 11. Run 3 — `apache/airflow` under catalogify 0.8.0

A different repository, a much larger one, generated with the current
release. Included here because it is the first bundle produced by a version
whose workflow requires a `verify` pass from the start.

### Cost

| Measure | Boutique r1 (0.5.0) | Boutique r2 (0.7.0) | Airflow (0.8.0) |
|---|---:|---:|---:|
| Total tokens | 1,394,136 | 1,600,683 | 1,207,172 |
| Fresh input | 120,261 | 117,850 | 101,559 |
| Cached input | 1,256,320 | 1,462,144 | 1,088,512 |
| Cache hit rate | 91.3% | 92.5% | 91.5% |
| Output | 17,555 | 20,689 | 17,101 |
| Wall clock | 6 min 43 s | 8 min 19 s | 6 min 29 s |

The most useful number here is fresh input: 101,559 tokens on a repository
orders of magnitude larger than Online Boutique, and *lower* than either
Boutique run. Cost tracks the number of things worth naming, not the size of
the tree. That is the claim the README makes, measured on a second repo.

An earlier session in the same directory (`18:23`) was aborted before any
turn completed and carries no usage; the figures above are the `18:40` run.

Quota percentages are not comparable across runs, because the 5-hour window
accumulates: 34%, then 45%, then 63% over the day.

### Result

| | |
|---|---:|
| Concepts | 17 |
| Concept bytes | 38,859 (~9,700 tokens) |
| `validate` | 0 errors, 17 warnings (all W8) |
| **`verify`** | **0 findings**, 16 notes |

Clean on the first pass, with no correction round. Every warning is an
unresolved open question, one per concept.

### Caveat: this run did not measure what it was meant to

Airflow was chosen because `providers/` holds 82 packages, which would let
the ninety-service figure be measured instead of extrapolated. The run
produced 17 concepts, so it was generated coarse and does not cover the
providers one by one. The cost figures above are sound; the
ninety-service measurement is still outstanding. Scoping a run at
`providers/` at fine granularity would settle it.

## 12. Run 0 — `kubernetes/kubernetes`, `pkg/kubelet`

The earliest bundle, generated before this project's corrections existed and
before `verify` was written. Kept because its numbers are the ones quoted in
the published articles, and because it is the corpus on which every check was
developed.

| | |
|---|---|
| Repository | 25,917 files, 500,022 lines of Go |
| Scope | `pkg/kubelet` only, 108,648 lines, coarse granularity |
| Commit | `d5ccf7968e5` |
| Generator | `speckit-okf/0.4.0` |
| Concepts | 9 |
| One service entry | 2.6 KB, 676 tokens |
| Full bundle | 21.9 KB, ~5,600 tokens |
| `inventory` | 2.1 s over the whole repository, 56 KB of JSON |

Two bundles exist, `knowledge` and `knowledge-v1-baseline`, generated
independently. **Both produce the identical five `verify` findings**: three
test-only commits cited as production invariants in the plugin manager, one in
the volume manager, and a status-manager gotcha whose commit touched
`kuberuntime`. The v2 bundle adds two notes for an "import cycle" that Go
forbids.

That two independent generations made the same five mistakes from the same
inputs is the strongest single argument in this log for putting the check in
the tool rather than the prompt.

A corrected copy exists as `knowledge-fixed`, which verifies clean.

## 13. Run 4 — Airflow metrics clients, and whether the bundle helps

**Date:** 5 November 2026

A scoped bundle for the metrics code of `apache/airflow` at `f44bb16d82`,
the parent of apache/airflow#70517. It covers
`shared/observability/.../metrics/`, `airflow-core/.../observability/metrics/`
and `task-sdk/.../observability/metrics/`. Claude Code 2.1.318 ran headless in
Docker, using Sonnet 5.5 through OpenRouter and the skill as published in
0.10.1. The A/B harness and its fixtures are not kept in the repository.

### Cost and result

| | |
|---|---:|
| Turns | 19 |
| Wall clock | 2 min 38 s |
| Fresh input / cache read / cache write | 30 / 857,974 / 88,481 |
| Output | 16,240 |
| Concepts | 9 |
| `validate` | 0 errors, 8 warnings (all W8) |
| **`verify`** | **0 findings**, 0 notes |

### Reuse A/B

The bundle was committed into the checkout with a pointer in Airflow's
`AGENTS.md`. Claude Code then ran two tasks with it and without it, with no
skill installed in either arm. The first task implements the feature from the
issue text, graded by six behavioural checks through the airflow-core and
task-sdk wrappers. The second asks why task-sdk has its own metrics wrapper,
graded on citing the splitting commit and naming the three places.

| Task | Arm | Valid attempts | Score | Turns (mean) | Seconds (mean) |
|---|---|---:|---:|---:|---:|
| feature | bundle | 2 | 1.00 | 12.0 | 106 |
| feature | none | 2 | 1.00 | 10.5 | 49 |
| why | bundle | 2 | 1.00 | 4.5 | 19 |
| why | none | 2 | 1.00 | 3.0 | 13 |

The bundle did not change correctness, and runs that had it took more turns
and more time. On these tasks the agent recovered everything it needed from
grep and one `git log`. The three copies of the client share names, and the
reason for the split is in a commit message. The third attempt in each cell
failed with HTTP 402 when the OpenRouter balance ran out, and is excluded.

### Caveats

Two valid attempts per cell is a smoke test. The tasks were chosen before
checking whether their answers were recoverable without a bundle, and they
were. The bundle was not clarified: it parked "why are these adapters copied
per distribution?" as an open question. A curated bundle, and a task whose
answer isn't in the tree or one log query, are the next things to measure.

In the same session a SkillEvaluator Tier 3 case asked for the bundle
explicitly. With the skill: pass, 0.81. Without: fail, 0.43, because without
the skill no OKF bundle can be produced. A second case asked for the feature
with its interface spelled out. Sonnet 5.5 did not load the skill, and both
arms passed 18/18 upstream tests.

## 13a. Run 5 — does a bundle make an implementation plan cheaper or better?

**Date:** 5 November 2026

Run 4 used tasks that grep and one `git log` could answer. This run uses a
change whose path a name search doesn't show: apache/airflow#69403, runtime
DagRun note updates. Upstream touched 16 source files across the Task SDK
runtime, the supervisor protocol and its versioned schema, the SDK HTTP
client and generated models, the core Execution API with a Cadwyn version,
and the generated TypeScript SDK. The task was to write an implementation
plan from the original issue (#64890), with no code. The hypothesis was that
the bundle would save the tokens spent exploring.

Credit was short, so Claude Haiku 5.5 did everything: built the bundle and
wrote every plan. The whole run cost about $0.45.

### The bundle

Scope: `execution_api/` in airflow-core, and `api/` and `execution_time/` in
task-sdk, at `8d4ab8a94d`, the parent of #69403. 17 concepts, `validate` 0
errors and 17 W8 warnings, **`verify` 0 findings** and 37 notes. 67 turns,
6 min 58 s. 3,134,899 cache-read, 163,679 cache-write, 64 fresh and 70,618
output tokens. The bundle covers Cadwyn versioning, the supervisor message
protocol, the separately versioned supervisor schema, the generated client
models and the TypeScript SDK.

### Result

Plans were graded on 11 parts of the real change. The checklist was written
from the upstream diff before any trial. Upstream's file list scores 11/11
and the issue text 0/11.

| Arm | Attempts | Score (mean, range) | Turns | Input tokens | Output tokens | Seconds |
|---|---:|---|---:|---:|---:|---:|
| bundle | 3 | 0.79 (0.73–0.82) | 16.3 | 652,244 | 17,602 | 89 |
| none | 3 | 0.76 (0.64–0.91) | 17.3 | 642,007 | 19,289 | 93 |

**No difference in plan quality or in tokens.** All three bundle-arm plans
cite the bundle. They still missed the parts the bundle documents at about
the same rate as plans without it: the supervisor schema version in 2 of 3,
and the TypeScript SDK in 3 of 3. Input tokens were the same, because the
agent read the bundle and then explored the code anyway.

### Caveats

- Haiku, not Sonnet. A smaller model may use a map differently.
- Three attempts per arm. The spread within each arm (0.64–0.91) is larger
  than the gap between them.
- Two checklist items were widened after the first scoring, for both arms
  alike. Every plan put the endpoint in `execution_api/routes/dag_runs.py` and
  the helper in `execution_time/context.py`, which are valid designs that
  upstream happened not to use. Before widening, the means were 0.64 with the
  bundle and 0.61 without.
- The pointer in `AGENTS.md` says "start with the bundle before exploring".
  It does not say the bundle can be trusted in place of exploring. A
  different instruction may change the token figures, and that is the next
  thing to try.

### Follow-up: a pointer that says to plan from the bundle

Same bundle, model, image and prompt. Only the `AGENTS.md` text changed. The
new text says every claim is checked by `catalogify verify`, tells the agent
to plan from the bundle, to open source files only to confirm a specific path
or signature, and not to re-explore code the bundle describes. Three
attempts; the two arms above are reused as the baseline.

| Arm | Attempts | Score (mean, range) | Turns | Input tokens | Output tokens | Seconds |
|---|---:|---|---:|---:|---:|---:|
| bundle, "plan from it" | 3 | 0.79 (0.73–0.91) | 25.7 | 1,430,409 | 27,328 | 145 |

**Telling the agent to rely on the bundle more than doubled input tokens and
did not improve the plans.** The supervisor schema version and the TypeScript
SDK were still missed at the same rate. The likely mechanism: the agent read
many of the 17 concepts (152 KB, roughly 38k tokens) and then confirmed paths
in code anyway. Every later turn re-sends that larger context, so the cost
compounds. The transcripts were not kept, so which files it opened was not
measured.

What this says about catalogify: a bundle read whole is more expensive than
grep on a task like this. A saving would need the agent to open only the one
or two concepts the task touches. Nothing in the bundle or the pointer makes
it do that.


## 13b. Run 6 — typed bundle reached through `catalogify find`

> **The ontology layer tested in runs 6 and 7 was not merged, because it
> did not help** (§13c). Its code is on the [`ontology-layer`](https://github.com/alexcpn/catalogify/tree/ontology-layer) branch (PR #22, closed):
> - typed `relations` in concept frontmatter,
> - `Playbook` and `Guardrail` concept types,
> - `catalogify find`,
> - `catalogify cochange --evidence`,
> - verify checks V9–V14,
> - validate warning W12.
>
> "catalogify 0.11.0" below means that branch, which was never released.

**Date:** 5 November 2026

The same task as §13a (plan apache/airflow#69403 from issue #64890), with the
ontology layer (unreleased 0.11.0, branch `ontology-layer`). Haiku 5.5 rebuilt the Execution API
bundle with typed relations, one Playbook ("Add a field or endpoint to the
Execution API") and one Guardrail ("task code never touches the metadata
DB"). `validate` reported 0 errors and `verify` 0 findings. The trial arm's
`AGENTS.md` pointer says not to read the bundle, and to run
`catalogify find <file>` on each file the plan changes before finalizing.
Three attempts; the `none` and `bundle` arms of §13a are the baseline. The
whole run, bundle included, cost about $0.50 on OpenRouter.

| Arm | Score (mean, range) | Turns | Input tokens |
|---|---|---:|---:|
| none (§13a) | 0.76 (0.64–0.91) | 17.3 | 642,007 |
| bundle, "start here" (§13a) | 0.79 (0.73–0.82) | 16.3 | 652,244 |
| bundle, "plan from it" (§13a) | 0.79 (0.73–0.91) | 25.7 | 1,430,409 |
| **typed bundle + `find`** | 0.76 (0.73–0.82) | 23.0 | 1,002,154 |

**No improvement, and 56% more input tokens than without a bundle.** The
TypeScript SDK was still missed in 3 of 3 plans.

The agents did use the layer. All three plans refer to `catalogify find` and
the playbook, and the supervisor-schema step now appears in 2 of 3 plans. The
playbook was the weak link. Its `requires` lists the version file and
`_generated.py`, but not `ts-sdk/src/generated` or
`execution_time/schema`, though `cochange` shows both with lift 89 and
143, above the support-3, lift-5 bar the generate workflow sets. The agent
following the playbook planned what the playbook said.

The baseline was also less ignorant than it looked. The playbook's steps cite
Airflow's own `execution_api/AGENTS.md` ("Adding a New Feature End-to-End").
The repository already documents most of this procedure, and agents without a
bundle can read it.

What this points to: a playbook's completeness can't be left to the
generating agent. `cochange` already knows the partner set, so verify can
check it deterministically: a note when a high-lift partner of a playbook's
`applies_to` is missing from its `requires`.

## 13c. Run 7 — a repository that doesn't document its procedures

**Date:** 5 November 2026

Airflow documents its Execution API procedure in its own `AGENTS.md`, so an
agent without a bundle could read it (§13b). mitmproxy doesn't: its
`AGENTS.md` only says how to run tests. The task is to plan mitmproxy#7910,
which makes the TCP inactivity timeout a `tcp_timeout` option. Upstream
changed five places. Two of them nothing in the repository's docs mentions:
regenerating `web/src/js/ducks/_options_gen.ts` from `web/gen/options_js.py`,
and the `CHANGELOG.md` entry. `cochange` shows the first at lift 10.7 against
`mitmproxy/options.py`.

Haiku 5.5 built the bundle with the unreleased 0.11.0 (branch `ontology-layer`): options, optmanager,
proxy core, tools and web/gen, 14 concepts, one Playbook ("add an option")
and one Guardrail. `validate` reported 0 errors and `verify` 0 findings, in
62 turns and 6 min 4 s. Plans were graded on the five parts.

The first round had three attempts per arm. Ten more per arm followed, with
the same image, bundle, prompt and grader. Combined:

| Arm | Attempts | Perfect plans | Score (mean) | Turns | Input tokens (mean) |
|---|---:|---:|---:|---:|---:|
| none | 13 | 10 | 0.954 | 11.3 | 269,746 |
| typed bundle + `find` | 13 | **13** | **1.000** | 10.5 | 245,946 |

**The first result in the bundle's favour.** Every plan that used `find` was
complete. Without a bundle, two plans left out regenerating
`_options_gen.ts`, and one didn't declare the option at all. Input tokens
were 9% lower with the bundle, where on Airflow `find` added 56%. Every
bundle-arm plan names the playbook.

How strong this is: three failures out of 26 plans, all in the no-bundle arm.
The chance of that split happening by luck alone is 0.11 (one-sided Fisher
exact), so it is suggestive, not significant. The token difference is within
the spread of either arm.

### Control: a plain bundle without the ontology layer

To find out which part did the work, a third arm used a bundle built by the
published skill (0.10.1, from `main`). It has the same scope and the same
model, but no typed relations, no playbook and no `find`. The agent read it
through the plain "start here" pointer. 13 attempts. That bundle has 11
concepts, `verify` 0 findings, and it mentions `_options_gen.ts` and its
regeneration in four of them.

| Arm | Attempts | Complete plans | Input tokens (mean) | Turns |
|---|---:|---:|---:|---:|
| none | 13 | 10 | 269,746 | 11.3 |
| plain bundle, read up front | 13 | **13** | 291,440 | 10.2 |
| typed bundle + `find` | 13 | **13** | 245,946 | 10.5 |

**The plain bundle did as well.** On this task the gain came from having a
bundle at all, which put the generated file in front of the agent. The
ontology layer didn't add correctness. Its one edge is cost: `find` used 16%
fewer input tokens than reading the plain bundle, but that gap is within
the spread of either arm.

### Conclusion

**The ontology layer did not help.** Across runs 6 and 7 it added nothing
that a plain bundle from the released skill didn't also give:
- on Airflow, which documents its own procedures, it matched no bundle at
  56% more tokens;
- on mitmproxy, which doesn't, a plain 0.10.1 bundle was just as complete.

What helped on mitmproxy was having a bundle at all, in a repository that
doesn't write its procedures down. The layer was not merged. Its code stays
on the [`ontology-layer`](https://github.com/alexcpn/catalogify/tree/ontology-layer) branch for reference.

Caveats:
- One checklist item was widened after the first scoring, for both arms.
  Every no-bundle plan declared the option with `loader.add_option` in the
  proxyserver addon instead of `mitmproxy/options.py`, which is a valid
  mitmproxy pattern. Before widening, the scores were 0.73 against 0.93.
- The prompt asks for generated files, which helps both arms find
  `_options_gen.ts`.
- One task, one repository, one model. The gap is the knowledge an
  undocumented repository hides, which is where a bundle should help; it says
  nothing about repositories that already document their procedures (§13b).

## 14. Open follow-ups

1. ~~Re-run generation under catalogify 0.7.0 and compare finding counts.~~
   Done — §9.
2. Fix the V4 extractor per section 6, then re-verify. Tracked as
   [#4](https://github.com/alexcpn/catalogify/issues/4). Note that
   run 2 produced no V4 findings at all, so the false positives in section 5
   are latent rather than fixed.
3. Work through the 21 `open_questions` with the clarify workflow, and record
   what a human answer changes.
4. Repeat on `apache/airflow`, whose 82 provider packages would let the
   ninety-service figure be measured rather than extrapolated. Partially done — §11.
