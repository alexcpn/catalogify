---
type: Module
title: OptManager (option management engine)
description: mitmproxy/optmanager.py holds option values, parses and types them, applies all-or-nothing updates with rollback, and loads and saves config files.
tags: [options, optmanager, config, signals]
timestamp: 2024-07-02T12:07:47+02:00
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/optmanager.py
generated_by: catalogify/0.10.1
source_files:
  - mitmproxy/optmanager.py
open_questions:
  - "When a config file sets an option that no addon ever declares, process_deferred keeps the value in self.deferred and nothing reports it. Is that intended, or should the user see a warning?"
---

# Responsibilities

`OptManager` is the base class of `Options`. It owns a dict of `_Option`
records (name, typespec, default, help, choices, current value), and makes them
reachable as attributes. Setting an attribute goes through `update`, so every
write is typed, validated and announced on the `changed` signal. Writes that
fail roll back and emit `errored`. The module also has the text layer:
`parse`/`load`/`load_paths` read YAML-style config, `serialize`/`save` write it
back in place, and `dump_defaults`/`dump_dicts` produce the listings used by
the CLI and the web API.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `OptManager.add_option(name, typespec, default, help, choices)` | Declare an option; sends `changed` so subscribers learn about it. |
| `OptManager.update(**kwargs)` / `update_known` / `update_defer` | Apply typed values. `update` raises on unknown names; `update_defer` stores them for later. |
| `OptManager.set(*specs, defer=False)` | Parse CLI-style `name=value` strings (booleans accept `true`, `false` or `toggle`) and apply. |
| `OptManager.subscribe(func, opts)` | Call `func(options, updated)` when any of `opts` change. Held by weak reference. |
| `OptManager.rollback(updated, reraise)` | Context manager that restores the deep-copied state on `OptionsError`. |
| `OptManager.make_parser(parser, name, metavar, short)` | Add an argparse flag for one option. Used by `tools/cmdline.py`. |
| `OptManager.process_deferred()` | Apply deferred values whose option now exists. Called after each addon loads. |
| `OptManager.reset()`, `default()`, `has_changed()`, `merge()` | Restore defaults, query defaults and change state, and merge dicts. |
| `dump_dicts(opts, keys)` | Return `{name: {type, default, value, help, choices}}` for the web UI. |
| `dump_defaults(opts, out)` | Write the defaults listing for `--options`. |
| `load_paths`, `load`, `save`, `serialize`, `parse` | Config file handling. `save` edits the existing file in place. |

# Dependencies

- Declared options come from [Options](options.md), which subclasses this class.
- Its `make_parser` output is what [CLI options](cli-options.md) exposes.
- `dump_dicts` feeds the `/options` endpoint and the `options/update` broadcast in [Web UI options](web-ui-options.md).
- Relies on `mitmproxy.signals` (`SyncSignal`) for `changed` and `errored`, and on `mitmproxy.exceptions.OptionsError`.
- The addon loader calls `process_deferred` (`mitmproxy/addonmanager.py`).

# Gotchas

- **Rollback is all-or-nothing, and it re-raises.** `update_known` runs inside `rollback(..., reraise=True)`: a subscriber that raises `OptionsError` reverts every value in that call and the error still reaches the caller. Partial updates used to leave state inconsistent; the fix made the error re-raise (`04f1a444`, `#2174`).
- **Subscriber references are weak.** `subscribe` stores `weakref`s, so a subscriber that goes out of scope silently stops receiving updates. Bound methods needed special handling (`4e24c95a`, `#2122`).
- **Sequence options are not scalars.** `_parse_setval` returns the whole list for `Sequence[str]`, and rejects multiple values for other types. Deferred sequence values are kept as lists so `--set` on a sequence option can be applied after the addon that declares it loads (`64961232`, `#4210`, closes `#3015`).
- **Config values can arrive before their option exists.** Config-file loads go through `update_defer`, and the flush happens in `process_deferred` (`e59ba134`, `#3162`). The `changed` signal is also sent on `add_option` so UI state refreshes (`bd7069a9`, `#3147`).
- **Unknown attributes raise.** Assignments on an instance are routed to `update` once `_options` exists, so setting an undeclared name raises `KeyError` rather than creating an attribute. Set-before-init is the only path that creates real attributes.

# Citations

- `04f1a444` — options: reraise when there's an error with a partial update (#2174).
- `4e24c95a` — optmanager: cope with bound methods in .subscribe (#2122).
- `64961232` — Make it possible to set sequence options (#4210, closes #3015).
- `e59ba134` — Use deferral mechanism for cfg file options (#3162).
- `bd7069a9` — Adjust options when changed (#3147).
