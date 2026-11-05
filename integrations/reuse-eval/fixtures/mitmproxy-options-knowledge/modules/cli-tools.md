---
type: Module
title: cli-tools (command-line parsers and entry points)
description: Builds the argparse parsers for mitmproxy, mitmdump and mitmweb from the option registry, then applies --set, config files and flag values in a fixed order.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/tools/cmdline.py
tags: [cli, options, argparse, python]
source_files:
  - mitmproxy/tools/cmdline.py
  - mitmproxy/tools/main.py
timestamp: 2025-04-29T11:26:08+02:00
generated_by: catalogify/0.11.0
relations:
  - {kind: changes_with, target: mitmproxy/options.py, evidence: [040238e2, 07a8c498, 14d8c912]}
open_questions:
  - "Is the order in run() (master constructed before the parser is built, and config files loaded after --set) a deliberate guarantee for addon-declared options, or incidental?"
  - "Should make_parser() warn when a flag is requested for an option that no loaded addon declares? It currently skips the flag silently."
---

# Responsibilities

`cmdline.py` contains only parser construction. `common_options` adds the
flags shared by every tool (`--version`, `--options`, `--commands`, `--set`,
`-q`, `-v`) and calls `make_parser` for the proxy, SSL, replay and
modification options, grouped into argparse argument groups. `mitmproxy()`,
`mitmdump()` and `mitmweb()` each build one parser on top of it: mitmdump
adds the positional filter arguments, mitmweb adds `web_open_browser`,
`web_port` and `web_host`.

`main.py` is the runtime. `run()` creates `Options`, then the master (which
loads addons and so declares their options), then the parser, parses
`argv`, applies `--set` with `defer=True`, loads `config.yaml` and
`config.yml` from the configuration directory, and finally runs
`process_options`. `process_options` copies every non-`None` argument whose
name is a known option into the registry, and sets terminal log level and
flow detail for `-q` and `-v`. `--options` prints defaults and exits;
`--commands` dumps the command list and exits.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `common_options` | Adds the flags shared by all three tools and the proxy option groups. |
| `mitmproxy` | Builds the parser for the console tool. |
| `mitmdump` | Builds the parser for the dump tool; adds the filter arguments. |
| `mitmweb` | Builds the parser for the web tool; adds `web_*` flags. |
| `process_options` | Copies parsed arguments into the option registry and handles `-q`, `-v`, `--version`. |
| `run` | Generic entry point: builds options and master, parses arguments, runs the event loop. |
| `mitmproxy` (main) | Console entry point. |
| `mitmdump` (main) | Dump entry point. |
| `mitmweb` (main) | Web entry point. |

Note: `cmdline.mitmproxy` and `main.mitmproxy` share a name in different modules.

# Dependencies

- Internal: [optmanager](optmanager.md) (`make_parser`, `set`, `load_paths`,
  `dump_defaults`), [options](options.md) (the registry), and the master classes
  in `mitmproxy/tools/console/` and `mitmproxy/tools/web/` (see [web-ui](web-ui.md)).
- External: `argparse` and the standard library.

# Key files

- `mitmproxy/tools/cmdline.py` - the parser definitions.
- `mitmproxy/tools/main.py` - `run()` and `process_options()`; read `run()` for ordering.

# Gotchas

- `--set` and config values are applied before flag values, but flag values
  override them because `process_options` runs last. Unknown names are deferred
  rather than rejected, so a typo in `--set` only surfaces when no addon claims it.
- Sequence options passed on the command line are appended, not replaced. Commit
  `64961232` changed the parsing of sequence options (`#4210`) and touched both
  `mitmproxy/optmanager.py` and `mitmproxy/tools/cmdline.py`.

# Citations

- `64961232` - Make it possible to set sequence options (#4210).
- `a44191a9` - Add `--show-ignored-hosts` (#6720); touched `mitmproxy/tools/cmdline.py` as a flag example.
