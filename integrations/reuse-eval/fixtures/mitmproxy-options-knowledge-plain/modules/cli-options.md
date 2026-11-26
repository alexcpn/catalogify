---
type: Module
title: CLI options (command-line exposure)
description: mitmproxy/tools/cmdline.py builds each front end's argparse parser from the option declarations, and tools/main.py feeds the parsed namespace back into the option store.
tags: [cli, argparse, options, mitmproxy, mitmdump, mitmweb]
timestamp: 2025-04-29T11:26:08+02:00
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/tools/cmdline.py
generated_by: catalogify/0.10.1
source_files:
  - mitmproxy/tools/cmdline.py
  - mitmproxy/tools/main.py
open_questions:
  - "process_options applies -q/--options/--commands first and then -v, so -v overrides the quiet log level that --options sets. Is that intended for 'mitmproxy --options -v'?"
---

# Responsibilities

`cmdline.py` defines one parser per front end: `mitmproxy`, `mitmdump` and
`mitmweb`. Each calls `common_options`, which registers the shared flags
(`--set`, `--options`, `--commands`, `--version`, `-q`, `-v`) and then asks
`OptManager.make_parser` for a flag per option it wants to expose. `main.py`
runs the chosen parser, calls `process_options`, and then drives the master's
run loop, installing SIGINT and SIGTERM handlers. The flow is: parse args,
copy the non-`None` values into the option store, and start.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `common_options(parser, opts)` | Shared flags, plus `--mode`, `--showhost`, `--show-ignored-hosts`, `--rfile`, `--scripts`, `--save-stream-file`, and similar. |
| `mitmproxy(opts)`, `mitmdump(opts)`, `mitmweb(opts)` | Build the parser for each front end. `mitmweb` adds `--web-open-browser`, `--web-port` and `--web-host`. |
| `process_options(parser, opts, args)` | Apply `args` to `opts`; `--version` exits. |
| `run(...)` | Run the master loop with signal handling. |
| `mitmproxy()`, `mitmdump()`, `mitmweb()` | Console entry points. |

# Dependencies

- Flags come from [OptManager](optmanager.md) `make_parser`, for declarations in [Options](options.md) and addon-declared options such as the `web_*` set in [Web UI options](web-ui-options.md).
- `process_options` writes through `OptManager.update`, so CLI values follow the same typing and rollback rules.
- Uses `argparse` from the standard library.

# Gotchas

- **Only `None` values reach the store.** `process_options` keeps only namespace entries that are not `None`, so an argparse default does not clobber a value set in the config file.
- **Options that exist on only one front end.** Flags are added per parser: `--web-port` appears only in `mitmweb`. An option whose addon is not loaded has no flag at all, which is why `mitmdump --options` is the reliable listing.
- **`--set` has bare-name semantics.** Per the help text, a bare boolean name means true, a bare string or integer name means None where allowed, and a bare sequence name empties the list. `--set` is the only way to reach options that have no dedicated flag.
- **Mutually exclusive bool flags.** Each boolean gets a `--X` / `--no-X` pair in a mutually exclusive group, so one command cannot both enable and disable the same option.
- **`--show-ignored-hosts` is a flag in `common_options`.** It sits next to the ignore-host flags and is the switch for showing raw streams of ignored hosts (`a44191a9`, closes `#6720`).

# Citations

- `a44191a9` — Add `--show-ignored-hosts` (#6720).
- `64961232` — Make it possible to set sequence options (#4210, closes #3015).
- `e59ba134` — Use deferral mechanism for cfg file options (#3162).
