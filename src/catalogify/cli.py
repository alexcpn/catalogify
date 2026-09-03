"""`catalogify` — the single entry point.

Subcommands forward every remaining argument to the tool that implements them,
so `catalogify history --limit 5 pkg/foo` behaves exactly like invoking the
underlying script directly. Run any subcommand with --help for its own flags.
"""
import sys

from . import __version__

USAGE = f"""catalogify {__version__} — turn a repository into a knowledge catalog

usage: catalogify <command> [args...]

Commands:
  inventory [out.json] [--config <cfg>]    Scan the repo into JSON: file tree,
                                           languages, entry points, manifests,
                                           API definitions, CI/CD, docs, ADRs,
                                           plus git churn and recent commits.
  history <path>... [--limit N] [--json]   Per-path git history: creation commit,
                                           recent subjects, and the revert /
                                           hotfix / risk-flagged commits where
                                           invariants hide. Add --patch for diffs
                                           (careful: can surface old secrets).
  validate <bundle_dir> [--config <cfg>]   Check a bundle against OKF v0.1 §9.
  install [--agents L] [--scope S]         Install the skill into your agents.
           [--list] [--uninstall]

Every command accepts --help.

The generated bundle is Open Knowledge Format v0.1:
https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""


def main(argv: list = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if args[0] in ("-V", "--version", "version"):
        print(f"catalogify {__version__}")
        return 0

    command, rest = args[0], args[1:]

    if command == "install":
        from .installer import main as installer_main
        # `catalogify install` defaults to installing; the installer's own
        # --list / --uninstall flags still select the other actions.
        if not any(a in rest for a in ("--list", "--uninstall", "--install")):
            rest = ["--install", *rest]
        return installer_main(rest)

    from . import runner
    dispatch = {
        "inventory": runner.inventory,
        "history": runner.history,
        "validate": runner.validate,
    }
    if command in dispatch:
        return dispatch[command](rest)

    print(f"catalogify: unknown command {command!r}\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
