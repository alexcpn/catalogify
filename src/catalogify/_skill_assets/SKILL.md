---
name: catalogify
description: >-
  Generate and maintain an Open Knowledge Format (OKF v0.1) knowledge bundle
  for a source-code repository — a directory of cross-linked markdown concepts
  with YAML frontmatter describing its services, modules, APIs, data models,
  and operations. Use when asked to document a codebase as a knowledge base,
  build or refresh an OKF bundle or knowledge catalog, mine git history for
  the "why" behind code, keep repo documentation in sync with code changes,
  or validate OKF conformance. Triggers on "catalogify", "OKF", "knowledge
  bundle", "knowledge catalog", "document this repo", "service catalog",
  "codebase knowledge base".
license: MIT
metadata:
  version: "0.5.0"
  commands:
    - catalogify
---

# OKF knowledge bundle

You are acting as an **OKF enrichment agent**. You analyze a source-code
repository and produce (or maintain) a conformant **Open Knowledge Format
v0.1** bundle: markdown files with YAML frontmatter that capture the
metadata, context, and curated insight surrounding the code — the things a
staff engineer would tell a new teammate, not a file-by-file paraphrase.

Spec: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>

Because the output is plain markdown in git, it is readable by humans,
diffable in PRs, and consumable by other agents with no bespoke tooling.

## Pick the workflow

Read **one** reference file — the one matching the task — and follow it.
Do not read all four.

| Situation | Read |
| --- | --- |
| No bundle yet (or an explicit full rebuild was requested) | `references/generate.md` |
| A bundle exists and the code has moved on since the last logged commit | `references/update.md` |
| Concepts carry `open_questions` that only a human can settle | `references/clarify.md` |
| Only a conformance/quality check is wanted | `references/validate.md` |

If unsure which applies, check for `.md` files under the bundle directory
(below): none → generate; some → update. Never run generate over an
existing bundle — it would destroy human curation.

## Commands

Three commands come with this skill and are already on `PATH` — no paths to
resolve, run them from anywhere inside the repo. Each accepts `--help`.

| Command | Purpose |
| --- | --- |
| `catalogify inventory [out.json] [--config <cfg>]` | Repo-wide inventory as JSON: file tree, languages, entry points, dependency manifests, API definitions, schemas/migrations, CI/CD, docs, ADR/RFC docs, plus `git.history` (`churn` per-file commit counts = significance signal, `recent_commits`). Prints `Inventory written to <path>` — read the JSON from *that* path, it is per-run and not fixed. Each category carries a `truncated` flag. |
| `catalogify history <path>… [--limit N] [--json] [--patch]` | Bounded per-concept git history: creation commit, commit count, recent subjects, and revert/hotfix/risk-flagged commits (deadlock, race, regression, security). This is where the **"why"** — invariants and gotchas — comes from. Diff-free by default; `--patch` opts into diffs and can surface secrets that were later removed. |
| `catalogify validate <bundle_dir> [--config <cfg>] [--json]` | OKF §9 conformance checker. ERRORs: unparseable frontmatter, missing/empty `type`, malformed `index.md`/`log.md`, `log.md` block missing its `Commit:` line. WARNINGs: W1 missing title/description, W2 broken links, W3 missing index, W4 empty body, W5 possible secret, W6 dangling `source_files`, W7 duplicate concept, W8 unresolved `open_questions`. |

`catalogify inventory` and `catalogify history` need `bash`, and use `git`
when it is available (on Windows both come with Git for Windows).

**Working without git.** Everything except history mining still works. The
inventory reports `git.is_git_repo: false` and empty history; `catalogify
history` prints a notice and exits 0 with no output. When that is the case:

- Skip history-based reasoning entirely rather than inventing it. No churn
  signal, no revert-derived gotchas, no commit citations.
- Take `timestamp` from the file's modification time instead of its last
  commit.
- Omit `resource:` unless the config supplies a `resource_base`, since there
  is no remote to derive one from.
- Write ``Commit: `none` `` in `log.md`. The validator accepts that in place
  of a SHA, so a bundle built outside git can still be conformant.
- Expect more `open_questions`, not fewer. Without history, the "why" has to
  come from a human, so ask rather than guess.

If a command is missing from `PATH`, the package is installed but its shell
has not been refreshed: tell the user to open a new terminal, or to re-run
`uv tool install --native-tls <source>`.

## Configuration

Look for `.okf-config.yml` in the repo root and use it if present; otherwise
use the documented defaults. `okf-config.template.yml`, installed next to this
file, is the annotated template and the authoritative list of defaults:
`bundle_dir: knowledge/`, `granularity: medium`, a standard `exclude` list,
`resource_base` derived from the git remote, type mappings, layout, and
`clarify.max_questions: 20`. Copy it to `.okf-config.yml` when the user wants
to change any of that. Everything works with no config at all.

Pass the config through whenever you found one — both `catalogify inventory --config
<path>` and `catalogify validate --config <path>` honor its `exclude` list; without
it they fall back to built-in defaults.

Two variables the reference files assume: **`CONFIG`** (the config path, or
unset) and **`BUNDLE_DIR`** (`okf.bundle_dir` from the config, else
`knowledge/`).

## Rules that hold across every workflow

- **Never fabricate.** When the code and its git history don't settle a fact,
  park a concrete, answerable question in the concept's `open_questions`
  frontmatter list rather than guessing. `references/clarify.md` turns those
  into human-confirmed knowledge. An honest gap beats a confident fabrication.
- **Never leak secrets.** Describe a config's *shape*, never its values. This
  applies to history too — `--patch` and `git blame` can surface credentials
  that were later removed.
- **Never destroy curation.** Removed code yields `status: deprecated`, never
  deletion. Facts guarded by a `<!-- clarified: ... -->` sentinel were
  confirmed by a human; leave them alone.
- **Preserve unknown frontmatter keys** on round-trip (OKF §4.1).
- **Writes stay inside `BUNDLE_DIR`.** Never modify source code.
- Reserved filenames `index.md` and `log.md` are never concepts (OKF §3.1).
- Only `type` is required in frontmatter, but always write `title` and
  `description` — indexes are useless without them.
- OKF's consumption model is permissive (unknown types fine, broken links
  fine), so generating early and often is safe; a broken link legitimately
  represents not-yet-written knowledge.

## Bundle shape

```
knowledge/
├── index.md            # okf_version: "0.1" + directory of everything
├── log.md              # dated history, newest first, each block records a commit SHA
├── architecture/
│   ├── index.md
│   └── overview.md     # type: Reference — the "start here" concept
├── services/…          # type: Service
├── modules/…           # type: Module
├── apis/…              # type: API Endpoint / API Resource
├── data/…              # type: Data Model / Database Table
└── operations/…        # type: Pipeline / Configuration / Playbook
```
