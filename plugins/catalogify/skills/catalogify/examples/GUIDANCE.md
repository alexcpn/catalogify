# Guidance for this knowledge bundle

<!-- Copy to the root of your bundle directory (knowledge/GUIDANCE.md by
default) and rewrite every section for your team. The agent reads it before
each generate, update and clarify run and never edits it. Delete what you
don't need. Plain markdown, no frontmatter. -->

## Audience

On-call engineers and coding agents who are new to a service. Assume they
know Go and Kubernetes. Do not assume they know our billing domain.

## Vocabulary

- Say **tenant**, not customer or account. A tenant owns one or more workspaces.
- **Ledger** means the append-only `ledger_entries` table, never the UI page.
- "Region" is a deployment region (`eu-1`, `us-2`), not a geographic area.

## Coverage

- Cover everything under `services/` and `pkg/`.
- Skip `tools/migrate-v1/`: one-off code, kept only for audit.
- `internal/gen/` is generated. Mention it in the overview; no concepts for it.

## Layout and types

- Add a `jobs/` directory for scheduled jobs, with type `Scheduled Job`.
- Put Kafka topics under `apis/` with type `Event Stream`.

## Sections per type

- Every `Service` has a `# Configuration` section: the environment variables
  it reads and what each one changes (names and shape only, no values).
- Every `Service` has a `# Ownership` section naming the owning team. If the
  code doesn't say, raise it as an open question.
- Every `Scheduled Job` states its schedule and what happens on a missed run.

## How to describe things

- Describe every HTTP handler by the route it serves, not the function name.
- Feature flags: list them per service in one table, with their default.

## Checks to run

- Grep for `// INVARIANT:` comments and list each one under `# Gotchas` of
  the concept that owns the file.

## Related bundles

- Platform services are documented in the `platform-kb` repository. Link to
  it rather than describing the platform here.

## Don't

- Don't document test helpers under `testutil/`.
- Don't copy SQL migrations into concepts; link the migration file.
