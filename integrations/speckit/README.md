# OKF knowledge bundles for Spec Kit

A [Spec Kit](https://github.com/github/spec-kit) extension that turns your AI
coding agent into an Open Knowledge Format (OKF v0.1) enrichment agent. It
builds a `knowledge/` directory of cross-linked markdown concepts from your
source code and git history, and keeps it current.

It is [catalogify](https://github.com/alexcpn/catalogify) packaged as slash
commands: the same scripts and the same workflow, built from the same source.
You do not need to install catalogify to use it.

## Install

```bash
# From a catalogify release
specify extension add okf --from https://github.com/alexcpn/catalogify/releases/download/v<version>/speckit-okf-<version>.zip

# From a catalogify checkout (dev mode)
python3 integrations/speckit/build.py
specify extension add --dev build/speckit-okf
```

## Usage

```bash
/speckit.okf.generate   # 1. bootstrap the bundle from code and git history
/speckit.okf.clarify    # 2. answer what the agent parked instead of guessing
/speckit.okf.update     # 3. after code changes, refresh incrementally
/speckit.okf.validate   # 4. OKF conformance: is the bundle well-formed?
/speckit.okf.verify     # 5. are its claims supported by the repository?
```

Output lands in `knowledge/` (configurable), ready to commit alongside your code.

### Command names by agent

Spec Kit names commands after your agent integration. In **Claude Code** and
**Codex** they are skills with hyphens: `/speckit-okf-generate`,
`/speckit-okf-clarify`, `/speckit-okf-update`, `/speckit-okf-validate` and
`/speckit-okf-verify`. Other agents get the dotted names above.

If a command is missing, check where it was registered. For Claude Code that
is `.claude/skills/speckit-okf-*`; for Codex, `.agents/skills/speckit-okf-*`.
Extensions are registered for the integrations that exist at install time, so
an integration added afterwards does not get them. Reinstall with `--force`:

```bash
specify extension add okf --force --from <the same URL>
```

Restart the agent afterwards so it picks up the new skills.

## Configuration

Copy `okf-config.template.yml` to `.specify/extensions/okf/okf-config.yml` to
change the bundle directory, excludes, type mappings, layout or granularity.
Defaults work without any config.

## For maintainers

Nothing in the installed extension is edited by hand. `build.py` assembles it
from `src/catalogify/_scripts` and `src/catalogify/_skill_assets`; only
`extension.yml`, `commands/verify.md` and this README live here. See the
docstring of `build.py` for how the workflow documents become commands and
what stops a build.
