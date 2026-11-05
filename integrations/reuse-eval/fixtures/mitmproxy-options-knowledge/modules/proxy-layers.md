---
type: Module
title: proxy-layers (mode, TLS and HTTP protocol layers)
description: The protocol layers that the proxy core stacks on each connection. They cover the proxy modes, TLS interception and the HTTP layer that owns request and response handling.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/proxy/layers/__init__.py
tags: [proxy, tls, http, layers, python]
source_files:
  - mitmproxy/proxy/layers/__init__.py
  - mitmproxy/proxy/layers/modes.py
  - mitmproxy/proxy/layers/tls.py
  - mitmproxy/proxy/layers/http/__init__.py
timestamp: 2025-04-07T20:09:53+02:00
generated_by: catalogify/0.11.0
open_questions:
  - "Is the HTTP/2 CONNECT restriction for secure web proxies (commit ef279567) a permanent protocol rule, or a workaround that a future upstream fix would lift?"
---

# Responsibilities

`layers/__init__.py` exports the layer classes that the rest of the proxy
imports. `layers/modes.py` implements how each proxy mode gets its destination:
`HttpProxy` and `HttpUpstreamProxy` for explicit proxying, `ReverseProxy` and
`TransparentProxy` for destinations known up front, `Socks5Proxy` for SOCKS5
(with `Socks5AuthHook` for authentication), all built on `DestinationKnown`.

`layers/tls.py` implements TLS interception. `TLSLayer` is the base, with
`ServerTLSLayer` and `ClientTLSLayer` for the two sides, and `MockTLSLayer` for
tests. Its hooks (`TlsClienthelloHook`, `TlsStartClientHook`,
`TlsEstablishedServerHook` and others) let addons observe or change the
handshake. Helper functions parse the ClientHello for TCP and DTLS.

`layers/http/__init__.py` defines `HttpLayer`, which owns each HTTP
connection, `HttpStream`, which owns each request and response pair, and the
`HTTPMode` enum. `validate_request(mode, request, validate_inbound_headers)`
enforces inbound header validation. The HTTP command and event classes live in
the same package, and the HTTP/1, HTTP/2 and HTTP/3 implementations are in the
`_http*` modules next to it.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `HttpProxy`, `HttpUpstreamProxy` | Explicit HTTP proxy modes. |
| `ReverseProxy`, `TransparentProxy`, `Socks5Proxy` | Modes whose destination is known before the request. |
| `DestinationKnown` | Shared base for modes with a known destination. |
| `TLSLayer`, `ServerTLSLayer`, `ClientTLSLayer`, `MockTLSLayer` | TLS layers. |
| `TlsClienthelloHook`, `TlsStartClientHook`, `TlsStartServerHook`, `TlsEstablishedClientHook`, `TlsEstablishedServerHook`, `TlsFailedClientHook`, `TlsFailedServerHook` | TLS hooks addons can observe. |
| `parse_client_hello`, `get_client_hello` | Parse the TLS ClientHello from bytes. |
| `HttpLayer` | Owns one HTTP connection. |
| `HttpStream` | Owns one request and response exchange. |
| `HTTPMode` | Whether the HTTP layer acts as regular, transparent, upstream or reverse. |
| `validate_request` | Checks an inbound request, optionally including header-name validation. |

# Dependencies

- Internal: [proxy-core](proxy-core.md) (`Layer` base, events and commands).
- Internal: [proxy-modes](proxy-modes.md) chooses which mode layer starts.
- Internal: options read here include `http2`, `http3`, `ssl_insecure`,
  `http_connect_send_host_header` and `validate_inbound_headers`; see [options](options.md).
- External: the protocol libraries imported by the `_http*` modules (not enumerated here; check their imports).

# Key files

- `mitmproxy/proxy/layers/http/__init__.py` - `HttpLayer`, `HttpStream` and `validate_request`.
- `mitmproxy/proxy/layers/tls.py` - the TLS layers and their hooks.
- `mitmproxy/proxy/layers/modes.py` - destination logic for each mode.

# Gotchas

- Commit `ef279567` disabled HTTP/2 CONNECT for secure web proxies, and changed
  `mitmproxy/proxy/layers/tls.py` as well as `mitmproxy/addons/tlsconfig.py`
  (CHANGELOG entry included). Any change to the CONNECT path must keep this.
- Inbound header validation is the defence against request smuggling. The rule
  is in [the guardrail](../operations/guardrails/http-smuggling-hard-fail.md);
  `validate_request` is where it is applied.

# Citations

- `ef279567` - disable HTTP/2 CONNECT for secure web proxies.
