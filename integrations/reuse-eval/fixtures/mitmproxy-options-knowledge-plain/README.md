# mitmproxy options and proxy core — knowledge bundle

This directory is generated. It describes how mitmproxy's option system
(`mitmproxy/options.py`, `mitmproxy/optmanager.py`, and their use by the
command line, the web UI and the proxy core) is built.

- Start here: [architecture/overview.md](architecture/overview.md)
- Index of everything: [index.md](index.md)

Built with catalogify 0.10.1 from commit `181dfb00`, 8 concepts.

## Checking it

`catalogify verify knowledge` resolves every cited commit, every interface
symbol and every source path against the repository.

## Correcting it

Unresolved uncertainty is parked in each concept's `open_questions`. The
`catalogify clarify` command walks a human through those questions, and an
answer given there is marked with a sentinel and survives later regeneration.
Editing a concept by hand is also fine, but a regeneration will not preserve
an unmarked edit, so prefer `clarify` for facts.
