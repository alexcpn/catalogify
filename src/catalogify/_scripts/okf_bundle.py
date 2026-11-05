"""okf_bundle.py — reading an OKF bundle, shared by verify_okf.py and okf_find.py.

Parsing only: frontmatter, sections, the concept walk, and the typed parts of
the ontology layer (relations, playbooks, guardrails). Nothing here touches
git; the scripts that import this do their own checking.

The ontology layer is a set of producer extension fields (OKF §4.1):

  relations      on any concept: a list of {kind, target, evidence}
  applies_to     on a Playbook or Guardrail: the paths whose change it concerns
  rule           on a Guardrail: the rule, one sentence
  motivated_by   on a Guardrail: commits that explain it
  enforced_by    on a Guardrail: tracked tests / CI / lint files that enforce it
  forbids        on a Guardrail: a list of {pattern, in} literal tripwires

Relation kinds are a fixed vocabulary, so verify can apply one evidence rule
per kind and an agent cannot invent vague predicates.
"""

import os
import re

try:
    import yaml  # type: ignore
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

RESERVED = {"index.md", "log.md"}
# Not concepts: a bundle's human front door, since forges render README.md
# when a directory is opened and ignore index.md; agent instruction files for
# agents that read the bundle; and the human-owned GUIDANCE.md. Matches
# validate_okf.py.
IGNORED = {"README.md", "GUIDANCE.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md"}
IGNORED_LOWER = {n.lower() for n in IGNORED}

HEADING = re.compile(r"^#{1,3}\s+(.*?)\s*$", re.M)
SHA = re.compile(r"^[0-9a-f]{7,40}$")

# kind -> what backs it. `requires` belongs to playbooks.
RELATION_KINDS = {
    "changes_with": "moves in the same commits as the target",
    "generated_from": "is regenerated from the target",
    "versioned_by": "needs a version entry in the target when it changes",
    "calls": "invokes the target at runtime",
    "reads_config": "reads options declared in the target",
    "requires": "a change it applies to also needs the target",
}
PLAYBOOK = "playbook"
GUARDRAIL = "guardrail"


def split_frontmatter(text):
    if not text.startswith("---"):
        return None, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def parse_yaml(fm):
    if HAVE_YAML:
        try:
            data = yaml.safe_load(fm)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError:
            return None
    data, key = {}, None
    for line in fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s*(.*)$", line)
        if item and key:
            data.setdefault(key, []).append(item.group(1).strip().strip("'\""))
            continue
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            key = k.strip()
            v = v.strip().strip("'\"")
            data[key] = v if v else []
    return data


def sections(body):
    """Split a body into {heading: text} by markdown heading."""
    out, current, buf = {}, None, []
    for line in body.splitlines():
        m = HEADING.match(line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf)
            current, buf = m.group(1).strip().lower(), []
        else:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf)
    return out


def under(filepath, prefix):
    """True when `filepath` is `prefix` itself or sits inside it."""
    prefix = prefix.rstrip("/")
    filepath = filepath.rstrip("/")
    return filepath == prefix or filepath.startswith(prefix + "/")


def overlaps(a, b):
    """True when one path contains the other (file in dir, dir in dir, equal)."""
    return under(a, b) or under(b, a)


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def str_list(value):
    return [str(v).strip() for v in as_list(value) if isinstance(v, (str, int)) and str(v).strip()]


def concept_type(data):
    return str((data or {}).get("type") or "").strip().lower()


def walk(bundle):
    """{relative path: (text, frontmatter dict or None, body)} for every concept file."""
    concepts = {}
    for dirpath, dirnames, filenames in os.walk(bundle):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            if not f.endswith(".md") or f in RESERVED or f.lower() in IGNORED_LOWER:
                continue
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, bundle)
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            fm, body = split_frontmatter(text)
            data = parse_yaml(fm) if fm else None
            concepts[rel] = (text, data if isinstance(data, dict) else None, body)
    return concepts


def relations(data):
    """(well-formed relations, problems) from a concept's frontmatter.

    A relation is well-formed when it is a mapping with a string `kind` and a
    string `target`; `evidence` is optional and normalised to a list of
    strings. Problems are human-readable reasons, one per bad entry. The kind
    is not checked against the vocabulary here: that is a verify finding.
    """
    raw = (data or {}).get("relations")
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["`relations` is not a list"]
    good, problems = [], []
    for i, rel in enumerate(raw):
        if not isinstance(rel, dict):
            problems.append(f"relation #{i + 1} is not a mapping")
            continue
        kind, target = rel.get("kind"), rel.get("target")
        if not isinstance(kind, str) or not kind.strip():
            problems.append(f"relation #{i + 1} has no `kind`")
            continue
        if not isinstance(target, str) or not target.strip():
            problems.append(f"relation #{i + 1} ({kind}) has no `target`")
            continue
        good.append({
            "kind": kind.strip(),
            "target": target.strip().rstrip("/") or target.strip(),
            # As written, for verify to judge: a bare all-digit SHA arrives as an
            # int (YAML 1.1 even reads a leading 0 as octal), a branch name as a str.
            "raw_evidence": as_list(rel.get("evidence")),
        })
    return good, problems


def forbids(data):
    """(well-formed tripwires, problems) from a Guardrail's `forbids` list."""
    raw = (data or {}).get("forbids")
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["`forbids` is not a list"]
    good, problems = [], []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("pattern"), str) or not item["pattern"]:
            problems.append(f"forbids #{i + 1} needs a non-empty `pattern`")
            continue
        scope = str_list(item.get("in")) or str_list((data or {}).get("applies_to"))
        good.append({"pattern": item["pattern"], "in": scope})
    return good, problems


def structure_problems(data):
    """Structural problems in the ontology fields; validate reports these as W12."""
    if not isinstance(data, dict):
        return []
    problems = list(relations(data)[1])
    kind = concept_type(data)
    if kind in (PLAYBOOK, GUARDRAIL) and not str_list(data.get("applies_to")):
        problems.append(f"a {data.get('type')} needs `applies_to`")
    if kind == GUARDRAIL:
        if not isinstance(data.get("rule"), str) or not data["rule"].strip():
            problems.append("a Guardrail needs a one-sentence `rule`")
        problems.extend(forbids(data)[1])
    return problems
