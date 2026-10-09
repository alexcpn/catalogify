# Catalogify - Context is Everything

**A codebase knowledge base the agent can actually afford to read — grounded in git, held to a commit.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`catalogify` turns a repository into an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
(OKF v0.1) bundle: linked Markdown concepts covering architecture, services,
modules, APIs, data models and operations. Your existing coding agent reads the
evidence and writes the catalog; the CLI only collects facts and checks claims.

- [QuickStart:Install Skill and Use](#quickstart-agent-skill)
- [The Four ideas](#the-four-ideas)
- [Recorded examples](#worked-examples)

## Why this exists

Agents stall on unfamiliar code. They need a map before they can navigate: who
owns the behavior, how the pieces fit, what already broke once. Full-repo
context dumps don't solve this — they drown the model. Hand-written wikis do,
just on a delay: they rot the moment someone merges.

`catalogify` takes the middle path. Capture the system-level structure once,
keep it cheap to refresh, and make every claim checkable.

## The four ideas

### 1. Architecture without the deep dive

The catalog describes high level architecture, service boundaries, key interfaces,
data and dependencies — enough for the agent to decide where to look, not
enough to replace the source. Deep source scan is left to harness's efficient
tools like [ripgrep](https://github.com/burntsushi/ripgrep), git grep, and AST parsers
like [Graphify](https://github.com/Graphify-Labs/graphify)

This matters on large repos and monorepos with hundreds of microservices. Bounded inventories
and history keeps the context size manageable. Full source scans, AST parse trees and the like
exhausts even the largest context sizes.

In a recorded Apache Airflow run, **1.8 million lines of code** produced 17
concepts totalling about **9,700 tokens**. That was a coarse overview, not
exhaustive coverage — a catalog covering hundreds of services will be larger, 
but would still fit into the model context.

### 2. A wiki with a DB like transaction log 

All wikis go stale. This one does too, unless there is an automated pipeline that updates 
with every commit. However even without a pipeline, this wiki freshness or staleness is clearly 
known. It keeps a transaction log with the commit SHA of the update. Comparing with the HEAD, an Agent can easily
understand whether the wiki needs update, and it can do so with the git diffs.

OKF keeps knowledge in ordinary Markdown with YAML frontmatter, concept links
and indexes. You can browse it on GitHub, review its diffs and commit it beside
the source.

Each concept lists its `source_files`; the bundle's `log.md`
records the repository commit each update covered:

```markdown
## 2026-10-06
Commit: `<repository-sha>`
* **Update**: Refreshed the payment service for the retry behavior change.
```

When you ask for an update, the agent compares that SHA with `HEAD`, diffs the
commits between them, and maps changed paths to concepts. Renames update source
mappings; removed components become deprecated; significant new code becomes a
candidate for a new concept. A rewritten history triggers a full re-scan instead
of trusting the old commit range.

The wiki is treated like code: versioned, diffable, checkpointed. The log is a
checkpoint for incremental review, not proof that every sentence is current —
uncommitted edits aren't in the diff. Invoke the update workflow after code
changes, before you lean on the catalog.

Human answers from the **clarify** workflow carry protection markers; updates
preserve them. Changes to your `GUIDANCE.md` re-check the whole catalog against
the new guidance, even when the code commit is unchanged.

### 3. Implicit knowledge from commit history

Code is the source of truth for what the system *does*. Commit history records
what the team *learned*: a retry that corrupted data, a migration that had to
be reverted, a race fixed years before the current maintainers arrived. Those
lessons rarely survive in comments, ADRs or the heads of people who left.

`catalogify history` surfaces risk-related commits, issue-closing messages and
`Fixes:` trailers — with body excerpts and the files each commit touched. The
agent investigates that evidence, follows relevant reverts back to the change
they undid, and writes supported lessons with commit citations. `cochange`
surfaces paths that repeatedly change together, hinting at relationships no
import graph shows.

Historical behavior may have changed again. The agent reconciles each lesson
with current code and leaves unresolved questions explicit rather than
guessing. Git can only supply reasoning somebody recorded; the clarify workflow
captures what still needs a human.

### 4. Deterministic verification

The agent writes the prose; `catalogify verify` checks the claims — no LLM in
the loop. In Python and plain git commands it resolves backtick-quoted commit
SHAs and confirms they touched the concept's declared source files, rejects
citations to commits that only changed tests, `git grep`s unambiguous interface
names from concept tables in tracked non-test source, and flags source paths
that aren't in git at all. Findings fail the command (`--strict` makes notes
fail too). `catalogify validate` separately enforces OKF structure, links and
log format.

This catches concrete classes of hallucination — invented SHAs, citations to
unrelated fixes, test-only evidence for production gotchas, names that don't
exist in the code. It does not prove the prose correctly interprets the
evidence, or that the catalog covers everything. Current behavior is grounded
in source; historical lessons cite commits; human clarifications are recorded
separately. A passing check still needs review.

## Quickstart: Agent skill

Install the package from PyPI, then copy its skill into your agent:

```bash
uv tool install catalogify
catalogify install
```

`uv tool install catalogify` uses the published PyPI version. **To test changes
on `main` before a release**, install from GitHub instead:

```bash
uv tool install --force git+https://github.com/alexcpn/catalogify
catalogify install
```

The second command matters: your agent reads a copied skill, so upgrading the
package alone does not update its instructions. Restart the agent after either
installation. Python 3.9+ and `bash` are required; git adds history mining and
incremental updates but is optional. See [Requirements](#requirements).

Open the repository you want to document and **enter these in the agent chat**:

```text
Use catalogify to generate a knowledge catalog for this repo.
Use catalogify to clarify the open questions in knowledge/.
Use catalogify to validate knowledge/ and verify its claims against the repo.
```

Run the prompts in order. The first creates `knowledge/`; the second asks you
about facts the agent could not establish. Your answers become part of the
catalog and survive later updates. You can skip a question and leave it open.
After committing code changes, ask your agent to check and refresh the catalog:

```text
Use catalogify to update knowledge/ from its last recorded commit, then validate and verify it.
```

The skill handles the supporting terminal commands. Run this before using the
catalog to plan another change; freshness checks happen when you invoke the
workflow.

**Tell it what the code doesn't say.** Before the first run, or at any point
later, put a `GUIDANCE.md` in `knowledge/`. The agent reads it on every run and
never edits it. It helps most with things no scan can find, such as a pipeline
whose stages never import each other and only meet through a queue or a table.
Name the stages in order and ask for one Pipeline concept that walks them. If
you add or change the file after the catalog exists, the next update checks
every concept against it and fills in what's missing. More in
[Steering a bundle](#steering-a-bundle).

For deeper explanations, add `detail: detailed` to the generate or update
prompt. This changes the depth of each concept without adding more concepts:

```text
Use catalogify to generate a knowledge catalog for this repo. Use detail: detailed.
```

[![asciicast](https://asciinema.org/a/xSfPT9wUxCD78mz0.svg)](https://asciinema.org/a/xSfPT9wUxCD78mz0)

## Spec Kit extension

Also available as a Speckit Extension https://speckit-community.github.io/extensions/okf

```bash
specify extension add okf --from \
  https://github.com/alexcpn/catalogify/releases/download/v0.10.1/speckit-okf-0.10.1.zip
```

Then **enter these in your agent chat** (use the command names your agent
registered):

```text
/speckit.okf.generate
/speckit.okf.clarify
/speckit.okf.validate
/speckit.okf.verify
```

After code changes, use `/speckit.okf.update`. Add `detail: detailed` to
`generate` or `update` arguments when you want deeper explanations for that
run, for example `/speckit.okf.generate detail: detailed`.

| Spec Kit command | Purpose |
| --- | --- |
| `/speckit.okf.generate` | Create a catalog from code and git history. |
| `/speckit.okf.update` | Refresh concepts affected by code changes. |
| `/speckit.okf.clarify` | Ask you to resolve open questions. |
| `/speckit.okf.validate` | Check the bundle's OKF structure. |
| `/speckit.okf.verify` | Check claims against the repository. |

**Command names depend on your agent.** Spec Kit names them after the
integration you chose. Claude Code and Codex register them as skills with
hyphens (`/speckit-okf-generate`, `/speckit-okf-verify`, …); other agents get
the dotted form shown here. Install the extension *after* choosing your agent
integration. Adding an integration later does not register extensions that
are already installed, so rerun the install with `--force`.

The extension reads its config from `.specify/extensions/okf/okf-config.yml`.
See the [extension guide](integrations/speckit/README.md) for more installation
details


## The four workflows

These workflows run through the agent skill or the Spec Kit extension. Ask your
agent in plain language with the skill, or use the extension commands above:

| Workflow | What it does |
| -------- | ------------ |
| **generate** | Inventory scan, git-history mining, concept plan, concept documents, `index.md` files, `log.md`, validation. |
| **update** | Diffs since the last logged commit; refreshes only stale concepts, deprecates orphans, adds new ones, preserves human curation. |
| **clarify** | Asks you about the `open_questions` the other workflows parked, then folds the answers in as cited, curation-protected knowledge. |
| **validate** | OKF §9 conformance check plus a quality spot-check. |

## What you get

The generated catalog lives in `knowledge/` by default, ready to commit next
to the code:

```
knowledge/
├── index.md            # okf_version: "0.1" + directory of everything
├── log.md              # dated history, each block records a commit SHA
├── README.md           # front door for humans browsing the repo
├── GUIDANCE.md         # optional, yours: steers the agent (see below)
├── architecture/
│   └── overview.md     # type: Reference — the "start here" concept
├── services/…          # type: Service
├── modules/…           # type: Module
├── apis/…              # type: API Endpoint / API Resource
├── data/…              # type: Data Model / Database Table
└── operations/…        # type: Pipeline / Configuration / Playbook
```

On a monorepo, raise `OKF_INVENTORY_CAP` above its default of 150. Raw churn
skews toward generated files and build config, so invest in the `exclude` list.

The `okf.detail` setting defaults to `default`, preserving existing output.
`detailed` asks for deeper interfaces, dependencies, history, gotchas, open
questions, and explanatory prose without changing which concepts are selected.
An explicit `detail: detailed` request in your agent prompt or Spec Kit command
overrides the config for that run without editing it.

## Configuration

Everything works with no config. To change the bundle directory, resource URI
base, excludes, type mappings, layout, detail mode, or the clarify question
budget, copy the annotated template into your repo root:

```bash
cp ~/.claude/skills/catalogify/okf-config.template.yml .okf-config.yml
```

The agent passes this config to its tools automatically once the file exists.
The inventory and validation tools both honor its `exclude` list.

## Steering a bundle

catalogify picks what to document from generic signals: entry points, schemas,
churn, co-change. It can't know your domain terms, which subsystems you care
about, or that every service in your shop needs an ownership section. Two
things fill that gap, and both are optional.

**`GUIDANCE.md` in the bundle directory** (`knowledge/GUIDANCE.md` by default).
Plain markdown, written by you, read by the agent before every generate, update
and clarify run. Use it for vocabulary, audience, what to cover or skip, extra
concept types or layout directories, extra sections per type, and read-only
checks such as "list every `// INVARIANT:` comment". It is not a concept, and
the agent never edits it. When it changes, the next update re-checks every
concept against it, filling gaps without rewriting curated text. Each `log.md`
block records which version was used (`Guidance:` plus the first 12 hex digits
of its SHA-256). A starting point ships with the skill as
`examples/GUIDANCE.md`:

```markdown
## Vocabulary
- Say **tenant**, not customer. A tenant owns one or more workspaces.

## Sections per type
- Every `Service` has a `# Configuration` section: the environment variables
  it reads (names and shape only, no values).

## Coverage
- Skip `tools/migrate-v1/`: one-off code, kept only for audit.
```


## Upgrade

**Upgrading is two steps.**
`catalogify install` *copies* the skill into each agent's skills directory. Those
copies do not track the package, so a new version of the CLI leaves your agents
following the old instructions.

```bash
uv tool upgrade catalogify     # 1. the CLI
catalogify install             # 2. the skill copies (overwrites by default)
```

Check that both actually moved — they are versioned independently:

```bash
catalogify --version                                  # the CLI
grep -m1 version: ~/.claude/skills/catalogify/SKILL.md # the skill your agent reads
```

Then restart your agent so it reloads the skill.

### Installing an unreleased version

`uv tool install catalogify` and `uv tool upgrade catalogify` use PyPI, so they
do not include changes merged after the last release. To run `main` or a local
checkout, force a reinstall over the existing one:

```bash
uv tool install --force git+https://github.com/alexcpn/catalogify   # from main
uv tool install --force /path/to/catalogify                         # from a checkout
catalogify install                                                  # then the skill, as always
```

`catalogify install` already forces overwrites, so it needs no flag of its own.
`--force` there exists only for `--scope project`, which refuses to clobber an
existing project-local skill without it.
Installing from GitHub does not change the declared package version, so
`catalogify --version` can still show the same number as the PyPI release.

By default, `catalogify install` copies the skill into every agent's user-global
skills directory (`~/.claude/skills`, `~/.cursor/skills`, `~/.codex/skills`,
`~/.agents/skills`). Use `--agents claude,cursor` to target specific agents.
The bundled `install.sh` / `install.ps1` do both installation steps, install
`uv` if needed, and fall back to `pip install --user`.

## Requirements

- **Python 3.9+**
- **`bash`** — present on Linux and macOS; on Windows the wrapper finds the `bash.exe` that ships with [Git for Windows](https://git-scm.com/download/win), starting from where `git.exe` is installed. It never uses the `bash.exe` in `System32`, which is a WSL launcher.
- **`git`** — needed for history mining, repository verification and incremental updates. Initial generation and structural validation work without it; see [What it runs on](#what-it-runs-on).

## Worked examples

Browse the [Apache Airflow catalog](https://github.com/agentic-ai-demos/airflow/tree/main/knowledge)
and the [Online Boutique catalog](https://github.com/agentic-ai-demos/microservices-demo/tree/main/knowledge).
The figures below describe recorded runs; the linked catalogs may change later.

| Recorded run | Apache Airflow | Online Boutique |
| --- | ---: | ---: |
| catalogify version | 0.8.0 | 0.7.0 |
| Concepts | 17 | 21 |
| Concept text, approximate tokens | **9,700** | **13,300** |
| Fresh input to generate | 101,559 tokens | 117,850 tokens |
| Total generation tokens, including cached input and output | 1,207,172 | 1,600,683 |
| Wall clock | 6 min 29 s | 8 min 19 s |
| Final verify findings | 0 | 0 |

Airflow's measured source tree was roughly **1.8 million lines**. Its catalog
was smaller than Boutique's because the run selected a coarser overview.
These runs show that a large source tree can produce a small context artifact;
they do not establish complete coverage or a fixed cost for every repository.
Concept token estimates use bytes divided by four. Generation usage includes
repeated input, with over 91% of input served from cache in both runs.

The initial Boutique run produced **17 verification findings**. A later run
with the verify-and-fix workflow ended with zero. That measures removal of
specific detectable errors, not proof that all prose is correct.
[EXPERIMENTS.md](EXPERIMENTS.md) preserves the runs, costs, findings and caveats.

## What it runs on

Use it on a single repository, a monorepo, or a selected subtree. Concepts are
scoped by folder, with one Service concept per deployable unit at the chosen
scope. On large monorepos, tune the inventory cap, exclusions and concept
granularity rather than assuming the whole catalog will fit in one prompt.

The recorded Kubernetes inventory scanned 25,917 files and 500,022 lines of Go
in 2.1 seconds, producing 56 KB of JSON. That is collection time, not the time
needed for the agent to generate or review a catalog.

Git is optional for initial generation and structural validation. History
mining, repository verification and incremental updates require it.

| Capability | With git | Without git |
| --- | --- | --- |
| Inventory, concepts, indexes, structural validation | yes | yes |
| Churn ranking and lessons from commit history | yes | unavailable |
| Verification against git and tracked source | yes | skipped |
| Incremental update from log.md | yes | unavailable |

Outside git, the log records ``Commit: `none` `` and timestamps come from file
modification times. There is no commit baseline to diff against, so the agent
must explain that limitation and preserve human curation when planning a refresh.
Use a full-history checkout for history mining; shallow clones limit what can
be recovered, and the history command warns about them.

## What a concept looks like

```markdown
---
type: Module
title: Container Manager (cm)
description: Owns cgroup hierarchy, CPU/memory/device allocation, and the
  on-disk checkpoints that let those allocations survive a kubelet restart.
tags: [cgroups, cpumanager, checkpoint, qos]
source_files: [pkg/kubelet/cm]
open_questions:
  - "After the V2→V3 migration fix was reverted, is the V3→V2 hybrid-state
     hazard still live, or was it addressed another way?"
---

# Gotchas

Checkpoint format changes are the highest-risk edit in this module, and the
hazard is the fallback path. When a V3 checkpoint has an invalid checksum,
restore falls back to V2, but the V3 fields already read stay in the struct,
producing a hybrid of V2 and V3 data (`83f1cae9656`, reverted by
`76100602564`).
```

That gotcha is not in a comment, a docstring, or an ADR. It was recovered from
the commit log by following a revert back to the commit it reverted.

`source_files` maps the concept to code, which is what makes incremental
updates possible. `open_questions` is where uncertainty goes instead of into
prose. Both are producer extension fields permitted by OKF §4.1.

## Working with human knowledge

The workflow asks the agent to put uncertainty in `open_questions`, then use
**clarify** to capture your answers. Updates preserve those answers and other
human curation. Removed code leads to deprecated concepts rather than deleted
pages, keeping existing links and historical context available.

Generation and updates write inside the bundle directory. The agent is
instructed to describe configuration shapes without copying secret values;
the validator also scans for possible secrets. These are workflow safeguards
and checks, not a guarantee that generated documentation needs no review.

## Reproducing the benchmark

The Kubernetes measurements used commit `d5ccf7968e5`. To inspect the same
source revision and run the collection tools:

```bash
git clone --filter=blob:none --no-tags \
  https://github.com/kubernetes/kubernetes.git k8s
cd k8s
git checkout d5ccf7968e5
catalogify inventory
catalogify history pkg/kubelet/cm --limit 3
```

Then ask your agent to generate a catalog scoped to `pkg/kubelet`, validate it
and verify its references. The original coarse run produced nine concepts,
about 5,600 tokens in total, with a 676-token service entry. Those are observed
sizes, not a fixed token budget per service. Models, scope and chosen detail
will change the output. The original results remain in [EXPERIMENTS.md](EXPERIMENTS.md).

## CLI reference: tools the agent calls

The skill calls these analysis and checking commands while it works. They are
listed here for inspection and automation; **to generate, update, or clarify a
catalog, ask your agent**. Those three workflows are not CLI subcommands.
`catalogify install` is the separate terminal command that copies the skill to
your agents. Every CLI command accepts `--help`.

```bash
catalogify inventory                        # repo facts + git churn, as JSON
catalogify history pkg/foo --limit 5        # the reverts and hotfixes behind a path
catalogify cochange pkg/foo --depth 3       # what changes when this changes
catalogify validate knowledge/              # OKF v0.1 §9 conformance (structure)
catalogify verify knowledge/                # do its claims survive the repo?
catalogify install [--list] [--uninstall]   # manage the agent skill
```

- **`inventory`** writes JSON: file tree, languages, entry points, dependency manifests, API definitions, schemas, CI/CD, docs, ADRs, per-file commit churn, any untracked subtrees found on disk so they can be named and skipped rather than mistaken for part of the project, the agent docs (`AGENTS.md` and kin) with the directory each covers, and whether the bundle has a `GUIDANCE.md`. On the full Kubernetes tree (500k lines, 25,917 files) it takes 2.1 seconds and produces 56 KB.
- **`history`** returns the creation commit, recent subjects, and the flagged commits where invariants hide, each with the files it touched, its issue/PR refs and a body excerpt. A commit is flagged for a risk word in its subject (revert, deadlock, race…), for closing an issue anywhere in its message (`Fixes #842` — bug fixes whose subject sounds harmless), or for a `Fixes: <sha>` trailer naming the commit that introduced the bug. A commit that changed only test files is marked `[TEST-ONLY]` to help the agent distinguish test maintenance from production behavior. Diffs are omitted by default; `--patch` opts in, and commit text still needs review for secrets.
- **`cochange`** mines logical coupling from history: units that keep changing in the same commit, scored by support, confidence and lift. This can surface candidates for shared contracts or deployment dependencies that need investigation. Co-change is a signal, not proof of a dependency.
- **`validate`** enforces OKF §9: four error classes, twelve warning classes. W9 catches links that validate against the spec and 404 on GitHub — a leading `/` means *bundle* root to OKF and *repository* root to every renderer, so bundle-relative links break whenever the bundle sits in a subdirectory. This is a check on *structure*.
- **`verify`** checks commit references, source tracking, interface names and dependency evidence as described [above](#4-deterministic-verification). Findings fail the command; notes require judgement and fail only with `--strict`. It does not assess whether the prose correctly interprets the evidence.

Each is also installed under a bare `okf-` name (`okf-inventory`,
`okf-history`, `okf-cochange`, `okf-validate`, `okf-verify`); the first two and
`okf-validate` carry over from the package's previous life as `okf_skill`.

## Uninstall

```bash
catalogify install --uninstall    # remove from every agent's skills dir
uv tool uninstall catalogify
```

Run `catalogify install --list` first to see where it is installed.

## License

MIT
