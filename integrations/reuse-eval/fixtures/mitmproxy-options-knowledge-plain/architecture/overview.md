---
type: Reference
title: mitmproxy options and proxy core — overview
description: Start here. How mitmproxy declares, manages, exposes and consumes its options, and how the proxy server uses them.
tags: [overview, options, proxy, architecture]
timestamp: 2025-08-19T23:04:34+02:00
generated_by: catalogify/0.10.1
source_files:
  - mitmproxy/options.py
  - mitmproxy/optmanager.py
  - mitmproxy/tools/cmdline.py
  - mitmproxy/tools/main.py
  - mitmproxy/tools/web/master.py
  - mitmproxy/tools/web/webaddons.py
  - mitmproxy/tools/web/app.py
  - mitmproxy/proxy/server.py
  - mitmproxy/proxy/context.py
  - mitmproxy/proxy/layer.py
  - mitmproxy/proxy/mode_specs.py
  - mitmproxy/proxy/mode_servers.py
  - web/gen/all
---

# Purpose

Everything mitmproxy can be configured with is an **option**. Options are
declared once, held in one object, and then reached from three user-facing
surfaces (command line, web UI, console) and from the proxy core. This bundle
covers that path end to end. It is scoped to `mitmproxy/options.py`,
`mitmproxy/optmanager.py`, `mitmproxy/proxy/`, `mitmproxy/tools/` and `web/gen/`.

# The four roles

| Role | Where | Concept |
| --- | --- | --- |
| Declare | `mitmproxy/options.py`, plus `loader.add_option` calls in addons | [Options](../modules/options.md) |
| Manage (type, parse, rollback, subscribe, save/load) | `mitmproxy/optmanager.py` | [OptManager](../modules/optmanager.md) |
| Expose on the CLI | `mitmproxy/tools/cmdline.py`, `mitmproxy/tools/main.py` | [CLI options](../modules/cli-options.md) |
| Expose in the web UI | `mitmproxy/tools/web/` | [Web UI options](../modules/web-ui-options.md) |
| Generate typed web-side artefacts | `web/gen/` | [Web code generators](../modules/web-gen.md) |
| Consume: listen on sockets, pick modes, run connections | `mitmproxy/proxy/` | [Proxy modes](../modules/proxy-modes.md), [Proxy server](../modules/proxy-server.md) |

# How an option travels

1. `Options()` (in `mitmproxy/options.py`) calls `add_option` for its core set.
   Addons then add their own through `loader.add_option` during load; the
   addon loader flushes any deferred values after each addon loads.
2. The CLI builds argparse flags from those declarations with
   `OptManager.make_parser`, and `process_options` pushes the parsed values
   back with `opts.update`.
3. The web UI reads `GET /options` (dumped with `dump_dicts`) and writes with
   `PUT /options`, which calls the same `update`. Changes are broadcast to
   browsers from `WebMaster._sig_options_update`.
4. A change emits `options.changed`. Subscribers such as the proxy server
   addon react, and proxy layers read values directly from
   `Context.options`.
5. If a subscriber raises `OptionsError`, the whole update is rolled back.

# Start reading here

- Adding an option: [Options](../modules/options.md), then the typing rules in [OptManager](../modules/optmanager.md).
- Why a CLI flag exists or does not: [CLI options](../modules/cli-options.md).
- Why a web setting behaves as it does (auth, port, cookies): [Web UI options](../modules/web-ui-options.md).
- Why the TypeScript option types look the way they do: [Web code generators](../modules/web-gen.md).
- Why a proxy mode listens where it does: [Proxy modes](../modules/proxy-modes.md).
- How a connection is driven once accepted: [Proxy server](../modules/proxy-server.md).

# Boundaries of this bundle

- The option *consumer* `mitmproxy/addons/proxyserver.py` sits outside the
  scope but is the component that reconciles proxy modes when `mode` or
  `server` change. It is described only as seen from the proxy modes concept.
- Many proxy options (`keep_host_header`, `connection_strategy`,
  `store_streamed_bodies`, `validate_inbound_headers`) are declared by addons,
  not by `mitmproxy/options.py`. See the open question in the Options concept.
- `mitmproxy/proxy/layers/` and the console UI (`mitmproxy/tools/console/`) are
  not covered by their own concept; only where they touch options.
- `web/gen/tflow_js.py` was not analysed.

See also [the knowledge index](../index.md).
