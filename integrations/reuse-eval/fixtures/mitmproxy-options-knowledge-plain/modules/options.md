---
type: Module
title: Options (core option declarations)
description: mitmproxy/options.py declares the core Options object — 28 options with types, defaults and help text that every other surface reads.
tags: [options, configuration, declarations]
timestamp: 2025-04-21T14:56:58+02:00
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/options.py
generated_by: catalogify/0.10.1
source_files:
  - mitmproxy/options.py
open_questions:
  - "Is mitmproxy/options.py meant to be the complete public option surface, or only the core subset? The proxy reads keep_host_header, connection_strategy, store_streamed_bodies and validate_inbound_headers, but they are declared by mitmproxy/addons/proxyserver.py, not here. Which list should users treat as authoritative?"
  - "The help text of cert_passphrase says 'provided in the --cert option', but the CLI flag is --certs. Is the help text stale and should it be corrected?"
---

# Responsibilities

`Options` is a subclass of `optmanager.OptManager` whose `__init__` calls
`add_option` once per core option (28 at this commit) and then `self.update(**kwargs)`
to apply constructor arguments. It holds no logic of its own. Its module
constants are `CONF_DIR` (`~/.mitmproxy`), `CONF_BASENAME`,
`CONTENT_VIEW_LINES_CUTOFF` (512) and `KEY_SIZE` (2048). Each declaration
fixes a name, a type, a default and a help string, and those four things are
what the CLI, the web UI and the console are generated from.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `Options(**kwargs)` | Declares the core options and applies `kwargs` as initial values. |
| `CONF_DIR`, `CONF_BASENAME` | Default configuration directory and file base name. |
| `CONTENT_VIEW_LINES_CUTOFF`, `KEY_SIZE` | Defaults used by `content_view_lines_cutoff` and `key_size`. |

Option names declared here (grouped): **server and display** `server`,
`showhost`, `show_ignored_hosts`; **certificates** `confdir`, `certs`,
`cert_passphrase`, `client_certs`, `add_upstream_certs_to_client_chain`,
`upstream_cert`, `key_size`, `ssl_insecure`, `ssl_verify_upstream_trusted_confdir`,
`ssl_verify_upstream_trusted_ca`; **listening and routing** `listen_host`,
`listen_port`, `mode`, `ignore_hosts`, `allow_hosts`, `tcp_hosts`, `udp_hosts`;
**protocols** `http2`, `http2_ping_keepalive`, `http3`,
`http_connect_send_host_header`, `websocket`, `rawtcp`; **display and
tooling** `content_view_lines_cutoff`, `protobuf_definitions`.

# Dependencies

- Builds on [OptManager](optmanager.md) for declaration, typing and update.
- Read by the CLI in [CLI options](cli-options.md) (every core option gets a flag through `make_parser`).
- Read by the web UI in [Web UI options](web-ui-options.md) and turned into TypeScript types by [Web code generators](web-gen.md) (`options_js.py` iterates `WebMaster(Options()).options`).
- Read by the proxy at runtime, from the option store rather than by import: `mode`, `listen_host` and `listen_port` in [Proxy modes](proxy-modes.md); `http2_ping_keepalive`, `http3` and `http_connect_send_host_header` in [Proxy server](proxy-server.md).
- External packages: none beyond the standard typing module.

# Gotchas

- **Booleans get a `--X` / `--no-X` pair.** `make_parser` creates a mutually exclusive pair for every boolean, so a default-true option such as `websocket` is turned off with `--no-websocket`. Sequence-typed options such as `mode`, `certs` and `ignore_hosts` accept repeated flags.
- **Connect Host header default.** `http_connect_send_host_header` defaults to `True`. It was added with the commit that fixes `#7019` (`71d7b3d6`); the commit does not discuss the off case further.
- **Show-ignored-hosts keeps flows in memory.** The option's help says ignored flows are kept in memory, which can greatly increase usage. It exists because `--ignore-hosts '.*'` otherwise hides SNIs from the user (`a44191a9`, closes `#6720`).
- **Secret-bearing options are visible on the command line.** The `cert_passphrase` help warns that passing it on the CLI exposes it in the process list. Prefer the config file. Describe the shape only when documenting secrets.
- **WireGuard is not a separate option.** The WireGuard mode is specified through `mode`, not through a dedicated option here; see [Proxy modes](proxy-modes.md). Its documentation was added in `77ed92d2` (fixes `#5706`).

# Key files

- `mitmproxy/options.py` — the full declaration list; start with `Options.__init__`.

# Citations

- `71d7b3d6` — Include Host header with CONNECT requests (fixes #7019).
- `a44191a9` — Add `--show-ignored-hosts` (#6720).
- `77ed92d2` — add WireGuard docs, fix #5706.
