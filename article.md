# Improve Context before you Improve your Codebase

*1.8 million lines of Apache Airflow, described in a 9,700-token catalog an engineer can check. An experiment in giving AI agents useful context for inherited software.*

* **Repo:** [catalogify on GitHub](https://github.com/alexcpn/catalogify)
* **Demo:** [On Apache Airflow](https://github.com/agentic-ai-demos/airflow/tree/main/knowledge)
* **Speckit Extension:** Speckit-okf

Enterprises and major open-source projects are increasingly leaning on AI for feature development and bug fixes. However, they all face the same challenge: to execute large, system-wide changes, AI needs effective context.

Current maintainers can “vibe-code” small bits and pieces, but for large architectural shifts, AI coding agents operate like a brand-new engineering team. In the real world, a new team requires a transition period to absorb the implicit knowledge locked inside the previous developers’ heads.

As Software Design Documents (SDDs) regain popularity alongside AI, old debates have resurfaced. One vocal camp treats the “Spec as the Source of Truth,” while an equally fierce camp argues that the “Code is the Source of Truth.”

Software engineering pioneers like Fred Brooks, Peter Naur, and the philosopher Michael Polanyi figured this out long ago. Brooks dismantles the first camp: in “No Silver Bullet” he warns that “descriptions of a software entity that abstract away its complexity often abstract away its essence” — a spec is an abstraction, and can never be as detailed as the code itself. But before the source-code camp starts cheering, Naur reminds us that the code is incomplete too. In “Programming as Theory Building” he argues that the real theory of a program “could not conceivably be expressed, but is inextricably bound to human beings” — it lives in the developers’ minds. To top it off, Polanyi’s notion of tacit knowledge names the underlying human limit: “we can know more than we can tell.”

This is great theory, but the practical consequences hit hard when an AI agent makes a change. It might propose a remarkably logical pull request — completely unaware that the team deleted that exact logic a year ago because it caused a race condition and crashed production. How do we document these gotchas and system context?

## Three things people try

* **Dump the repo, or RAG over it.** Retrieval finds text that resembles the query. But the question a routing agent needs answered is which service owns pod eviction, and ownership is a fact about responsibility rather than a string that appears somewhere in the source. It lives in people’s heads and, when you are lucky, in commit messages.
* **Build a code graph.** Parse every file with tree-sitter and query the symbols and call edges. A tool like Graphify does this well: for the reaching question — “what breaks if I change this function” — it is precise and cheap. But the index has to be complete, and completeness is expensive. Graphify’s for a single kubelet service is a 14.5 MB `graph.json`, ~3.8 million tokens; ninety services would be 343 million. And a call graph has no opinion about what a service is for — which is the routing question. The catalog below takes the opposite bet, a few hundred tokens per service, every run logged.
* **Write better docs.** Nobody does. And the tools that generate docs usually automatically regenerate them on every commit, so the one correction a human bothered to make has a half-life of one push.

Take Apache Airflow: roughly 14,000 files and 1.8 million lines of code. Ask an agent to add Iceberg table support. Before it can make a useful plan, it needs to know which components own the work, how they interact, and which past mistakes it must avoid.

## Two kinds of Context: Shallow and Deep

Understanding a codebase involves two different jobs:

1. **Shallow (Which components does this change touch?):** A little about the whole system. A compact architecture and ownership map.
2. **Deep (What changes inside those components?):** Detailed knowledge of relevant code. Agentic code search, dependency graphs, tests, etc.

The difficult context is often *why* the code works this way. A dependency graph can show a relationship; it may not explain the compatibility rule behind it. Git history, especially fixes and reverts, can recover some of that reasoning.

## What the catalog must do

For this to be useful, I wanted five properties:

* **Small enough to read in full.** The agent needs to compare components before choosing where to look.
* **Checkable.** Claims about constraints and past failures should point to supporting code or commits.
* **Explicit about uncertainty.** Missing answers become questions for a human.
* **Preserve corrections.** Human input should survive regeneration.
* **Live in git.** Markdown files that can be reviewed alongside code.

I vibe-coded Catalogify for this. It writes these files using Google’s Open Knowledge Format: one file per concept, with metadata, links, and an index. It installs as a skill for Claude Code, Cursor, or Codex. There is also a Speckit Extension based on this. *(Please use the catalogify skill for the most up-to-date code, as the extension updates take time to sync to the Speckit Community).*

## From repository to map

Scripts gather bounded evidence; the agent uses it to organize and write the catalog.

1. **Inventory the repository.** A script lists tracked files and summarizes the structure. Airflow’s inventory took 0.98 seconds and produced about 14,000 tokens, giving the agent a starting point without reading every file.
2. **Identify meaningful components.** Change frequency and directories that repeatedly change together help reveal boundaries and relationships worth investigating.
3. **Extract interfaces and dependencies.** Scripts collect declarations and imports so the agent can ground its descriptions in the source.
4. **Investigate failures and reverts.** History searches flag commits mentioning problems such as races, leaks, or corruption. The agent must read the changes, including the original commit behind a revert, before describing a constraint.
5. **Record gaps and validate references.** Each entry is checked for guarantees, ordering, failure behavior, compatibility, and ownership. Unanswered questions stay visible. Validation checks cited commits and symbols against the repository.
6. **Stay cheap on large repositories.** Cost tracks the number of things worth naming, not the size of the tree: generating the Airflow catalog — 1.8 million lines — took about 101K tokens of fresh input, fewer than the 8,000-line Online Boutique, and the finished catalog reads in ~9,700 tokens. A complete code graph scales the other way: Graphify’s index runs ~3.8 million tokens per service, 343 million for ninety. On an inherited monolith, the catalog still fits in one context window; the graph cannot.

Reverts are particularly useful leads. In the kubelet’s container manager, for example, a checkpoint migration fix was reverted two days later. Reading the pair exposed a rollback compatibility problem that a scan of current interfaces would not explain.

History does not recover everything the original team knew. It gives the agent evidence to investigate and the reviewer a way to challenge the result.

## What the runs cost

I generated catalogs for two public repositories with Codex. The run log records the measurements, including failed runs.

| Measurement | Apache Airflow | Online Boutique |
| :--- | :--- | :--- |
| Lines of code | 1,805,835 | 8,103 |
| Estimated source tokens | ~17,900,000 | ~70,000 |
| Catalog entries | 17 | 20 |
| Catalog tokens | ~9,700 | ~11,600 |
| Fresh input tokens to generate | 101,559 | 117,850 |
| Generation time | 6 min 29 s | 8 min 19 s |

Airflow was 223 times larger, yet its catalog was smaller and faster to generate. In these two runs, catalog size reflected the chosen level of detail more than repository size. That is useful for navigation, but it does not establish completeness or prove that the catalog improves subsequent code changes.

Both catalogs are published unedited: Apache Airflow and Online Boutique.

## The most useful failure

When I audited an early Kubernetes catalog, I found production claims derived from commits that changed only tests. A fix for a goroutine leak in a test had become a supposed design constraint of the plugin manager.

The prompt explicitly told the agent to read beyond commit subjects. A second independent run repeated the same five mistakes. That means that even a good Agent harness mapped by Claude Opus or similar cutting-edge models can skip prompts/instructions sometimes.

I changed the evidence output: the script now lists the files each commit touched and labels commits that affect only tests as `[TEST-ONLY]`. That makes the distinction visible at the point where the agent forms its claim.

The citations also made the mistakes cheap to find. In one audit, I found four errors across nine entries in twenty minutes by following commit hashes with `git show`.

The lesson: **make evidence easy to inspect, and put mechanical checks in tools.** Fluent documentation still needs review.

## Try it on an inherited codebase

```bash
uv tool install catalogify
catalogify install

