# catalogify for Cursor

Builds a `knowledge/` directory for the repository you have open: short,
cross-linked markdown concepts (Open Knowledge Format v0.1) that describe its
services, modules, APIs, data models and operations, and why they are the way
they are. The "why" comes from git history, and every commit or file a concept
cites is checked against the repo before the bundle is done.

This plugin is the catalogify agent skill packaged for Cursor. It is built from
the [catalogify](https://github.com/alexcpn/catalogify) repository and holds
the same instructions that `catalogify install` copies.

## Requirements

The skill drives the `catalogify` command-line tool, which collects the facts
the agent writes from. You need one of:

- [uv](https://docs.astral.sh/uv/). The skill then runs the tool with
  `uvx catalogify@<version>`, and nothing else has to be installed.
- catalogify itself, at the plugin's version: `uv tool install catalogify` or
  `pip install catalogify`. An installed CLI of a different version is not
  used; the skill falls back to uv instead.

Also Python 3.9+ and `bash` (on Windows, the one that ships with Git for
Windows). git is optional but history mining and incremental updates need it.

## Usage

In Agent chat, in the repository you want to document:

```text
Use catalogify to generate a knowledge catalog for this repo.
Use catalogify to clarify the open questions in knowledge/.
Use catalogify to validate knowledge/ and verify its claims against the repo.
```

After code changes, ask it to update the catalog. Add `detail: detailed` to a
generate or update prompt for deeper concepts.

Configuration (`okf-config.yml`), `GUIDANCE.md` for steering a bundle, and the
full command reference are documented in the
[catalogify README](https://github.com/alexcpn/catalogify#readme).

## Local install

To try a checkout of this plugin without the marketplace:

```bash
ln -s /path/to/catalogify/plugins/catalogify ~/.cursor/plugins/local/catalogify
```

Then reload Cursor.

## License

MIT
