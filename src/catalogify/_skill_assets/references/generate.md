# Generate — bootstrap an OKF knowledge bundle

You are acting as an **OKF enrichment agent**. Your job is to analyze this
repository and produce a conformant **Open Knowledge Format (OKF v0.1)**
knowledge bundle: a directory of markdown files with YAML frontmatter that
captures the metadata, context, and curated insight surrounding this codebase.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Scope hints: use any focus/scope the user gave (a subdirectory, a
subsystem, a granularity preference); otherwise cover the whole repo.

## Phase 0 — Configuration and inventory

1. Resolve `CONFIG` and `BUNDLE_DIR` as described in `SKILL.md`. If no
   config file exists, use the defaults documented in
   `okf-config.template.yml`, installed next to `SKILL.md`
   (`bundle_dir: knowledge/`, `granularity: medium`).
2. **Guard against clobbering curation.** If `BUNDLE_DIR` already exists
   and contains one or more `.md` files (whether or not `log.md` is
   present — a hand-seeded or partial bundle is still real curation),
   STOP here and tell the user to run the **update** workflow instead;
   regenerating from scratch would destroy that curation. Only proceed if
   the user explicitly asked for a full rebuild. If `BUNDLE_DIR` doesn't
   exist or is empty, continue.
3. Run `catalogify inventory` and read the path it prints (do not assume a
   fixed location — the script picks a per-run temp file to avoid
   collisions with concurrent runs):

   ```bash
   # if a config file was found, pass it so its exclude list is honored:
   catalogify inventory --config "$CONFIG"
   # otherwise run without --config to use the built-in defaults:
   catalogify inventory
   ```

   The script prints `Inventory written to <path>` — read the JSON from
   that path. It contains the file tree, languages, entry points,
   dependency manifests, schema/migration files, API definition files,
   CI/CD configs, existing docs, and ADR/design-decision docs
   (`adr_docs`), honoring the config's `exclude` list. Each category also
   carries a `truncated` flag (see the top-level `truncated` object) — if
   a category you need was truncated, either widen `exclude` in the config
   or ask the user before concluding you've seen the full picture for
   that category.
4. Note the **git history signals** under `git.history` in the inventory:
   - `churn` — files ranked by commit count (hottest first). Treat high
     churn as a **significance** signal in Phase 1 (a file touched by 40
     commits almost certainly deserves a concept and probably hides
     gotchas); treat near-zero churn as a hint the code may be trivial or
     generated.
   - `recent_commits` — recent non-merge subjects, a cheap first read on
     what the project has been doing lately.
   - Use these to prioritize; pull the deeper per-concept "why" in Phase 2
     with `catalogify history` (below). If not a git repo, `git.history` is
     empty — skip history-based reasoning rather than inventing it.
5. Determine `resource_base`: from config, else from
   `git remote get-url origin` + default branch (convert SSH form to an
   `https://.../blob/<branch>/{path}` form). If the repo has no remote,
   omit `resource:` fields entirely rather than inventing URIs.

## Phase 1 — Concept planning (do this BEFORE writing files)

Read the inventory plus key files (READMEs, entry points, route
definitions, schema files, docker/CI configs) and draft a **concept plan**:
a table of `concept_id | type | title | one-line description | source files`.

Selection rules by granularity (default: medium):

- Always: one `architecture/overview.md` concept (type: `Reference`)
  describing the system's purpose, high-level structure, and how the
  pieces fit together — with links to every other top-level concept.
- One concept per **deployable unit / service / app** (type: `Service`).
- One concept per **significant module or package** — significant means it
  has a coherent responsibility a new engineer would need explained, not
  merely that a directory exists (type: `Module`).
- One concept per **API surface**: group endpoints by resource or router
  file, not one file per endpoint unless granularity=fine
  (type: `API Endpoint` or `API Resource`).
- One concept per **data model / database table / event schema** found in
  migrations, ORM models, .proto/.avsc/OpenAPI schemas (type:
  `Data Model` / `Database Table`).
- One concept per **operational artifact** worth explaining: CI pipeline,
  deployment config, cron/scheduled jobs (type: `Pipeline`,
  `Configuration`).
- Optionally: `operations/` playbooks if the repo contains runbook-like
  docs; mirror external references into `references/` when the code links
  to essential external documents.
- Seed a `Design Decision` concept (in `architecture/`) for each ADR/RFC
  found in `adr_docs`, and mirror truly external decision records into
  `references/`.

**Use churn to break significance ties.** When deciding whether a
borderline module/file warrants its own concept, consult `git.history.churn`
from the inventory: high-churn files are both more important to explain and
more likely to carry hard-won gotchas, so bias toward giving them a concept
(and a richer "why" section). Do not create concepts for high-churn files
that are pure noise (logs, generated data, fixtures) — significance is about
*coherent responsibility*, not commit count alone.

Present this plan to the user briefly (the table), then proceed — do not
wait for approval unless the plan exceeds ~40 concepts, in which case ask
whether to coarsen granularity.

## Phase 2 — Write the bundle

Create the bundle under `BUNDLE_DIR` following OKF §3–§8 exactly:

### Frontmatter (every concept file)

```yaml
type: <Type>                      # REQUIRED, non-empty
title: <Human-readable name>
description: <ONE sentence, used in indexes and previews>
resource: <resource_base with the primary source file path>   # omit for abstract concepts
tags: [<lowercase-tag>, ...]
timestamp: <ISO 8601 — the MOST RECENT commit time across this concept's source_files;
            get each with: git log -1 --format=%cI -- <path>, then take the latest.
            If a source file is untracked / has no git history, fall back to the current UTC time.>
source_files:                     # extension field: repo-relative paths this concept derives from
  - path/to/file.py
generated_by: catalogify/0.5.0   # producer extension (OKF §4.1)
open_questions:                   # extension field: unresolved uncertainties (omit if none)
  - "Is the retry budget in submit_order() a hard SLA or a heuristic? Source is ambiguous."
```

`source_files`, `generated_by`, and `open_questions` are producer extension
fields (permitted by OKF §4.1). `source_files` is what makes incremental
updates possible, so always include it. Using the *latest* commit time across
`source_files` for `timestamp` keeps it consistent with how
the **update** workflow and the validator detect staleness (they compare
`timestamp` against each `source_files` entry's last commit time).

`open_questions` is how you **park uncertainty instead of guessing**: when the
code (and its git history) don't let you state a fact confidently — an intent,
an invariant, a "why" — add a concrete, answerable question here rather than
inventing an answer. The **clarify** workflow collects these, asks the user, and
folds the answers back into the bodies. Omit the field entirely when a concept
has no open questions.

### Body conventions

- Favor **structural markdown** (headings, tables, fenced code) over prose.
- Use conventional headings where applicable: `# Schema` for
  columns/fields of data concepts, `# Examples` for usage snippets,
  `# Citations` for external sources (numbered, per OKF §8).
- Write what a **staff engineer would tell a new teammate**, not a
  file-by-file paraphrase: purpose, invariants, gotchas, why it is shaped
  the way it is (cite commit messages or ADRs when they explain a
  decision).
- Do NOT copy large source excerpts. Short illustrative snippets only.
- Do NOT include secrets, tokens, credentials, or internal hostnames
  found in the code. If a config file contains secrets, describe its
  shape, never its values.

### Required sections for `Service` and `Module` concepts

A concept that describes code MUST carry all four of the following. A
concept with only prose is not useful to a routing agent — it can neither
be checked against the code nor traversed to a neighbour.

**1. `# Responsibilities`** — two to four sentences. What this owns, and
the shape of its control flow (request handler? reconciler? batch job?).

**2. `# Interfaces` — extracted, not remembered.** A table of the actual
public surface. Derive it from the source; never write it from memory.
Grep the concept's `source_files` for exported declarations, e.g.:

```bash
# Go — exported funcs and methods, tests excluded
grep -rn --include='*.go' -E '^func ([A-Z]|\([^)]*\) [A-Z])' <dir> | grep -v '_test\.go'
# Python — module-level defs and classes
grep -rn --include='*.py' -E '^(def [a-z]|class [A-Z])' <dir>
# TypeScript / JavaScript
grep -rn --include='*.ts' --include='*.js' -E '^export (async )?(function|class|const)' <dir>
# Java / C#
grep -rn --include='*.java' --include='*.cs' -E '^\s*public (class|interface|[A-Za-z<>\[\]]+ [a-z])' <dir>
```

Then select — do not paste hundreds of rows. Drop test fixtures and
fakes (`testing/`, `fake_*`, `mock_*`), and keep the entries a caller
would actually reach for (roughly 5–15), one line each:

```markdown
# Interfaces

| Symbol | Purpose |
| --- | --- |
| `SyncPod(pod, status)` | Drives one pod to its desired state; the main reconcile entry point. |
| `GetPodStatus(uid)` | Reads cached status; does not hit the runtime. |
```

If the surface is an HTTP or RPC API, list routes/methods instead of
symbols. If a concept genuinely has no public surface (a leaf helper),
say so in one line rather than omitting the heading.

**3. `# Dependencies` — derived from imports.** Do not guess the graph;
read it. Extract the concept's internal imports, then map each imported
path to the concept whose `source_files` contains it, and emit a
bundle-relative link:

```bash
# Go
grep -rh --include='*.go' -A40 '^import (' <dir> | grep -oE '"[a-z0-9./-]+/[a-z0-9./-]+"' | sort -u
# Python
grep -rhE --include='*.py' '^(from|import) ' <dir> | sort -u
# TypeScript / JavaScript
grep -rhoE --include='*.ts' --include='*.js' "from ['\"][^'\"]+['\"]" <dir> | sort -u
```

Every internal import that resolves to another concept becomes a link,
with the relationship named in prose ("calls", "reads from", "publishes
to"). List external packages separately, unlinked. This is what makes the
bundle traversable rather than a pile of independent files.

**4. `# Gotchas`** — the invariants and traps, each citing a commit (see
history mining below). Omit the heading only if history genuinely
surfaced nothing.

Also add `# Key files` when a reader would otherwise not know where to
start.

### Cross-linking

- Link with bundle-relative paths beginning with `/` (OKF §5.1), e.g.
  `[orders model](/data/orders.md)`. Express the relationship in the
  surrounding prose. Links to concepts you have not written yet are
  allowed — broken links legitimately represent not-yet-written
  knowledge (§5.3).
- Aim for every code concept to link to at least one other concept. An
  orphan concept usually means the `# Dependencies` step was skipped.

### Mine git history for the "why" — and follow the reverts

For each non-trivial concept, run the per-path history helper on its
`source_files` before writing the body:

```bash
catalogify history <source-file-or-dir>
# machine-readable: add --json ; cap the list: --limit N
```

It returns the creation commit, commit count, recent subjects, and — most
valuably — **revert/hotfix/risk-flagged commits** (reverts, hotfixes,
regressions, races, deadlocks, leaks, corruption, security fixes). Those
are your gotchas and invariants.

**Do not stop at the subject line.** A subject tells you something went
wrong; it rarely tells you the rule. For the two or three highest-signal
commits per concept, read the actual commit:

```bash
git show --stat <sha>          # what changed, no diff body
git show <sha> -- <path>       # the change itself (scrub secrets)
git log --follow -1 --format='%B' <sha>   # full message, often the real rationale
```

For a `Revert "X"` commit, always find and read the original X — the pair
is what carries the rule. Prefer `git blame -L <a>,<b> <file>` when you
need line-level rationale for one tricky hunk.

**Then write the rule, not the anecdote.** Several related commits usually
imply one invariant. Synthesize it:

> Bad (anecdote): "Commit `76100602564` reverted a checkpoint migration."
>
> Good (rule): "Checkpoint format changes must be forward *and* backward
> compatible, because nodes get downgraded — the V2→V3 migration was
> reverted (`76100602564`) and the V3 checksum later had to be fixed
> specifically for rollback (`bc752cdfdb0`)."

Cite every sha in `# Citations`. If history is thin or the "why" still
isn't clear, record an `open_questions` entry rather than guessing.

**Never leak secrets from history.** Historical commits and blame can
surface credentials that were later removed — describe shape, never
values, exactly as you would for current code.

### Interrogate for open questions — don't just wait to trip over one

`open_questions` should be *sought*, not only recorded when you happen to
notice a gap. Before finishing each `Service` or `Module` concept, ask
these five questions of it, and park any you cannot answer from code plus
history:

| Category | Ask |
| --- | --- |
| Guarantees | Is this timeout / retry budget / interval a hard SLA others rely on, or an implementation detail? |
| Ordering | What must happen before what, and what breaks if that order changes? |
| Failure | What happens on partial failure — retried, dropped, or left inconsistent? |
| Compatibility | What must stay stable for older/newer peers, and where is that enforced? |
| Ownership | Which team owns this, and what is the escalation path when it breaks? |

Ask them as **specific, answerable** questions ("Is the 30s node status
interval a hard SLA?"), never open-ended ones ("how does status work?").
Two or three good questions on a substantial concept is normal; zero
usually means the interrogation was skipped rather than that the code was
unambiguous.

### Index files (OKF §6)

- Write `index.md` in the bundle root and in every subdirectory.
- No frontmatter, EXCEPT the bundle root `index.md`, which carries exactly:

  ```yaml
  ---
  okf_version: "0.1"
  ---
  ```

- Body = sections of bulleted links, each entry reusing the concept's
  `description` frontmatter:

  ```markdown
  # Services

  * [Checkout Service](services/checkout.md) - Handles cart-to-order conversion and payment orchestration.

  # Data

  * [data/](data/) - Database tables and event schemas.
  ```

### Log file (OKF §7)

Create `log.md` at the bundle root:

```markdown
# Knowledge Bundle Update Log

## <YYYY-MM-DD>
Commit: `<short-sha>`
* **Initialization**: Generated bundle from commit `<short-sha>` with catalogify. <N> concepts across <dirs>.
```

The `Commit:` line is REQUIRED and machine-checked (validator rule E4) —
it is what the **update** workflow reads to resume incrementally. Always
write it as the first line under the date heading, exactly in that
backtick-quoted form.

## Phase 3 — Validate and report

1. Run the conformance checker:

   ```bash
   catalogify validate "$BUNDLE_DIR" --config "$CONFIG"   # drop --config if none was found
   ```

2. Fix any ERRORs (unparseable frontmatter, missing/empty `type`,
   malformed reserved files). WARNINGs (broken links, missing optional
   fields, unresolved `open_questions` — W8) are acceptable but list them.
3. Report to the user: concept count by type, bundle tree, validation
   result, **how many concepts carry `open_questions`**, and suggested next
   steps:
   - review `architecture/overview.md` first;
   - run the **clarify** workflow to resolve the open questions (this is where
     the highest-value, human-only knowledge gets captured);
   - run the **update** workflow after future code changes.

## Hard rules

- Only `type` is required in frontmatter, but always provide `title` and
  `description` — indexes are useless without them.
- Reserved filenames `index.md` and `log.md` must never be used for
  concepts (§3.1).
- Concept IDs are file paths minus `.md`; use lowercase, hyphenated
  filenames.
- Every path in `source_files` must actually exist in the repo (the
  validator flags dangling entries as W6). Give each concept a unique
  `type` + `title` combination to avoid duplicate-concept warnings (W7).
- Never fabricate facts about the code. If behavior is unclear from the
  source (and git history doesn't settle it), either mark it inline
  ("unverified — inferred from X") **and** add a concrete `open_questions`
  entry so the **clarify** workflow can resolve it — never guess.
- All writes stay inside `BUNDLE_DIR`. Never modify source code.
