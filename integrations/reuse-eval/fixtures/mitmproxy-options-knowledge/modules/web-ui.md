---
type: Module
title: web-ui (mitmweb master, options API and web options)
description: The mitmweb master pushes option changes to the browser, exposes GET and PUT /options, declares the web_* options and handles web authentication.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/tools/web/master.py
tags: [web, mitmweb, options, api, python]
source_files:
  - mitmproxy/tools/web/master.py
  - mitmproxy/tools/web/app.py
  - mitmproxy/tools/web/webaddons.py
timestamp: 2025-08-19T23:04:34+02:00
generated_by: catalogify/0.11.0
open_questions:
  - "Is /options/save intentionally a no-op? Its handler is commented out and returns without writing; should it persist, or is the web UI meant to be session-only?"
  - "Should web_password be accepted as an argon2 hash only, or both forms as the code allows? Which is the supported contract?"
---

# Responsibilities

`WebMaster` (`master.py`) subclasses the base master and connects
`options.changed` to `_sig_options_update`, which broadcasts an
`options/update` message with `dump_dicts` for the changed names. When it
starts, it listens on `web_host` and `web_port`, and on bind failure it names the
conflicting address and suggests another `web_port`.

`app.py` is the Tornado application. Its `Options` handler answers `GET
/options` (and `/options.json`) with the option table and `PUT` updates the
registry, turning any error into a 400. `SaveOptions` is mounted at
`/options/save` but does nothing. The rest of the application serves flows,
commands, events and state; see the routes table near the end of the file.

`webaddons.py` declares the web options (`web_open_browser`, `web_debug`,
`web_port` default 8081, `web_host` default 127.0.0.1) and the `WebAuth`
addon. `WebAuth` takes `web_password`, accepts an argon2 hash when the value
starts with `$`, and otherwise generates a random token when none is set.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `WebMaster` | The mitmweb master; wires options and proxy state to the web clients. |
| `WebAddon` | Declares `web_open_browser`, `web_debug`, `web_port`, `web_host`. |
| `WebAuth` | Web authentication; computes the URL and token. |
| `open_browser` | Opens the UI in a browser if `web_open_browser` is set. |
| `Options` (app) | `GET` and `PUT` on `/options`. |
| `SaveOptions` (app) | `POST /options/save`; currently a no-op. |
| `Application` (app) | The Tornado application with the route table. |
| `ClientConnection` (app) | WebSocket client that receives `options/update` and other broadcasts. |

# Dependencies

- Internal: [optmanager](optmanager.md) (`dump_dicts`, `update`, `changed`),
  [options](options.md), [cli-tools](cli-tools.md) (`mitmweb` flags).
- Internal: [web-gen](web-gen.md) generates the TypeScript that the browser
  uses for the same option shapes.
- External: `tornado`, `argon2` (optional, for hashed passwords).

# Key files

- `mitmproxy/tools/web/master.py` - `_sig_options_update` and `running`.
- `mitmproxy/tools/web/app.py` - `Options` handler and the route table (`/options`, `/options/save`).
- `mitmproxy/tools/web/webaddons.py` - the `web_*` declarations and `WebAuth`.

# Gotchas

- No history-backed invariant was found for these files beyond the generated
  front-end types. Commit `460789b7` (`#6910`) touched `app.py`, but its
  subject concerns generated JS, so it is cited only for that. The open
  questions above are the place to record what the API promises.

# Citations

- `460789b7` - Autofix generated JS files and do not patch them in tests (#6910); touched `mitmproxy/tools/web/app.py`.
