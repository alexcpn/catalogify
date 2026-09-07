#!/usr/bin/env python3
"""okf-cochange.py — which parts of the repo change together.

The inventory ranks paths by churn and the history script explains one path.
Neither answers the question a routing agent actually has: *when someone
implements a change like this, what else moves?*

Two directories that are always edited in the same commit are coupled, and
that coupling is invisible to everything else in this toolchain. It does not
appear in an import graph, a call graph, or the working tree, because the
mechanism is often a wire contract, a shared schema, a message topic or a
deployment ordering rule that no parser can see. It appears only in history.
This is `logical coupling` in the mining-software-repositories literature.

Metrics per pair (A, B):
  support     commits touching both. Raw evidence; ignore anything small.
  confidence  support / commits(A) — "when A changes, B changes X% of the
              time". Asymmetric on purpose: a library and its one caller are
              not equally predictive of each other.
  lift        confidence / base rate of B. Above 1 means the pair co-occurs
              more than chance; near 1 means B just changes a lot.

Commits touching more than --max-files paths are skipped: a mass rename or a
license-header sweep would otherwise couple everything to everything.

Usage:
  okf-cochange.py [<path> ...] [--depth N] [--since DATE] [--max-commits N]
                  [--max-files N] [--min-support N] [--top N] [--json]

With no paths, it reports the most coupled pairs repo-wide, grouping files
into units by their first --depth path components. With paths, each path is
its own unit and the report is oriented around them.

Requires git; stdlib only.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict


def git_log(max_commits, since):
    args = ["git", "log", "--no-merges", "--name-only", "--format=%x00%H"]
    if max_commits:
        args += ["-n", str(max_commits)]
    if since:
        args += ["--since", since]
    try:
        done = subprocess.run(args, capture_output=True, text=True, check=False)
    except OSError as exc:
        sys.exit(f"okf-cochange: could not run git: {exc}")
    if done.returncode != 0:
        # Same convention as okf-history.sh: outside a repository there is no
        # history to mine, which is not an error the agent should stop on.
        print("okf-cochange: not a git repository — no history to mine.", file=sys.stderr)
        raise SystemExit(0)
    for chunk in done.stdout.split("\0"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        lines = [ln for ln in chunk.split("\n") if ln.strip()]
        if len(lines) < 2:
            continue  # a commit that touched no files
        yield lines[0], lines[1:]


def unit_of(path, explicit, depth):
    """Map one file to the unit it belongs to.

    A file under one of the explicitly requested paths belongs to that path.
    Everything else still gets a unit, by depth, so the requested paths can
    be found coupled to the rest of the repository rather than only to each
    other.
    """
    for prefix in explicit:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return prefix
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    return "/".join(parts[:min(depth, len(parts) - 1)])


def main():
    ap = argparse.ArgumentParser(
        description="Directories that change together, mined from commit history.",
    )
    ap.add_argument("paths", nargs="*", help="Units to report on (default: whole repo, grouped by --depth)")
    ap.add_argument("--depth", type=int, default=2, help="Path components per unit for everything outside the given paths (default 2)")
    ap.add_argument("--since", help="Only commits after this date, e.g. '2 years ago'")
    ap.add_argument("--max-commits", type=int, default=2000, help="Commits to scan, newest first (default 2000)")
    ap.add_argument("--max-files", type=int, default=40, help="Skip commits touching more paths than this (default 40)")
    ap.add_argument("--min-support", type=int, default=3, help="Ignore pairs seen in fewer commits (default 3)")
    ap.add_argument("--top", type=int, default=15, help="Rows per unit, or overall (default 15)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    explicit = [p.rstrip("/") for p in args.paths]
    for p in explicit:
        if not os.path.exists(p):
            sys.exit(f"okf-cochange: path does not exist: {p}")

    unit_commits = defaultdict(int)
    pair_commits = defaultdict(int)
    scanned = skipped = 0

    for _sha, files in git_log(args.max_commits, args.since):
        scanned += 1
        if len(files) > args.max_files:
            skipped += 1
            continue
        units = {u for u in (unit_of(f, explicit, args.depth) for f in files) if u}
        for u in units:
            unit_commits[u] += 1
        ordered = sorted(units)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                pair_commits[(a, b)] += 1

    considered = scanned - skipped
    if not considered:
        sys.exit("okf-cochange: no commits to analyse.")

    # Build each unit's neighbour list, ranked by how strongly it predicts them.
    neighbours = defaultdict(list)
    for (a, b), support in pair_commits.items():
        if support < args.min_support:
            continue
        ca, cb = unit_commits[a], unit_commits[b]
        for src, dst, c_src, c_dst in ((a, b, ca, cb), (b, a, cb, ca)):
            confidence = support / c_src if c_src else 0.0
            base = c_dst / considered if considered else 0.0
            neighbours[src].append({
                "unit": dst,
                "support": support,
                "confidence": round(confidence, 4),
                "lift": round(confidence / base, 2) if base else None,
            })
    for rows in neighbours.values():
        rows.sort(key=lambda r: (-r["confidence"], -r["support"]))

    if explicit:
        report_units = [u for u in explicit if u in unit_commits] or explicit
    else:
        report_units = sorted(neighbours, key=lambda u: -unit_commits[u])[:args.top]

    result = {
        "commits_scanned": scanned,
        "commits_skipped_as_bulk": skipped,
        "max_files": args.max_files,
        "min_support": args.min_support,
        "depth": args.depth,
        "units": [{
            "unit": u,
            "commits": unit_commits.get(u, 0),
            "changes_with": neighbours.get(u, [])[:args.top],
        } for u in report_units],
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    scope = (f"given paths vs. the repo at depth {args.depth}" if explicit
             else f"units at depth {args.depth}")
    print(f"co-change coupling — {considered} commits analysed "
          f"({skipped} bulk commits over {args.max_files} files skipped), {scope}")
    print(f"support = commits touching both; confidence = how often the other "
          f"moves when this one does; lift > 1 = more than chance\n")
    for entry in result["units"]:
        print(f"{entry['unit']}  ({entry['commits']} commits)")
        rows = entry["changes_with"]
        if not rows:
            print(f"    no partner reaches support >= {args.min_support}\n")
            continue
        print("    also changes                                          conf   support   lift")
        for r in rows:
            lift = f"{r['lift']:.1f}" if r["lift"] is not None else "  -"
            print(f"    {r['unit']:<50} {r['confidence'] * 100:4.0f}%   {r['support']:>7}   {lift:>4}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
