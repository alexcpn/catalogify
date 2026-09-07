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

Findings are `catalogify verify` results on the finished bundle. Run 0 predates
`verify` and was judged retrospectively. Runs 1 and 2 are the same repository
and commit, regenerated under a later version.

Detail sections: run 1 in §1–§8, run 2 in §9, run 3 in §11, run 0 in §12.

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
