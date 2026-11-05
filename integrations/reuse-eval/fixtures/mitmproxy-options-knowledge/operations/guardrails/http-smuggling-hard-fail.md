---
type: Guardrail
title: Inbound HTTP header validation must stay on by default
description: Malformed inbound HTTP/1 and HTTP/2 headers, including whitespace in header names, are rejected by default. Disabling validate_inbound_headers reopens HTTP request smuggling.
applies_to:
  - mitmproxy/proxy/layers/http/__init__.py
  - mitmproxy/proxy/layers/http/_http1.py
  - mitmproxy/proxy/layers/http/_http2.py
rule: Inbound header validation is on by default. Do not change the default of validate_inbound_headers to False, and do not bypass validate_request or the HTTP/1 header-name check. Turning validation off is a user choice that the option help already flags as enabling HTTP smuggling.
motivated_by:
  - b06fb6d1
  - b41416b7
enforced_by:
  - test/mitmproxy/proxy/layers/http/test_http.py
  - test/mitmproxy/net/http/http1/test_read.py
source_files:
  - mitmproxy/proxy/layers/http/__init__.py
  - mitmproxy/proxy/layers/http/_http1.py
  - mitmproxy/proxy/layers/http/_http2.py
timestamp: 2025-04-07T20:09:53+02:00
generated_by: catalogify/0.11.0
open_questions:
  - "Human to confirm: is the rule above the intended policy, and is it enforced anywhere beyond the two listed tests? Commit b06fb6d1 names GHSA-gcx2-gvj7-pxv3 and b41416b7 names GHSA-22gh-3r9q-xf38; the advisories are the authority for the wording."
---

# Rule

Inbound HTTP requests are checked for malformed structure, including
whitespace in header names, before mitmproxy forwards them. The check is
controlled by `validate_inbound_headers` (declared in
`mitmproxy/addons/proxyserver.py`, default `True`). Its help text says that
disabling it makes mitmproxy vulnerable to HTTP smuggling.

# Why

Two security advisories drove this:

- `b06fb6d1` - security: reject whitespace in HTTP/1 header names. The commit
  fixes GHSA-gcx2-gvj7-pxv3 and introduces the option.
- `b41416b7` - a merge from GHSA-22gh-3r9q-xf38 that makes mitmproxy hard-fail
  on request and response smuggling attempts.

# How to apply

- When changing the header or request parsing in `_http1.py`, `_http2.py` or
  `validate_request`, keep the validation on the default path.
- When adding a test for a new malformed-input case, put it in the two enforced
  test files so the guardrail is checked.
- If you need looser parsing for a specific client, make it an explicit option
  and leave the default alone.

# Citations

- `b06fb6d1` - security: reject whitespace in HTTP/1 header names (GHSA-gcx2-gvj7-pxv3).
- `b41416b7` - merge of GHSA-22gh-3r9q-xf38 (request/response smuggling hard-fail).
