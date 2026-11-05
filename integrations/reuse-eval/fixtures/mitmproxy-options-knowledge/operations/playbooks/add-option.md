---
type: Playbook
title: Add a new option
description: Checklist for adding a mitmproxy option, from the declaration to the CLI flag, the generated web types and the changelog.
applies_to:
  - mitmproxy/options.py
  - mitmproxy/addons/
  - mitmproxy/tools/cmdline.py
relations:
  - {kind: requires, target: web/src/js/ducks/_options_gen.ts, evidence: [091399f8, a44191a9, 71d7b3d6]}
source_files:
  - mitmproxy/options.py
  - web/gen/all
  - web/gen/options_js.py
timestamp: 2025-04-21T14:56:58+02:00
generated_by: catalogify/0.11.0
open_questions:
  - "Should a new option always be declared in mitmproxy/options.py, or is declaring it in the addon that uses it the preferred pattern? The repo has both; no document says which to use when."
---

# Steps

1. **Declare the option.** For a core option, add an `add_option(name, type,
   default, help)` call in `Options.__init__` in `mitmproxy/options.py`. For an
   option owned by an addon, call `loader.add_option(...)` in the addon's `load`
   method, as `mitmproxy/addons/proxyserver.py` does for `validate_inbound_headers`.
   Write a full help string: it is shown by `--options`, the web UI and the
   console.
2. **Expose it on the command line if users need a flag.** Add
   `opts.make_parser(<parser or group>, "<name>")` in
   `mitmproxy/tools/cmdline.py`, in `common_options` for every tool, or in
   `mitmproxy()`, `mitmdump()` or `mitmweb()` for a single tool. `make_parser`
   silently skips names it does not know, so check the flag appears in
   `mitmdump --help`.
3. **Regenerate the web option types.** Run `web/gen/all` (CI does the same in
   `.github/workflows/autofix.yml`, step at line 28). That rewrites
   `web/src/js/ducks/_options_gen.ts` from `web/gen/options_js.py`. Commit the
   regenerated file. Do not hand-edit it.
4. **Check the type is supported.** `_ts_type` in `web/gen/options_js.py` maps
   only `bool`, `str`, `int`, `Sequence[str]`, `str | None` and `int | None`.
   Any other type raises `RuntimeError` during generation, so add a mapping
   first.
5. **Test it.** Run `uv run pytest test/mitmproxy/test_options.py` and
   `uv run pytest test/mitmproxy/test_optmanager.py` (AGENTS.md requires
   `uv run pytest`, not bare `pytest`).
6. **Changelog.** Add an entry to `CHANGELOG.md`. Recent option commits
   (`a44191a9`, `71d7b3d6`) updated it in the same change.

# Evidence

Commits `091399f8`, `a44191a9` and `71d7b3d6` each changed `mitmproxy/options.py`
and `web/src/js/ducks/_options_gen.ts` together. Commit `a44191a9` also changed
`mitmproxy/tools/cmdline.py`, which is why step 2 is listed.

# Citations

- `091399f8` - Add experimental option for HTTP/3 in transparent mode (#7037).
- `a44191a9` - Add `--show-ignored-hosts` (#6720).
- `71d7b3d6` - Include Host header with CONNECT requests (#7021).
