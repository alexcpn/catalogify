---
type: Module
title: options (core option declarations)
description: The Options class in mitmproxy/options.py declares the core set of mitmproxy options (proxy, TLS, HTTP and display) on top of OptManager.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/options.py
tags: [options, configuration, python]
source_files:
  - mitmproxy/options.py
timestamp: 2025-04-21T14:56:58+02:00
generated_by: catalogify/0.11.0
relations:
  - {kind: changes_with, target: web/src/js/ducks/_options_gen.ts, evidence: [091399f8, a44191a9, 71d7b3d6]}
  - {kind: changes_with, target: mitmproxy/tools/cmdline.py, evidence: [040238e2, 07a8c498, 14d8c912]}
open_questions:
  - "Is the default http2_ping_keepalive of 58 seconds a tuned value for a particular peer or an arbitrary choice that must stay under a common idle timeout?"
  - "Should cert_passphrase be kept on the command line at all, given its help text warns it is visible in the process list?"
  - "Which team owns the core option set, and who is the escalation path when a default change breaks users?"
---

# Responsibilities

Declares the core options in `Options.__init__`, one `add_option` call per
option, and ends by calling `self.update(**kwargs)` so constructor arguments are
applied. It is a declaration file: it holds no behaviour of its own. Behaviour
is in the modules that read the values (the proxy addons, the layers and the
front ends). Constants `CONF_DIR`, `CONF_BASENAME`, `CONTENT_VIEW_LINES_CUTOFF`
and `KEY_SIZE` live at module level.

Options fall into rough groups: general display (`showhost`,
`show_ignored_hosts`), listeners and modes (`server`, `mode`, `listen_host`,
`listen_port`), host filters (`ignore_hosts`, `allow_hosts`, `tcp_hosts`,
`udp_hosts`), protocol switches (`http2`, `http3`, `websocket`, `rawtcp`,
`http_connect_send_host_header`), upstream TLS (`ssl_insecure`,
`ssl_verify_upstream_trusted_ca`, `ssl_verify_upstream_trusted_confdir`,
`upstream_cert`) and certificates (`certs`, `client_certs`, `cert_passphrase`,
`key_size`, `add_upstream_certs_to_client_chain`).

Not every option lives here. Addons register their own through `Loader.add_option`,
for example `validate_inbound_headers` and `connect_addr` in
`mitmproxy/addons/proxyserver.py`, and `web_port`, `web_host` in
`mitmproxy/tools/web/webaddons.py`.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `Options` | The option registry class. Subclass of `OptManager`; constructor takes keyword values. |
| `CONF_DIR` | Default configuration directory, `~/.mitmproxy`. |
| `CONF_BASENAME` | Base name of configuration files, `mitmproxy`. |
| `CONTENT_VIEW_LINES_CUTOFF` | Default content-view line limit (512). |
| `KEY_SIZE` | Default TLS key size for generated certificates (2048 bits). |

# Dependencies

- Internal: imports `mitmproxy.optmanager` for the base class. Option values are
  read by [proxy-modes](proxy-modes.md) (`mode`, `listen_host`, `listen_port`),
  [proxy-layers](proxy-layers.md) (`http2`, `http3`, `ssl_insecure`, `http_connect_send_host_header`),
  [web-ui](web-ui.md) and [console-options](console-options.md).
- Mechanics: [optmanager](optmanager.md) provides the types, validation and CLI wiring.
- External: none beyond the standard library and `mitmproxy.optmanager`.

# Key files

- `mitmproxy/options.py` - the declarations; read the `add_option` calls in order.

# Gotchas

- Every option needs a complete help string. Help text feeds `--options`, the
  web UI and the generated TypeScript types, and a missing one shows up in every
  front end. Commit `395e6415` made this a rule for mitmweb options (`#7563`).
- `show_ignored_hosts` keeps the contents of ignored flows in memory, so enabling it
  costs memory on busy sessions. Commit `a44191a9` added it so that raw TCP/UDP
  streams of ignored hosts can be seen when the MITM part is off (`#6720`).
- Changing an option here usually also changes the generated web types. Commits
  `091399f8`, `a44191a9` and `71d7b3d6` each touched both `mitmproxy/options.py`
  and `web/src/js/ducks/_options_gen.ts`. See [the add-option playbook](../operations/playbooks/add-option.md).

# Citations

- `395e6415` - Ensure that all mitmweb options have help text (#7563).
- `a44191a9` - Add `--show-ignored-hosts` (#6720).
- `71d7b3d6` - Include Host header with CONNECT requests (#7021).
- `091399f8` - Add experimental option for HTTP/3 in transparent mode (#7037).
