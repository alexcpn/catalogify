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

```bash
uv tool install catalogify
catalogify install
```

Then ask, in plain language:

```
"generate a knowledge catalog for this repo"
```

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
and fits in one call alongside the specification. See [Benchmark](#benchmark)
to reproduce these numbers.

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

## The four workflows

Ask in plain language and the skill picks one:

| Workflow | What it does |
| -------- | ------------ |
| **generate** | Inventory scan, git-history mining, concept plan, concept documents, `index.md` files, `log.md`, validation. |
| **update** | Diffs since the last logged commit; refreshes only stale concepts, deprecates orphans, adds new ones, preserves human curation. |
| **clarify** | Asks you about the `open_questions` the other workflows parked, then folds the answers in as cited, curation-protected knowledge. |
| **validate** | OKF §9 conformance check plus a quality spot-check. |

## Commands

The deterministic work is three subcommands you can run yourself, with or
without an agent. Each accepts `--help`.

```bash
catalogify inventory                        # repo facts + git churn, as JSON
catalogify history pkg/foo --limit 5        # the reverts and hotfixes behind a path
catalogify validate knowledge/              # OKF v0.1 §9 conformance
catalogify install [--list] [--uninstall]   # manage the agent skill
```

- **`inventory`** writes JSON: file tree, languages, entry points, dependency manifests, API definitions, schemas, CI/CD, docs, ADRs, plus per-file commit churn. On the full Kubernetes tree (500k lines, 25,917 files) it takes 2.1 seconds and produces 56 KB.
- **`history`** returns the creation commit, recent subjects, and the revert / hotfix / risk-flagged commits where invariants hide. Diff-free by default so historical secrets do not leak; `--patch` opts in.
- **`validate`** enforces OKF §9: four error classes, nine warning classes.

`okf-inventory`, `okf-history` and `okf-validate` remain as aliases from the
package's previous life as `okf_skill`.

## Requirements

- **Python 3.9+**
- **`bash`** — present on Linux and macOS; on Windows the wrapper finds the `bash.exe` that ships with [Git for Windows](https://git-scm.com/download/win).
- **`git`** — *optional*. Used for churn ranking, history mining and incremental updates. Everything else works without it; see [What it runs on](#what-it-runs-on).

## Install

```bash
uv tool install catalogify     # or: pip install catalogify
catalogify install
```

Restart your agent afterwards so it picks up the skill. `catalogify install`
copies it into every agent's user-global skills directory
(`~/.claude/skills`, `~/.cursor/skills`, `~/.codex/skills`,
`~/.agents/skills`). Use `--agents claude,cursor` to target specific ones and
`--scope project` to install into `./.<agent>/skills` instead.

The bundled `install.sh` / `install.ps1` do both steps, install `uv` if it is
missing, and fall back to `pip install --user`.

## Usage

```bash
agent "generate a knowledge catalog for this repo"
agent "refresh the catalog, the code has moved on"
agent "resolve the open questions in the catalog"
agent "validate the catalog"
```

Output lands in `knowledge/` (configurable), ready to commit next to the code:

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

On a monorepo, start with `granularity: coarse` and raise
`OKF_INVENTORY_CAP` above its default of 150. Raw churn skews toward generated
files and build config, so invest in the `exclude` list.

## Configuration

Everything works with no config. To change the bundle directory, resource URI
base, excludes, type mappings, layout, granularity, or the clarify question
budget, copy the annotated template into your repo root:

```bash
cp ~/.claude/skills/catalogify/okf-config.template.yml .okf-config.yml
```

`catalogify inventory --config .okf-config.yml` and `catalogify validate <dir>
--config .okf-config.yml` honor its `exclude` list; the agent passes it through
automatically once the file exists.

## Safety properties

- **Never guesses.** Unverifiable facts become `open_questions`, resolved by the clarify workflow and marked with `<!-- clarified: ... -->` sentinels that later updates will not overwrite. Your answer outranks the machine's inference permanently.
- **Never deletes curation.** Removed code marks a concept `status: deprecated` rather than deleting it. Human prose survives every refresh.
- **Never emits secrets.** Config values are described by shape, never value, including from history. The validator flags anything that slips through (W5).
- **Never touches source code.** All writes stay inside the bundle directory.

## Benchmark

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

# then ask your agent to generate the catalog, and check it:
catalogify validate knowledge/
```

Token counts are bytes ÷ 4. Measured against `kubernetes/kubernetes` at commit
`d5ccf7968e5`. The structural graph was built AST-only (no API key), so its
wiki lacks LLM community labels.

## Uninstall

```bash
catalogify install --uninstall    # remove from every agent's skills dir
uv tool uninstall catalogify
```

Run `catalogify install --list` first to see where it is installed.

## License

MIT
