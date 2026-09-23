# catalogify

**Turn a repository into a knowledge catalog your AI agent can afford to read.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`catalogify` generates an [Open Knowledge Format (OKF v0.1)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle: a directory of cross-linked markdown concepts with YAML frontmatter
describing a codebase's services, modules, APIs, data models and operations.
Where git is available it mines the history for the reasoning behind the code,
and whatever it cannot establish it parks as an open question rather than
inventing an answer.

- **Monorepo or single repo.** One `Service` concept per deployable unit, scoped by folder — a repo with hundreds of services produces the same directory layout as a single-service repo, just wider.
- **Cheap on large codebases.** Scanning 25,917 files and 500,022 lines of Kubernetes takes 2.1 seconds. A service entry is ~676 tokens whether the service is 10k lines or 100k.
- **Git optional.** History mining and incremental updates need it; everything else does not.

It installs as a portable **Agent Skill**, so it works in Claude Code, Cursor,
OpenAI Codex, and anything else that reads the open `.agents/skills` standard.
Your agent follows the skill to generate, update, clarify, or validate a catalog.
The package also provides a **CLI** for repository scans, history analysis,
bundle checks, and skill installation.
For [Spec Kit](https://github.com/github/spec-kit) projects the same workflows
ship as slash commands, built from this repository
([below](#spec-kit-extension)).

## Quickstart: agent skill

Install the package from PyPI, then copy its skill into your agent:

```bash
uv tool install catalogify
catalogify install
```

`uv tool install catalogify` uses the published PyPI version. **To test changes
on `main` before a release**, including the new `detail` setting, install from
GitHub instead:

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
After code changes, ask your agent to update the catalog. The catalogify skill
handles the supporting terminal commands for you.

For deeper explanations, add `detail: detailed` to the generate or update
prompt. This changes the depth of each concept without adding more concepts:

```text
Use catalogify to generate a knowledge catalog for this repo. Use detail: detailed.
```

[![asciicast](https://asciinema.org/a/xSfPT9wUxCD78mz0.svg)](https://asciinema.org/a/xSfPT9wUxCD78mz0)

## Spec Kit extension

If your project already uses [Spec Kit](https://github.com/github/spec-kit),
install the extension instead of the standalone skill. It supplies the same
workflows as agent commands and does not require `catalogify` to be installed.
Install the published extension after choosing your Spec Kit agent integration:

```bash
specify extension add okf --from \
  https://github.com/alexcpn/catalogify/releases/download/v0.9.2/speckit-okf-0.9.2.zip
```

**To test changes on `main` before a release**, build and install the extension
from this checkout:

```bash
python3 integrations/speckit/build.py
specify extension add --dev build/speckit-okf
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
details. Both installation routes produce the same OKF v0.1 bundle; installing
both registers two skills for the same workflows.

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

### Project-scoped installs

`--scope project` copies the skill into `./.<agent>/skills` instead of your home
directory. Those copies are upgraded the same way, but only from inside the
project:

```bash
cd /path/to/your/repo
catalogify install --scope project --force
```

`catalogify install --list` shows every location the skill is installed, which is
the quickest way to find copies you have forgotten about.

### Telling which version wrote a bundle

Every concept records the generator in its frontmatter:

```bash
grep -rh generated_by knowledge --include='*.md' | sort -u
```

A bundle generated by an older version was written under that version's rules —
worth checking before trusting it, and worth regenerating after a
correctness-affecting upgrade.

## Requirements

- **Python 3.9+**
- **`bash`** — present on Linux and macOS; on Windows the wrapper finds the `bash.exe` that ships with [Git for Windows](https://git-scm.com/download/win).
- **`git`** — *optional*. Used for churn ranking, history mining and incremental updates. Everything else works without it; see [What it runs on](#what-it-runs-on).

## Worked examples

Two finished catalogs, published unedited. Start at the architecture overview in either and
click through.

| | [**Apache Airflow**](https://github.com/agentic-ai-demos/airflow/tree/main/knowledge) | [**Online Boutique**](https://github.com/agentic-ai-demos/microservices-demo/tree/main/knowledge) |
|---|---:|---:|
| Lines of code | **1,805,835** | 8,103 |
| Tracked files | 13,954 | 392 |
| Commits of history | 40,823 | 2,690 |
| Languages | Python, TypeScript, Go, JS | Go, C#, Node, Python, Java |
| Reading the source would cost | ~17,900,000 tokens | ~70,000 tokens |
| **The catalog it produced** | **17 concepts, ~9,700 tokens** | **20 concepts, ~11,600 tokens** |
| Compression | **1,838 : 1** | 6 : 1 |
| Fresh input to generate it | **101,559 tokens** | 117,850 tokens |
| Wall clock | 6 min 29 s | 8 min 19 s |

Read the last four rows together. Airflow is **1.8 million lines of code** — 223 times the size
of Online Boutique — and its catalog is *smaller*, took *fewer* uncached tokens, and finished
*faster*.

That is the whole property. Cost tracks the number of things worth naming, not the size of the
tree, so the catalog stays inside one context window no matter how big the repository gets.
Over 91% of each run was served from cache, so the billed figure is lower again.

Every run behind those figures — including the ones that went wrong — is recorded in
[EXPERIMENTS.md](EXPERIMENTS.md), with what it cost and what the checker found.

## Why it exists

Giving an agent "context on the codebase" is two problems.

**Routing** — *which of our 90 services does this spec touch?* Wide and
shallow. You need a little about everything.

**Reaching** — *inside that service, what changes?* Narrow and deep. You need
everything about a little.

A code graph such as [Graphify](https://github.com/Graphify-Labs/graphify) —
which parses your code with tree-sitter and builds a queryable graph of every
symbol and call edge — is excellent at reaching and will beat prose every
time. Ask it "what breaks if I change this function" and it answers precisely.
`catalogify` targets routing instead, where the winning property is being
small enough that an agent can read the whole estate in one call.

The two compose well: route with catalogify to pick the services, then run
Graphify inside the one you picked. They are not alternatives.

Measured on `pkg/kubelet` from `kubernetes/kubernetes` (108,648 lines of Go),
with Graphify run over the same directory:

| Artifact | Size | Tokens |
| --- | ---: | ---: |
| Graphify `graph.json` | 14.5 MB | 3,813,486 |
| Graphify `wiki/` (446 articles) | 1,004 KB | 256,968 |
| catalogify bundle (9 concepts) | 21.9 KB | 5,596 |
| **catalogify service entry** | **2.6 KB** | **676** |

At 676 tokens per service, a 90-service catalog is roughly **61,000 tokens**
and fits in one call alongside the specification. See [Reproducing the benchmark](#reproducing-the-benchmark)
to reproduce these numbers.

## How this relates to what else exists

The brownfield problem is well recognised, and several tools address parts of
it. They are worth naming, because they solve a different half.

**[Brownfield Bootstrap](https://speckit-community.github.io/extensions/brownfield)
and [BrownKit](https://github.com/github/spec-kit/issues/2510)** scan an
existing project and configure the harness to match it: a constitution derived
from your actual conventions, spec and plan templates matched to the detected
stack, module boundaries, capability and risk discovery. Both work by static
analysis of the working tree. **Neither reads your git history**, which is where
the invariants live — the reverts, the hotfixes, the rule somebody learned at
2am and never wrote down. catalogify starts there.

**Repomix and similar context loaders** put the codebase in front of the model
before work begins. That is the right instinct and it is bounded by arithmetic:
Airflow's source is roughly 17.9 million tokens. Its catalog is 9,700.

**Code graphs** (Graphify, tree-sitter indexers) answer *reaching* — what breaks
if I change this function — and answer it better than prose ever will. See
above: the two compose.

**Agentic search**, as Claude Code does it, has largely replaced precomputed
indexes for the reaching problem. That is one reason catalogify does not build
one. It operates a layer above, on the question you have to answer before
searching is worth anything: which parts of this system does this change touch?

What is left uncovered by all of the above is a durable, cheap description of
the estate, grounded in history and checkable against the code. That is the
only thing this tool tries to be.

## What it runs on

**Monorepos and single repos alike.** Concepts are scoped by folder, so a
repository holding hundreds of services gets one `Service` concept per
deployable unit and its own `modules/`, `apis/` and `data/` concepts
underneath — the same directory layout a single-service repo produces, just
wider. Point it at the whole tree or at one subdirectory.

**Large codebases stay cheap**, because the catalog describes the repo rather
than reproducing it. Scanning all of `kubernetes/kubernetes` — **25,917 files
and 500,022 lines of Go** — takes **2.1 seconds** and yields a 56 KB inventory
(~14,000 tokens) for the agent to plan from. Cost scales with the number of
things worth naming, not with lines of code: a service entry is ~676 tokens
whether the service is 10k lines or 100k.

**With or without git.** History mining is a bonus, not a requirement:

| | With git | Without git |
| --- | --- | --- |
| Inventory, concepts, indexes, validation | yes | yes |
| Churn ranking, the "why" from reverts and hotfixes | yes | — |
| Commit citations, `resource:` URLs from the remote | yes | — |
| Incremental `update` | yes | — (re-run `generate`) |
| Conformant bundle | yes | yes |

Outside a repository the inventory reports `git.is_git_repo: false`, `history`
prints a notice and exits cleanly, timestamps come from file modification
times, and `log.md` records ``Commit: `none` ``, which the validator accepts.
The agent is told to raise more `open_questions` in that case, since without
history the reasoning behind the code can only come from you.

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

## Why mine history at all

The gotcha in that example exists in no comment, no docstring, and no design
document — in Kubernetes, a project with KEPs, a design-proposals archive, and
reviewers who demand rationale. It survived only as a revert.

That is not an oversight, it is the normal condition. Michael Polanyi called it
tacit knowledge in 1966: *"we know more than we can tell."* Peter Naur applied
it to software in [*Programming as Theory Building*](https://pages.cs.wisc.edu/~remzi/Naur.pdf)
(1985), arguing that the real product of programming is the **theory** of the
system held in the developers' heads, and that program text and documentation
are insufficient carriers of it. A program whose original team has dispersed is,
in his terms, dead — and a new team patching it produces characteristically
wrong fixes that erode the system's conceptual integrity.

That is precisely the position an AI agent is in on first contact with your
repository. It arrives after the team has dispersed, holding the artefacts and
none of the theory.

Nor does writing a specification escape it. Fred Brooks, in *No Silver Bullet*:
*"the complexity of software is an essential property, not an accidental one,"*
so *"descriptions of a software entity that abstract away its complexity often
abstract away its essence."* That ceiling applies whether a human or a model
wrote the spec.

Commit history is a narrow exception. Nobody writes a revert as documentation;
they write it because production broke, leaving a dated, attributed, immutable
record of a place where the theory and the code disagreed. `catalogify history`
goes looking for exactly those.

This recovers fragments, not the theory. For everything still missing, the
generator raises an `open_question` and the clarify workflow asks a human while
there is still a human to ask.

## Safety properties

- **Never guesses.** Unverifiable facts become `open_questions`, resolved by the clarify workflow and marked with `<!-- clarified: ... -->` sentinels that later updates will not overwrite. Your answer outranks the machine's inference permanently.
- **Never deletes curation.** Removed code marks a concept `status: deprecated` rather than deleting it. Human prose survives every refresh.
- **Never emits secrets.** Config values are described by shape, never value, including from history. The validator flags anything that slips through (W5).
- **Never touches source code.** All writes stay inside the bundle directory.

## Reproducing the benchmark

To reproduce the table above:

```bash
git clone --filter=blob:none --no-tags \
  https://github.com/kubernetes/kubernetes.git k8s

# Graphify, for comparison
pip install graphifyy
graphify update k8s/pkg/kubelet
cd k8s/pkg/kubelet && graphify export wiki
wc -c graphify-out/graph.json          # 15,253,944
cat graphify-out/wiki/*.md | wc -c     # 1,027,874

# catalogify
cd ../..                               # back to the k8s repo root
catalogify inventory                   # 2.1s, 56 KB of JSON
catalogify history pkg/kubelet/cm --limit 3

# then ask your agent to generate and validate the catalog
```

Token counts are bytes ÷ 4. Measured against `kubernetes/kubernetes` at commit
`d5ccf7968e5`. The structural graph was built AST-only (no API key), so its
wiki lacks LLM community labels.

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

- **`inventory`** writes JSON: file tree, languages, entry points, dependency manifests, API definitions, schemas, CI/CD, docs, ADRs, per-file commit churn, and any untracked subtrees found on disk so they can be named and skipped rather than mistaken for part of the project. On the full Kubernetes tree (500k lines, 25,917 files) it takes 2.1 seconds and produces 56 KB.
- **`history`** returns the creation commit, recent subjects, and the revert / hotfix / risk-flagged commits where invariants hide, each with the files it touched. A commit that changed only test files is marked `[TEST-ONLY]` so a "fix goroutine leak in foo_test.go" is never mistaken for a production invariant. Diff-free by default so historical secrets do not leak; `--patch` opts in.
- **`cochange`** mines logical coupling from history: units that keep changing in the same commit, scored by support, confidence and lift. Two services can be coupled through a wire contract, a shared schema or a deployment ordering rule while sharing no import at all, and that relationship exists in no import graph, no call graph and no snapshot of the working tree. It shows up only in commits.
- **`validate`** enforces OKF §9: four error classes, ten warning classes. W9 catches links that validate against the spec and 404 on GitHub — a leading `/` means *bundle* root to OKF and *repository* root to every renderer, so bundle-relative links break whenever the bundle sits in a subdirectory. This is a check on *structure*.
- **`verify`** is a check on *truth*, and it is the one that matters. Every commit the bundle cites must exist and must touch that concept's own `source_files`; a commit that changed only test files cannot back a production invariant; every symbol in an `# Interfaces` table must appear in non-test code; a `# Gotchas` section that cites nothing is an unsupported claim; and every `source_files` path must be tracked by git, so a vendored dependency or an imported project sitting in your working tree cannot be written up as if it were yours. Run it in CI and an agent can no longer quietly write a confident sentence with nothing behind it.

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
