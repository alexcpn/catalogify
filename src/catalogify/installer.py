"""`catalogify install`: install this skill into one or more AI agents.

The skill descriptor (SKILL.md) uses the open Agent Skills format, so the same
files work in Claude Code, Cursor, OpenAI Codex, and any tool that reads the
generic `.agents/skills` location. This command copies the skill directory —
SKILL.md, its `references/` workflow files, and the config template — into each
agent's skills directory, for the current user (default) or a specific project.

Typical use (after `uv tool install catalogify`):

  catalogify install                 # all agents, user-global
  catalogify install --agents cursor # just Cursor
  catalogify install --scope project # into ./.<agent>/skills
  catalogify install --list          # show where it is installed
  catalogify install --uninstall     # remove it
"""
import argparse
import shutil
from importlib.resources import as_file, files
from pathlib import Path

from . import __version__

SKILL_NAME = "catalogify"

# Per-agent skills directory, relative to the scope base (home dir or project dir).
AGENT_DIRS = {
    "claude": ".claude/skills",   # Claude Code
    "cursor": ".cursor/skills",   # Cursor
    "codex": ".codex/skills",     # OpenAI Codex CLI
    "agents": ".agents/skills",   # open standard (Copilot, Gemini CLI, Goose, ...)
}
ALL_AGENTS = list(AGENT_DIRS)

# Agents without a documented per-project skills directory.
_PROJECT_UNSUPPORTED = {"codex"}

# Packaging scaffolding that must not leak into an installed skill directory.
_ASSET_EXCLUDES = shutil.ignore_patterns("__init__.py", "__pycache__", "*.pyc")


def _parse_agents(value: str) -> list:
    if not value or value.strip().lower() == "all":
        return list(ALL_AGENTS)
    chosen = []
    for raw in value.split(","):
        agent = raw.strip().lower()
        if not agent:
            continue
        if agent == "all":
            return list(ALL_AGENTS)
        if agent not in AGENT_DIRS:
            raise SystemExit(
                f"Unknown agent: {agent!r}. Choose from: {', '.join(ALL_AGENTS)}, all"
            )
        if agent not in chosen:
            chosen.append(agent)
    return chosen


def _scope_base(scope: str, target: str) -> Path:
    if scope == "user":
        return Path.home()
    return Path(target).expanduser().resolve()


def _dest_dir(agent: str, scope: str, target: str) -> Path:
    return _scope_base(scope, target) / AGENT_DIRS[agent] / SKILL_NAME


def install_skill(agents: list, scope: str, target: str, force: bool) -> int:
    where = "user-global (home)" if scope == "user" else f"project ({_scope_base(scope, target)})"
    print(f"Installing skill '{SKILL_NAME}' [{where}] into: {', '.join(agents)}")

    installed = skipped = 0
    with as_file(files("catalogify._skill_assets")) as assets:
        for agent in agents:
            if scope == "project" and agent in _PROJECT_UNSUPPORTED:
                print(f"  - {agent}: no per-project skills dir; use --scope user. Skipped.")
                continue
            dest = _dest_dir(agent, scope, target)
            if (dest / "SKILL.md").exists() and not force:
                print(f"  - {agent}: already present ({dest}) -- use --force to overwrite")
                skipped += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(assets, dest, ignore=_ASSET_EXCLUDES, dirs_exist_ok=True)
            print(f"  - {agent}: {dest / 'SKILL.md'}")
            installed += 1

    print(f"\nDone. Installed: {installed}, skipped: {skipped}.")
    print("Commands provided by this package (restart the agent if it was running):")
    print("  catalogify inventory [out.json] [--config <cfg>]   # repo inventory + git churn")
    print("  catalogify history <path>... [--limit N] [--json]  # per-concept git history")
    print("  catalogify validate <dir> [--config <cfg>]         # OKF v0.1 conformance")
    return 0


def list_skill(agents: list, scope: str, target: str) -> int:
    where = "user-global (home)" if scope == "user" else f"project ({_scope_base(scope, target)})"
    print(f"Skill '{SKILL_NAME}' [{where}]:")
    for agent in agents:
        skill_file = _dest_dir(agent, scope, target) / "SKILL.md"
        status = "present" if skill_file.exists() else "absent "
        print(f"  - {agent:7s} {status}  {skill_file}")
    return 0


def uninstall_skill(agents: list, scope: str, target: str) -> int:
    removed = 0
    for agent in agents:
        dest = _dest_dir(agent, scope, target)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
            print(f"  - {agent}: removed {dest}")
            removed += 1
        else:
            print(f"  - {agent}: nothing to remove ({dest})")
    print(f"\nDone. Removed: {removed}.")
    return 0


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        prog="catalogify install",
        description="Install the OKF knowledge-bundle skill into AI agents (Claude, Cursor, Codex, ...).",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--install", action="store_true", help="Install the skill (default action).")
    action.add_argument("--list", action="store_true", help="Show where the skill is installed.")
    action.add_argument("--uninstall", action="store_true", help="Remove the skill.")

    parser.add_argument(
        "--agents",
        default="all",
        metavar="LIST",
        help=f"Comma-separated agents or 'all'. Choices: {', '.join(ALL_AGENTS)}. Default: all.",
    )
    parser.add_argument(
        "--scope",
        choices=("user", "project"),
        default="user",
        help="user = ~/.<agent>/skills (default); project = ./.<agent>/skills.",
    )
    parser.add_argument(
        "--target",
        default=".",
        metavar="DIR",
        help="Project directory for --scope project (default: current directory).",
    )
    parser.add_argument(
        "--global",
        dest="force_user_scope",
        action="store_true",
        help="Alias for --scope user (kept for convenience).",
    )
    parser.add_argument("--force", action="store_true", default=True, help="Overwrite existing skill files.")
    parser.add_argument("--version", action="version", version=f"catalogify {__version__}")
    args = parser.parse_args(argv)

    scope = "user" if args.force_user_scope else args.scope
    agents = _parse_agents(args.agents)

    if args.list:
        return list_skill(agents, scope, args.target)
    if args.uninstall:
        return uninstall_skill(agents, scope, args.target)
    if args.install:
        return install_skill(agents, scope, args.target, args.force)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
