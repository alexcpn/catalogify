---
type: Module
title: web-gen (code generators for the web front end)
description: Scripts in web/gen/ that generate the TypeScript option types, state fixtures, flow-table columns and backend constants. CI runs them through web/gen/all.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/web/gen/all
tags: [codegen, web, typescript, options]
source_files:
  - web/gen/all
  - web/gen/options_js.py
  - web/gen/state_js.py
  - web/gen/tflow_js.py
  - web/gen/web_columns.py
  - web/gen/backend_consts.py
timestamp: 2025-05-30T23:21:40+02:00
generated_by: catalogify/0.11.0
open_questions:
  - "Is web/gen/all's run-every-script loop the intended long-term workflow, or should each generator be run alone during development? No repo document says which."
---

# Responsibilities

Each script in `web/gen/` writes one generated file and is run by hand or by
CI. `web/gen/all` runs every `*.py` script in the directory, and stops on the
first failure (`set -euxo pipefail`). CI runs it from the autofix workflow
(`.github/workflows/autofix.yml`, step at line 28), so a change to a generated
file is committed by the bot.

`options_js.py` builds a `WebMaster` from `Options()` and writes
`web/src/js/ducks/_options_gen.ts`. The file has three exports:
`OptionsState` (the type of every option, mapped through `_ts_type`), `Option`
(the union of option names) and `defaultState` (the defaults, with `null`
written as `undefined`). Because it builds a master, it sees options added by
addons too, such as `web_port`. `_ts_type` raises for any Python type it does
not know, so a new option type needs a mapping here first.

`web_columns.py` writes the header and list in `mitmproxy/tools/web/web_columns.py`
from the flow-table component. `state_js.py` builds a fixture for the front-end
tests. `tflow_js.py` and `backend_consts.py` produce the flow and backend
constants.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `make` (options_js) | Async; returns the TypeScript source for the options types and defaults. |
| `_ts_type` (options_js) | Maps a Python option type to a TypeScript type; raises on unknown types. |
| `make` (state_js) | Async; returns the TypeScript state fixture. |
| `extract_columns` (web_columns) | Reads the column list from the flow-table component. |
| `make` (web_columns) | Returns the generated Python module with `AVAILABLE_WEB_COLUMNS`. |
| `make` (tflow_js, backend_consts) | Return the generated TypeScript for flows and backend constants. |

Entry point: `web/gen/all` (runs every generator in order).

# Dependencies

- Internal: [options](options.md) and [optmanager](optmanager.md) (types and
  defaults), [web-ui](web-ui.md) (`WebMaster` and the state the fixture builds).
- Generated outputs (not in this bundle's scope): `web/src/js/ducks/_options_gen.ts`,
  `mitmproxy/tools/web/web_columns.py`, and the test fixtures under `web/src/js/__tests__/`.
- External: none beyond the standard library and the mitmproxy modules above.

# Key files

- `web/gen/all` - the runner.
- `web/gen/options_js.py` - the option type generator.

# Gotchas

- Generated files must be regenerated, not patched by hand. Commit `460789b7`
  moved the generators into `web/gen/`, made the autofix workflow run them, and
  stopped tests from patching generated JS (`#6910`).
- Because `options_js.py` instantiates the real master, a broken addon import
  breaks type generation too, not only the web UI.

# Citations

- `460789b7` - Autofix generated JS files and do not patch them in tests (#6910).
