#!/usr/bin/env python3
"""okf_find.py — what the bundle knows about one file, without reading the bundle.

An agent about to change a file needs a few facts, not a 40k-token map: the
rules that guard the file, what has to change with it, and why. This looks
those up for each path given and prints them, bounded:

  guardrails  Guardrails whose applies_to covers the path, listed first
  concepts    concepts whose source_files cover it: title and description
  relations   their typed relations (outgoing), and relations in other
              concepts that point at the path (incoming): "X is
              generated_from this"
  playbooks   Playbooks whose applies_to covers it: what else the change
              requires, and the steps, truncated

Nothing is checked here; `catalogify verify` checks the same fields.

Usage: okf_find.py <path>... [--bundle DIR] [--repo-root PATH] [--max N] [--json]
The bundle defaults to `okf.bundle_dir` in .okf-config.yml, else knowledge/.
Exit 0 always (an unknown path is an empty answer), 2 on bad usage.

Stdlib only; PyYAML is needed to read relations, playbooks and guardrails.
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_bundle import (  # noqa: E402  (sibling module, shared with verify_okf.py)
    GUARDRAIL, HAVE_YAML, PLAYBOOK, concept_type, forbids, overlaps, relations,
    sections, str_list, walk,
)


def repo_root_of(start):
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                             capture_output=True, text=True, check=False)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except OSError:
        pass
    return os.path.abspath(start)


def configured_bundle(repo_root):
    cfg = os.path.join(repo_root, ".okf-config.yml")
    try:
        with open(cfg, encoding="utf-8") as fh:
            m = re.search(r"^\s*bundle_dir:\s*[\"']?([^\"'#\n]+)", fh.read(), re.M)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return "knowledge"


def excerpt(text, limit):
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def lookup(query, concepts, limit, step_chars):
    found = {"path": query, "guardrails": [], "concepts": [], "incoming": [], "playbooks": []}
    for rel, (_, data, body) in sorted(concepts.items()):
        if not data:
            continue
        ctype = concept_type(data)
        title = str(data.get("title") or rel)
        applies = str_list(data.get("applies_to"))
        if ctype == GUARDRAIL and any(overlaps(query, a) for a in applies):
            found["guardrails"].append({
                "concept": rel, "title": title, "rule": str(data.get("rule") or "").strip(),
                "enforced_by": str_list(data.get("enforced_by")),
                "forbids": [t["pattern"] for t in forbids(data)[0]],
            })
        elif ctype == PLAYBOOK and any(overlaps(query, a) for a in applies):
            steps = next((v for k, v in sections(body).items() if k.startswith("step")), "")
            found["playbooks"].append({
                "concept": rel, "title": title,
                "requires": [r["target"] for r in relations(data)[0] if r["kind"] == "requires"],
                "steps": excerpt(steps, step_chars),
            })
        elif ctype not in (PLAYBOOK, GUARDRAIL) and any(
                overlaps(query, s) for s in str_list(data.get("source_files"))):
            found["concepts"].append({
                "concept": rel, "title": title, "type": data.get("type"),
                "description": str(data.get("description") or "").strip(),
                "relations": [{"kind": r["kind"], "target": r["target"]} for r in relations(data)[0]],
            })
        # Incoming: a relation elsewhere whose target is this path.
        if ctype != PLAYBOOK:
            for r in relations(data)[0]:
                if overlaps(query, r["target"]):
                    found["incoming"].append({
                        "concept": rel, "title": title, "kind": r["kind"],
                        "from": str_list(data.get("source_files")) or applies,
                    })
    for key in ("concepts", "incoming", "playbooks", "guardrails"):
        found[key] = found[key][:limit]
    return found


def render(found):
    lines = [f"== {found['path']}"]
    if not any(found[k] for k in ("guardrails", "concepts", "incoming", "playbooks")):
        lines.append("   nothing in the bundle covers this path")
        return "\n".join(lines)
    for g in found["guardrails"]:
        how = []
        if g["enforced_by"]:
            how.append("enforced by " + ", ".join(g["enforced_by"]))
        if g["forbids"]:
            how.append("forbids " + ", ".join(f"`{p}`" for p in g["forbids"]))
        lines.append(f"   GUARDRAIL {g['title']}: {g['rule']}"
                     + (f" ({'; '.join(how)})" if how else " (not enforced)")
                     + f"  [{g['concept']}]")
    for c in found["concepts"]:
        lines.append(f"   concept   {c['title']} ({c['type']}): {c['description']}  [{c['concept']}]")
        for r in c["relations"]:
            lines.append(f"             {r['kind']} -> {r['target']}")
    for i in found["incoming"]:
        src = ", ".join(i["from"][:2]) + ("…" if len(i["from"]) > 2 else "")
        lines.append(f"   incoming  {src or i['title']} {i['kind']} this  [{i['concept']}]")
    for p in found["playbooks"]:
        lines.append(f"   PLAYBOOK  {p['title']}  [{p['concept']}]")
        if p["requires"]:
            lines.append("             also change: " + ", ".join(p["requires"]))
        if p["steps"]:
            lines.extend("             " + ln for ln in p["steps"].splitlines() if ln.strip())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Look up what the bundle says about a file or directory.")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--bundle", help="Bundle directory (default: okf.bundle_dir, else knowledge/)")
    ap.add_argument("--repo-root", help="Repository root (default: git toplevel of the cwd)")
    ap.add_argument("--max", type=int, default=5, help="Entries per section (default 5)")
    ap.add_argument("--steps-chars", type=int, default=800, help="Playbook steps excerpt length")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.repo_root) if args.repo_root else repo_root_of(os.getcwd())
    bundle = args.bundle or os.path.join(root, configured_bundle(root))
    if not os.path.isdir(bundle):
        ap.error(f"bundle directory {bundle} not found (use --bundle)")
    if not HAVE_YAML:
        print("okf-find: PyYAML is not installed; relations, playbooks and guardrails "
              "cannot be read.", file=sys.stderr)

    concepts = walk(bundle)
    results = []
    for p in args.paths:
        query = os.path.relpath(os.path.abspath(p), root) if os.path.exists(p) else p
        results.append(lookup(query.rstrip("/"), concepts, args.max, args.steps_chars))

    if args.json:
        print(json.dumps({"bundle": os.path.relpath(bundle, root), "results": results}, indent=2))
    else:
        print("\n\n".join(render(r) for r in results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
