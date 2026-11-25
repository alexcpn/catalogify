"""Files `catalogify meta init` writes into a new meta repo.

Kept as strings so they ship with the scripts (package data is `*.py` here)
and stay out of the skill assets that agents install.
"""

REPOS_YAML = """\
# The repos this meta bundle indexes. Hand-written: catalogify never writes
# this file after `meta init`. After editing it, run `catalogify meta sync`
# (sync applies grouping and contracts while it reads each child bundle),
# then `catalogify meta derive`.
version: 1

repos:
  example:
    title: Example service repo
    remote: https://github.com/example-org/example.git
    bundle_path: knowledge          # where the catalogify bundle lives; null = no bundle
    # local: ../example             # a checkout to sync from when no name=dir is given
    # url: https://forge.example/example/-/blob/{ref}/knowledge/{path}
    #                               # link template; default <remote>/blob/{ref}/<bundle_path>/{path}
    group_by: directory             # directory | catalog:<page.md> | frontmatter:<key>
    # catalog_skip: [Overview]      # catalog mode: headings that are not domains
    # unit_types: [Service, Module, Component]   # directory mode: what counts as a unit

# Interface styles that cross repo lines. A unit in one repo that uses an
# identifier a unit in another repo provides becomes a cross-repo edge.
# contracts:
#   grpc:
#     title: gRPC services
#     provides:
#       section: Interfaces         # first table column of this section (default)
#       # pattern: 'service (\\w+)'  # or a regex; group 1 is the identifier
#     # consumes:
#     #   sections: [Dependencies]  # default: the whole page except the provides section
#     # min_length: 6
"""

AGENTS_MD = """\
# Working in this meta repo

This repo indexes several other repos. It holds a summary of each repo's
catalogify bundle (`bundles/<name>/summary.md`), never the bundle itself, and
pages derived from those summaries. Use it to find which repos and domains a
change touches before you open any code.

## Two tiers

1. **Route here.** Search `components/` for the domains a feature touches and
   `edges/` for the contracts between repos. Each component page lists its
   units, the edges to other domains in the same repo, and the cross-repo
   edges. Follow `architecture/spec-splitting.md` to split the feature into
   one spec per repo.
2. **Work there.** Each unit links to its page in the child repo at the commit
   that was summarised. Continue inside that repo, with its own bundle.

## Rules

- Don't edit pages that carry `generated_by: catalogify-meta/...`, except their
  `# Notes` section and `open_questions`. `catalogify meta derive` rebuilds
  the rest. Remove the marker to take a page over by hand.
- Never copy a child bundle into `bundles/`. `meta sync` writes the summary
  and nothing else, and `catalogify verify` fails if anything else is there.
- Link child pages by their forge permalink. Cite only this repo's commits in
  backticks, because a child repo's commit doesn't exist here and verify
  reports it.
- A contract match is evidence that a caller exists, not proof. Check the
  consumer's code before you rely on it.
- Don't copy secrets into hand-written pages.
"""

OKF_CONFIG = """\
okf:
  exclude:
    - "bundles/**"
    - "workspace/**"
"""

GITIGNORE = """\
workspace/
"""

README_MD = """\
# Meta bundle

One routing index over several repos' catalogify bundles. Start at
`index.md`. Agents working here should read `AGENTS.md` first.

Refresh it with:

```bash
catalogify meta sync      # summarise each child bundle (edit repos.yaml first)
catalogify meta derive    # rebuild components/, edges/ and the indexes
catalogify validate . --config .okf-config.yml
catalogify verify .
```
"""

INDEX_MD = """\
---
okf_version: "0.1"
---

<!-- generated_by: catalogify-meta/{version} -->
# Meta bundle

## Directories

- [architecture/](architecture/index.md): 1 concept
"""

ARCH_INDEX_MD = """\
<!-- generated_by: catalogify-meta/{version} -->
# Architecture

## Concepts

- [Splitting a feature spec across repos](spec-splitting.md): How to turn one feature into a spec per repo using this meta bundle.
"""

SPEC_SPLITTING_MD = """\
---
type: Playbook
title: Splitting a feature spec across repos
description: How to turn one feature into a spec per repo using this meta bundle.
tags: [meta, planning]
---

# Steps

1. Write the feature down in plain terms: what changes for whom.
2. Search `components/` for the domains it touches. Note each domain's repo.
3. For each domain, read its `# Cross-repo edges`. Every contract the feature
   changes adds the consumer domains on that contract page to the list.
4. Read `architecture/overview.md` if it exists, for the contracts that name
   matching can't find (shared schemas, queues, config pipelines, deployment
   repos).
5. Write one spec per repo. Each spec names the units it changes (link the
   unit pages) and the contracts it changes or depends on.
6. For each changed contract, check the `open_questions` and `# Notes` on its
   page: who approves the change, and how compatibility is confirmed.
7. Continue in each repo with that repo's own bundle.

# Notes

Edit this playbook to fit how your teams plan. `meta derive` never touches it.
"""

LOG_MD = """\
# Meta Bundle Update Log

## {date}
Commit: `{commit}`
* **Initialization**: scaffold created by catalogify meta init.
"""

# path -> template, in the order `meta init` reports them.
SCAFFOLD = {
    "repos.yaml": REPOS_YAML,
    "AGENTS.md": AGENTS_MD,
    ".okf-config.yml": OKF_CONFIG,
    ".gitignore": GITIGNORE,
    "README.md": README_MD,
    "log.md": LOG_MD,
    "index.md": INDEX_MD,
    "architecture/index.md": ARCH_INDEX_MD,
    "architecture/spec-splitting.md": SPEC_SPLITTING_MD,
}
