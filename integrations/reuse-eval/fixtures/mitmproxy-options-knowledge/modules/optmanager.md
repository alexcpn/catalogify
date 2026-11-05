---
type: Module
title: optmanager (option value engine)
description: OptManager holds typed option values, applies updates transactionally, parses --set and config files, builds argparse flags and notifies subscribers.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/optmanager.py
tags: [options, configuration, cli, python]
source_files:
  - mitmproxy/optmanager.py
timestamp: 2024-07-02T12:07:47+02:00
generated_by: catalogify/0.11.0
relations:
  - {kind: changes_with, target: mitmproxy/tools/main.py, evidence: [0bbb0215, 0c6663d0, 1b134113]}
open_questions:
  - "Is serialize() dropping keys that are not registered an intended guarantee, so that a config file written by one version never carries stale keys, or a side effect of the implementation?"
  - "When an option is deferred from --set and no addon ever declares it, should mitmproxy warn at startup? The code keeps it silently in `deferred`."
  - "Is the rule that a rolled-back partial update re-raises the OptionsError an API promise for addon authors, or only a convenience for the CLI?"
---

# Responsibilities

`OptManager` is the base class of `Options`. It stores one `_Option` per
name (type, default, help, choices, current value), exposes values through
attribute access, and is the only place that writes them. Writes are
transactional: `update_known` wraps assignments in `rollback`, which
deep-copies the option table first, restores it and re-raises when an
`OptionsError` escapes. Two signals are emitted: `changed` (set of updated
names) and `errored` (the exception). Subscribers register with `subscribe`
for named options only.

Input paths: `set(*specs, defer=...)` parses `name=value` strings. Values for
`Sequence[str]` options are collected as lists; `bool` accepts `toggle`,
`true`, `false` or no value. Unknown names are either raised or kept in
`deferred` for an addon that has not loaded yet. `load` and `load_paths`
read YAML config files, with later paths overriding earlier ones and relative
`scripts` entries resolved against the config's directory.

Output paths: `dump_defaults` writes an annotated YAML file for `--options`,
`dump_dicts` returns JSON-serialisable descriptions for the web API, `serialize`
and `save` write a config file while keeping unrelated text, and `make_parser`
adds argparse entries (a `--x`/`--no-x` pair for booleans, `append` for sequences).

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `OptManager` | Base class; holds the option table and the `changed` and `errored` signals. |
| `OptManager.add_option` | Declares an option; emits `changed` so front ends pick it up. |
| `OptManager.update` | Sets options by keyword; raises `KeyError` for unknown names. |
| `OptManager.update_known` | Sets known options and returns the unknown ones; rolls back on error. |
| `OptManager.update_defer` | Sets known options now and stashes unknown ones in `deferred`. |
| `OptManager.set` | Applies `name=value` strings (the `--set` form). |
| `OptManager.process_deferred` | Applies stashed values once their option has been declared. |
| `OptManager.subscribe` | Calls a function when a named option changes. |
| `OptManager.make_parser` | Adds an argparse flag for one option. |
| `OptManager.merge` | Merges a dict, appending to sequence options. |
| `dump_defaults` | Writes the annotated default config (`--options`). |
| `dump_dicts` | Returns option metadata as plain dicts (web API and `options/update`). |
| `parse` | Parses YAML text into a dict, with line-numbered errors. |
| `load` | Loads YAML text into an options object. |
| `load_paths` | Loads several config files in order. |
| `serialize` | Writes a round-trip YAML representation. |
| `save` | Writes a config file in place. |

# Dependencies

- Internal: [options](options.md) subclasses `OptManager`. [cli-tools](cli-tools.md)
  calls `make_parser`, `set`, `update` and `dump_defaults`. [web-ui](web-ui.md)
  calls `dump_dicts` and `update`. [console-options](console-options.md) subscribes
  to `changed`.
- Addon declaration: `mitmproxy/addonmanager.py` calls `add_option` through
  `Loader.add_option` and `process_deferred` after addons load.
- External: `ruamel.yaml` for parsing and writing, `mitmproxy.utils.signals`
  and `mitmproxy.utils.typecheck`.

# Key files

- `mitmproxy/optmanager.py` - `OptManager` (around line 99) and the module-level helpers after it.

# Gotchas

- Sequence options accept several values, but scalar options accept exactly one:
  `_parse_setval` raises when a scalar gets more than one value. Commit `64961232`
  made `Sequence[str]` settable from the command line and deferred config
  (`#4210`, fixes `#3015`), so the deferred store keeps lists for every option.
- Options set in config files or `--set` before their addon has loaded are
  stored in `deferred` and applied later. Commit `e59ba134` introduced this for
  config-file options (`#3162`).
- A failed partial update does not leave half the values changed: the table is
  restored and the error is re-raised. Commit `04f1a444` fixed the re-raise (`#2174`).
- Subscribers must wait for the option to exist. `subscribe` raises for an
  unknown name. Commit `bd7069a9` (`#3147`) fixed the console missing options
  added later by making `add_option` send `changed`.

# Citations

- `64961232` - Make it possible to set sequence options (#4210).
- `e59ba134` - Use deferral mechanism for cfg file options (#3162).
- `04f1a444` - options: reraise when there's an error with a partial update (#2174).
- `bd7069a9` - Adjust options when changed (#3147).
