# Meta — one routing index over several repos

You are building or refreshing a **meta repo**: a separate git repo that
indexes several repos' catalogify bundles. It lists each repo's units
(services, modules, components) and the edges between them, both inside a
repo and across repos. A planning agent reads it to route a feature to the
few repos it touches (tier 1), then continues inside each repo with that
repo's own bundle (tier 2).

The meta repo never holds a child bundle. For each repo, `catalogify meta
sync` reads the bundle where it is and writes one summary,
`bundles/<name>/summary.md`: its units, the edges inside the repo, and the
identifiers each unit provides and uses. Derived pages link to child pages
as forge permalinks at the commit that was summarised.

Each child repo needs a catalogify bundle first, made with the generate
workflow in that repo. Building child bundles is not part of this workflow.

## Steps

### 1. Scaffold

Run `catalogify meta init <dir>` in an empty directory, then `git init` there
if it isn't a repo yet. Init never overwrites a file, so it is safe to rerun.
It writes `repos.yaml`, `AGENTS.md`, `.okf-config.yml`, `.gitignore`,
`README.md`, `log.md`, the indexes and `architecture/spec-splitting.md`.

### 2. Register the repos with the user

Fill in `repos.yaml` together with the user. Don't guess remotes or paths.
For each repo you need:

- `title`, `remote` and `bundle_path` (where its bundle lives, or `null` for
  a repo with no bundle, such as a vendor system; derive gives it a stub page
  under `components/external/` to write by hand);
- optionally `local`, a checkout to sync from, and `url` when the forge
  doesn't serve `<remote>/blob/<ref>/<path>`;
- `group_by`, the way the repo splits into domains. Open the child bundle's
  `index.md` and pick with the user:
  - `catalog:<page.md>` when the bundle has a page whose headings already
    name the domains (use `catalog_skip` for headings like "Overview");
  - `frontmatter:<key>` when concepts carry a domain-like frontmatter key;
  - `directory` (the default) when the top-level directories are the domains.
    `unit_types` limits which concept types count.

Then the **contracts**: the interface styles that cross repo lines, such as
gRPC services, REST APIs or event topics. Ask the user which ones matter. For
each, `provides.section` names the section whose first table column lists
what a unit provides (default `Interfaces`), or `provides.pattern` gives a
regex whose group 1 is the identifier. Set `consumes.sections` only if the
whole page is too broad a place to look for uses.

### 3. Sync the summaries

Run `catalogify meta sync` (repos with `local`), or
`catalogify meta sync <name>=<bundle_dir> ...`. Check each output line:

- `ref unknown` means the child `log.md` has no `Commit:` line. The links
  won't be permalinks and verify will report it. Fix the child bundle.
- `relation targets not covered by a unit` and tie warnings mean a child's
  `relations` point at files no unit claims. The edge is dropped, not guessed.
- `cannot be matched; use provides.pattern` names identifiers that need a
  pattern.

Never copy child bundle files into `bundles/`. Sync removes them, and
`catalogify verify` fails on them.

### 4. Derive

Run `catalogify meta derive`. It rebuilds `components/<repo>/<domain>.md`,
`edges/<contract>/<repo>-<domain>.md` and the indexes, and prints one summary
line. Warnings to act on:

- `summary built with an older repos.yaml; resync`: you changed grouping or
  a contract, so run sync again.
- `has no summary`: that repo hasn't been synced.
- a domain slug collision (exit 1): two domain names in one repo map to the
  same file. Rename one in the child's catalog or frontmatter.

If the summary line says **zero contract pages** where you expected some,
open two child pages that should match (a provider and a consumer) and fix
`repos.yaml`: the provides section name, a `provides.pattern`, or
`min_length`. Don't hand-edit derived pages to add edges. Derive overwrites
everything except `# Notes` and `open_questions`.

### 5. Write what derive can't see

Derive only finds contracts that are identifiers named on both sides. Write
these by hand, with the user:

- `architecture/overview.md`: the estate in a page. Which repos exist, what
  each is for, and how a request crosses them.
- A page under `edges/` for each contract that isn't a shared name: shared
  schemas, queues and topics, config pipelines, and deployment repos that
  sync manifests into others. Give each one `type: Interface`, the provider,
  every consumer, and links to their component pages.

Hand-written pages carry no `generated_by` marker, so derive never touches
them, and they still appear in the indexes. Link child pages by permalink.
In backticks, cite only commits of the meta repo: a child repo's commit
doesn't exist here, and verify reports it as V1.

### 6. Clarify

Contract pages carry questions such as
`[contract-approval:grpc/dc-sessions] Who approves a change to this
contract...`. Ask the user. Record each answer under the page's `# Notes`
section, with a sentinel naming the question ID:

```markdown
# Notes

<!-- clarified: contract-approval:grpc/dc-sessions -->
The DC platform team approves; consumers are checked by the contract tests in edge CI.
```

Then remove the answered question from `open_questions`. Derive keeps
`# Notes` and the remaining questions on every rebuild, adds questions it
newly detects, and never asks again about an ID that has a `clarified`
sentinel.

### 7. Log, validate and verify

- Prepend a dated block to `log.md`, newest first, with
  ``Commit: `<meta repo HEAD>` `` and one line on what changed.
- Run `catalogify validate . --config .okf-config.yml`. The config excludes
  `bundles/**`, so the summaries aren't checked as concepts.
- Commit, then run `catalogify verify .`. On a meta repo it adds **V15**
  (a derived page cites something other than a repo summary, or links a
  unit the summary doesn't list, or links at another commit) and **V16**
  (the mount record and a summary disagree on the commit, the commit is
  unknown, or files other than `summary.md` sit under `bundles/<name>/`).
  Fix every FINDING.

## Refreshing in CI

Sync reads local paths only and never fetches. In CI, clone just each child
bundle, then sync and derive:

```bash
git clone --depth 1 --filter=blob:none --sparse "$REMOTE" "workspace/$NAME"
git -C "workspace/$NAME" sparse-checkout set "$BUNDLE_PATH"
catalogify meta sync "$NAME=workspace/$NAME/$BUNDLE_PATH"
catalogify meta derive
git diff --exit-code    # optional: fail when the meta repo is out of date
```

`workspace/` is gitignored. A shallow clone is fine here: the commit comes
from the child bundle's own `log.md`, not from history.

## Rules

- A contract match is evidence that a caller exists, not proof. Every
  contract page says so. Keep that caveat when you quote it.
- Edges inside a repo come only from what the child bundle declares (its
  typed `relations` and `# Dependencies` links). If a repo shows none, its
  bundle doesn't record them. Improve the child bundle rather than adding
  edges here.
- Don't copy secrets into hand-written pages.
