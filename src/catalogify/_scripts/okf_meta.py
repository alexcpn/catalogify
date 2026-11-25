#!/usr/bin/env python3
"""okf_meta.py — one routing index over many repos' catalogify bundles.

A meta repo lists every repo's units (services, modules, components) and the
edges between them, so a planning agent can route a feature to the few repos
it touches before opening any code.

  init [<dir>]                       scaffold a meta repo
  sync [--root D] [name=dir ...]     summarise child bundles, read in place
  derive [--root D]                  rebuild components/, edges/ and indexes

Sync never copies a child bundle. It writes one bounded digest per repo,
`bundles/<name>/summary.md`: units, the edges inside the repo (from the child's
typed `relations` and `# Dependencies` links), and the identifiers each unit
provides and uses per declared contract. Derive reads only `repos.yaml` and
those summaries. Cross-repo edges are name matches: evidence of a caller, not
proof.

Pages derive writes carry `generated_by: catalogify-meta/<version>`. Pages
without it are never touched. On a rebuild a derived page keeps its `# Notes`
section and its `open_questions`, which merge by question ID.

Exit codes: 0 ok, 1 an input is not an OKF bundle or a domain slug collides,
2 usage error.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Shared parsing lives in verify_okf.py on this branch; import, don't fork.
from verify_okf import (FILE_EXT, IGNORED_LOWER, LINK, RESERVED, parse_yaml,  # noqa: E402
                        sections, split_frontmatter, table_first_column)
import okf_meta_templates as templates  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:  # PyYAML is a package dependency; this is a broken install
    yaml = None

NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
GROUP_BY = re.compile(r"^(directory|catalog:.+|frontmatter:.+)$")
DEFAULT_UNIT_TYPES = ["Service", "Module", "Component"]
EDGE_KINDS = ("calls", "changes_with", "generated_from", "versioned_by", "reads_config")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
MATCHABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
COMMIT = re.compile(r"^Commit:\s+`([0-9a-fA-F]{7,40}|none)`\s*$")
CLARIFIED = re.compile(r"<!--\s*clarified:\s*(\S+?)\s*-->")
QUESTION_ID = re.compile(r"^\[([^\]\s]+)\]\s*")
INDEX_MARK = "<!-- generated_by: catalogify-meta/"
SKIP_DIRS = {"bundles", "workspace", "scripts"}
EVIDENCE = ("A match means the consumer's page named the identifier at the summarised "
            "commit. That is evidence of a caller, not proof: check the consumer's code "
            "before relying on it.")


class Usage(Exception):
    """Exit 2."""


class NotBundle(Exception):
    """Exit 1."""


def version():
    """The catalogify version next to this script, else the installed one."""
    init = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "__init__.py")
    try:
        with open(init, encoding="utf-8") as fh:
            m = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read())
            if m:
                return m.group(1)
    except OSError:
        pass
    try:
        from catalogify import __version__  # type: ignore
        return __version__
    except ImportError:
        return "unknown"


def plural(n, word, suffix="s"):
    return f"{n} {word}{'' if n == 1 else suffix}"


def today():
    return datetime.date.today().isoformat()


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


# --- files -------------------------------------------------------------------

VOLATILE = re.compile(r"^\s*(timestamp|synced):.*$", re.M)


def write_if_changed(path, text):
    """Write `text` unless the file already says the same apart from its
    `timestamp:`/`synced:` lines. Returns True when it wrote. Atomic."""
    path = str(path)
    try:
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
        if VOLATILE.sub("", old) == VOLATILE.sub("", text):
            return False
    except OSError:
        pass
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return True


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def q(s):
    """A YAML scalar: JSON strings are valid YAML double-quoted strings."""
    return json.dumps(s, ensure_ascii=False)


def emit_frontmatter(fields):
    """Fixed-order frontmatter. `fields` is a list of (key, value) pairs;
    None values are left out, lists are block sequences."""
    out = ["---"]
    for key, value in fields:
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            out.append(f"{key}:")
            out += [f"  - {q(v)}" for v in value]
        elif isinstance(value, bool):
            out.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            out.append(f"{key}: {value}")
        else:
            out.append(f"{key}: {q(value)}")
    out.append("---")
    return "\n".join(out) + "\n"


def cell(s):
    return str(s).replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def table_rows(text):
    """Data rows of the markdown tables in `text`, cells unescaped."""
    rows, header_seen = [], False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            header_seen = False
            continue
        cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s.strip().strip("|"))]
        if all(set(c) <= set("-: ") for c in cells):
            header_seen = True
            continue
        if header_seen:
            rows.append(cells)
    return rows


def unquote(c):
    c = c.strip()
    return c[1:-1] if len(c) >= 2 and c[0] == c[-1] == "`" else c


# --- ownership ---------------------------------------------------------------

def is_marked(text):
    """Derived by meta: a `generated_by: catalogify-meta/` frontmatter key, or
    (for index.md, which may not carry frontmatter) a first-line comment."""
    if text is None:
        return False
    fm, body = split_frontmatter(text)
    if fm and re.search(r"^generated_by:\s*[\"']?catalogify-meta/", fm, re.M):
        return True
    return body.lstrip().startswith(INDEX_MARK)


def previous_notes(text):
    """The raw `# Notes` section, heading included, up to the next level-1
    heading or the end; "" when there is none."""
    if not text:
        return ""
    _, body = split_frontmatter(text)
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^#\s+Notes\s*$", line):
            end = next((j for j in range(i + 1, len(lines)) if re.match(r"^#\s", lines[j])), len(lines))
            return "\n".join(lines[i:end]).rstrip() + "\n"
    return ""


def previous_questions(text):
    if not text:
        return []
    fm, _ = split_frontmatter(text)
    data = parse_yaml(fm) if fm else None
    oq = (data or {}).get("open_questions")
    return [str(x) for x in oq if isinstance(x, str) and x.strip()] if isinstance(oq, list) else []


def merge_questions(previous, detected, notes):
    """Keep the previous list verbatim, then add each
    detected (id, text) whose id is neither already there nor clarified."""
    have = {m.group(1) for m in (QUESTION_ID.match(p) for p in previous) if m}
    clarified = set(CLARIFIED.findall(notes or ""))
    out = list(previous)
    for qid, text in detected:
        if qid not in have and qid not in clarified:
            out.append(f"[{qid}] {text}")
            have.add(qid)
    return out


# --- registry ----------------------------------------------------------------

def load_registry(root):
    path = os.path.join(root, "repos.yaml")
    text = read(path)
    if text is None or not text.strip():
        raise Usage(f"no repos.yaml in {root}; run 'catalogify meta init' first")
    if yaml is None:
        raise Usage("PyYAML is required to read repos.yaml (pip install PyYAML)")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise Usage(f"repos.yaml is not valid YAML: {exc}")
    if not isinstance(data, dict):
        raise Usage("repos.yaml must be a mapping; run 'catalogify meta init' first for a template")
    if data.get("version") != 1:
        raise Usage(f"repos.yaml: version must be 1, found {data.get('version')!r}")
    repos = data.get("repos")
    if not isinstance(repos, dict) or not repos:
        raise Usage("repos.yaml lists no repos; see the template from 'catalogify meta init'")

    out = {}
    for name, e in repos.items():
        where = f"repos.yaml: repo {name!r}"
        if not isinstance(name, str) or not NAME.match(name):
            raise Usage(f"{where}: names must match {NAME.pattern}")
        if name == "external":
            raise Usage(f"{where}: 'external' is reserved for components/external/")
        if not isinstance(e, dict):
            raise Usage(f"{where}: must be a mapping")
        for key in ("title", "remote"):
            if not isinstance(e.get(key), str) or not e[key].strip():
                raise Usage(f"{where}: needs a non-empty {key}")
        if "bundle_path" not in e or not (e["bundle_path"] is None or isinstance(e["bundle_path"], str)):
            raise Usage(f"{where}: needs bundle_path (a path, or null for no bundle)")
        group_by = e.get("group_by") or "directory"
        if not isinstance(group_by, str) or not GROUP_BY.match(group_by):
            raise Usage(f"{where}: group_by must be directory, catalog:<page> or frontmatter:<key>")
        for key in ("local", "url"):
            if e.get(key) is not None and not isinstance(e[key], str):
                raise Usage(f"{where}: {key} must be a string")
        if e.get("url") and "{path}" not in e["url"]:
            raise Usage(f"{where}: url needs a {{path}} placeholder")
        lists = {}
        for key, default in (("catalog_skip", []), ("unit_types", DEFAULT_UNIT_TYPES)):
            v = e.get(key, default)
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise Usage(f"{where}: {key} must be a list of strings")
            lists[key] = v
        out[name] = {
            "title": e["title"].strip(), "remote": e["remote"].strip(),
            "bundle_path": e["bundle_path"], "local": e.get("local"), "url": e.get("url"),
            "group_by": group_by, **lists,
        }

    contracts = {}
    raw = data.get("contracts") or {}
    if not isinstance(raw, dict):
        raise Usage("repos.yaml: contracts must be a mapping")
    for name, c in raw.items():
        where = f"repos.yaml: contract {name!r}"
        if not isinstance(name, str) or not NAME.match(name):
            raise Usage(f"{where}: names must match {NAME.pattern}")
        if not isinstance(c, dict) or not isinstance(c.get("title"), str) or not c["title"].strip():
            raise Usage(f"{where}: needs a title")
        prov = c.get("provides") or {}
        cons = c.get("consumes") or {}
        if not isinstance(prov, dict) or not isinstance(cons, dict):
            raise Usage(f"{where}: provides and consumes must be mappings")
        pattern = prov.get("pattern")
        if pattern is not None:
            try:
                if re.compile(pattern).groups < 1:
                    raise Usage(f"{where}: provides.pattern needs a capture group (group 1 is the identifier)")
            except re.error as exc:
                raise Usage(f"{where}: provides.pattern is not a valid regex: {exc}")
        sections_ = cons.get("sections")
        if sections_ is not None and (not isinstance(sections_, list)
                                      or not all(isinstance(x, str) for x in sections_)):
            raise Usage(f"{where}: consumes.sections must be a list of strings")
        min_length = c.get("min_length", 6)
        if not isinstance(min_length, int) or isinstance(min_length, bool) or min_length < 1:
            raise Usage(f"{where}: min_length must be a positive integer")
        contracts[name] = {
            "title": c["title"].strip(),
            "section": str(prov.get("section") or "Interfaces"),
            "pattern": pattern,
            "consumes": sections_,
            "min_length": min_length,
        }
    return {"repos": out, "contracts": contracts}


def config_hash(entry, contracts):
    """A hash of what sync applied while building a summary, so derive can
    tell when repos.yaml changed since."""
    payload = {k: entry[k] for k in ("group_by", "catalog_skip", "unit_types")}
    payload["contracts"] = contracts
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


# --- reading a child bundle (sync only) --------------------------------------

def newest_commit(log_text):
    """The `Commit:` of the first (newest) dated block, else 'unknown'."""
    in_block = False
    for line in log_text.splitlines():
        if line.startswith("## "):
            if in_block:
                return "unknown"
            in_block = True
            continue
        if in_block:
            m = COMMIT.match(line.strip())
            if m:
                return "unknown" if m.group(1) == "none" else m.group(1)
    return "unknown"


def walk_bundle(src):
    """{posix rel path: (frontmatter dict, body)} for every concept file."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for f in sorted(filenames):
            if not f.endswith(".md") or f in RESERVED or f.lower() in IGNORED_LOWER:
                continue
            path = os.path.join(dirpath, f)
            text = read(path)
            if text is None:
                continue
            fm, body = split_frontmatter(text)
            data = parse_yaml(fm) if fm else None
            rel = os.path.relpath(path, src).replace(os.sep, "/")
            out[rel] = (data if isinstance(data, dict) else {}, body)
    return out


def resolve_link(from_rel, target):
    """A link target as a bundle-relative posix path, or None for external."""
    target = target.split("#")[0].strip()
    if not target or "://" in target or target.startswith("mailto:"):
        return None
    if target.startswith("/"):
        path = target.lstrip("/")
    else:
        path = os.path.join(os.path.dirname(from_rel), target)
    path = os.path.normpath(path).replace(os.sep, "/")
    return None if path.startswith("..") else path


def str_list(v):
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v if isinstance(x, (str, int))] if isinstance(v, list) else []


def group_units(concepts, entry):
    """{rel: domain} for the concepts a domain claims under `group_by`."""
    mode = entry["group_by"]
    if mode == "directory":
        types = {t.lower() for t in entry["unit_types"]}
        return {rel: (rel.split("/")[0] if "/" in rel else "Root")
                for rel, (data, _) in concepts.items()
                if str(data.get("type", "")).strip().lower() in types}
    if mode.startswith("frontmatter:"):
        key = mode.split(":", 1)[1]
        out = {}
        for rel, (data, _) in concepts.items():
            v = data.get(key)
            if isinstance(v, list):
                v = v[0] if v else None
            out[rel] = str(v).strip() if v not in (None, "") else "Unassigned"
        return out
    # catalog:<page>
    page_rel = mode.split(":", 1)[1].lstrip("/")
    if page_rel not in concepts:
        raise NotBundle(f"catalog page {page_rel} is not a concept in this bundle")
    skip = {s.strip().lower() for s in entry["catalog_skip"]}
    out, heading = {}, None
    for line in concepts[page_rel][1].splitlines():
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            heading = m.group(1).strip()
            continue
        if heading is None or heading.lower() in skip:
            continue
        for target in LINK.findall(line):
            rel = resolve_link(page_rel, target)
            if rel in concepts and rel != page_rel:
                if rel not in out:
                    out[rel] = heading
                break  # the first link to a concept on each line
    return out


def find_section(secs, name):
    """Sections whose heading is `name`, or starts with it (`Interfaces (gRPC)`)."""
    name = name.strip().lower()
    return [k for k in secs if k == name or k.startswith(name + " ") or k.startswith(name + "(")]


def code_shaped(s, min_length):
    return (len(s) >= min_length and
            ("_" in s or "." in s or any(c.isdigit() for c in s) or re.search(r"[a-z][A-Z]", s) is not None))


def segments(tok):
    """A dotted token and every contiguous run of its segments."""
    parts = [p for p in tok.split(".") if p]
    return {".".join(parts[i:j]) for i in range(len(parts)) for j in range(i + 1, len(parts) + 1)}


def provided_identifiers(body, secs, contract, problems, where):
    if contract["pattern"]:
        found = {m.group(1) for m in re.finditer(contract["pattern"], body) if m.group(1)}
    else:
        found = set()
        for key in find_section(secs, contract["section"]):
            for c in table_first_column(secs[key]):
                spans = re.findall(r"`([^`]+)`", c) or [c]
                for span in spans:
                    span = re.sub(r"^\([^)]*\)\s*", "", span.strip())  # Go receiver
                    span = span.split("(")[0].strip()                  # call arguments
                    if span:
                        found.add(span)
    out = set()
    for ident in found:
        if not code_shaped(ident, contract["min_length"]):
            continue
        if not MATCHABLE.match(ident):
            problems.append(f"{where}: identifier \"{ident}\" cannot be matched; use provides.pattern")
            continue
        out.add(ident.strip("."))
    return out


def used_identifiers(body, secs, contract, own):
    if contract["consumes"]:
        text = "\n".join(secs[k] for name in contract["consumes"] for k in find_section(secs, name))
    elif contract["pattern"]:
        text = body
    else:
        skip = set(find_section(secs, contract["section"]))
        text = "\n".join(v for k, v in secs.items() if k not in skip)
        if not secs:
            text = body
        else:  # text before the first heading counts too
            first = re.search(r"^#{1,3}\s", body, re.M)
            if first and first.start() > 0:
                text = body[:first.start()] + "\n" + text
    # Link targets and URLs name files, not identifiers.
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"\S+://\S+", " ", text)
    out = set()
    for tok in TOKEN.findall(text):
        tok = tok.strip(".")
        if "." in tok and tok.rsplit(".", 1)[1].lower() in FILE_EXT:
            continue  # frontend.yaml, auth.md
        for seg in segments(tok):
            if code_shaped(seg, contract["min_length"]):
                out.add(seg)
    return out - own


def covering_unit(target, unit_sources):
    """The unit whose source_files cover `target` most specifically, or a
    ('tie', [units]) / None."""
    target = target.strip().lstrip("./")
    best, best_len, tied = None, -1, []
    for rel, sources in unit_sources.items():
        for sf in sources:
            s = sf.strip().lstrip("./").rstrip("/")
            if not s:
                continue
            if target == s or target.startswith(s + "/"):
                if len(s) > best_len:
                    best, best_len, tied = rel, len(s), [rel]
                elif len(s) == best_len and rel != best:
                    tied.append(rel)
    if len(set(tied)) > 1:
        return ("tie", sorted(set(tied)))
    return best


def build_summary(name, entry, contracts, src, ver):
    """Read a child bundle in place and return (summary text, stats)."""
    if not os.path.isdir(src) or not os.path.isfile(os.path.join(src, "index.md")) \
            or not os.path.isfile(os.path.join(src, "log.md")):
        raise NotBundle(f"{src} is not an OKF bundle (needs index.md and log.md)")
    ref = newest_commit(read(os.path.join(src, "log.md")) or "")
    concepts = walk_bundle(src)
    domains = group_units(concepts, entry)
    units = sorted(domains)
    unit_sources = {rel: str_list(concepts[rel][0].get("source_files")) for rel in units}

    stats = {"uncovered": 0, "problems": [], "ties": []}
    edges = {}
    for rel in units:
        data, body = concepts[rel]
        rels = data.get("relations")
        for r in rels if isinstance(rels, list) else []:
            if not isinstance(r, dict) or r.get("kind") not in EDGE_KINDS or not isinstance(r.get("target"), str):
                continue
            to = covering_unit(r["target"], unit_sources)
            if isinstance(to, tuple):
                stats["ties"].append(f"{name} {rel}: relation target {r['target']} is covered equally "
                                     f"by {' and '.join(to[1])}; no edge recorded")
                continue
            if to is None:
                stats["uncovered"] += 1
                continue
            if to == rel:
                continue
            key = (rel, r["kind"], to)
            edges.setdefault(key, set()).update(str_list(r.get("evidence")))
        secs = sections(body)
        for key in [k for k in secs if k.startswith("dependenc")]:
            for target in LINK.findall(secs[key]):
                to = resolve_link(rel, target)
                if to in domains and to != rel:
                    edges.setdefault((rel, "depends_on", to), set())

    provides, uses = [], []
    for rel in units:
        data, body = concepts[rel]
        secs = sections(body)
        for cname in sorted(contracts):
            c = contracts[cname]
            own = provided_identifiers(body, secs, c, stats["problems"], f"{name} {rel}")
            provides += [(rel, cname, i) for i in sorted(own)]
            used = used_identifiers(body, secs, c, own)
            if used:
                uses.append((rel, cname, sorted(used)))

    fields = [
        ("type", "Reference"),
        ("title", f"Summary of {entry['title']}'s bundle"),
        ("description", f"Generated by catalogify meta sync from {entry['bundle_path']}/ at {ref}. Do not edit."),
        ("generated_by", f"catalogify-meta/{ver}"),
        ("source", entry["remote"]),
        ("subpath", entry["bundle_path"]),
        ("ref", ref),
        ("synced", today()),
        ("config", config_hash(entry, contracts)),
        ("units", len(units)),
        ("edges", len(edges)),
    ]
    body = [
        "# Units", "",
        table(["Unit", "Type", "Domain", "Title", "Description"], [
            [f"`{cell(rel)}`", cell(concepts[rel][0].get("type", "")), cell(domains[rel]),
             cell(concepts[rel][0].get("title", rel)), cell(concepts[rel][0].get("description", ""))]
            for rel in units]), "",
        "# Edges", "",
        table(["From", "Kind", "To", "Evidence"], [
            [f"`{cell(a)}`", k, f"`{cell(b)}`", " ".join(sorted(ev))]
            for (a, k, b), ev in sorted(edges.items())]), "",
        "# Provides", "",
        table(["Unit", "Contract", "Identifier"], [[f"`{cell(r)}`", c, f"`{cell(i)}`"] for r, c, i in provides]), "",
        "# Uses", "",
        table(["Unit", "Contract", "Identifiers"],
              [[f"`{cell(r)}`", c, ", ".join(f"`{cell(i)}`" for i in ids)] for r, c, ids in uses]), "",
    ]
    stats.update(units=len(units), edges=len(edges), provided=len(provides), ref=ref)
    return emit_frontmatter(fields) + "\n" + "\n".join(body), stats


def read_summary(path):
    """Parse a summary back. Shared by derive and verify (V15/V16)."""
    text = read(path)
    if text is None:
        return None
    fm, body = split_frontmatter(text)
    data = (yaml.safe_load(fm) if yaml else parse_yaml(fm)) if fm else {}
    secs = sections(body)

    def rows(name):
        return table_rows(secs.get(name, ""))

    def idents(c):
        return [unquote(x) for x in re.findall(r"`[^`]*`", c)]

    return {
        "fm": data or {},
        "units": [{"path": unquote(r[0]), "type": r[1], "domain": r[2], "title": r[3], "description": r[4]}
                  for r in rows("units") if len(r) >= 5],
        "edges": [{"from": unquote(r[0]), "kind": r[1], "to": unquote(r[2]), "evidence": r[3].split()}
                  for r in rows("edges") if len(r) >= 4],
        "provides": [{"unit": unquote(r[0]), "contract": r[1], "identifier": unquote(r[2])}
                     for r in rows("provides") if len(r) >= 3],
        "uses": [{"unit": unquote(r[0]), "contract": r[1], "identifiers": idents(r[2])}
                 for r in rows("uses") if len(r) >= 3],
    }


def link_template(entry):
    """The repo's `url`, or <remote>/blob/{ref}/<bundle_path>/{path}."""
    if entry.get("url"):
        return entry["url"]
    base = entry["remote"].rstrip("/")
    if base.endswith(".git"):
        base = base[:-4]
    sub = (entry["bundle_path"] or "").strip("/")
    sub = "" if sub in ("", ".") else sub + "/"
    return f"{base}/blob/{{ref}}/{sub}{{path}}"


def link_ref(ref):
    return "HEAD" if not ref or ref == "unknown" else str(ref)


def link_for(entry, ref, path):
    """A forge permalink to a child page at the summarised commit."""
    return link_template(entry).replace("{ref}", link_ref(ref)).replace("{path}", path)


# --- commands ----------------------------------------------------------------

def cmd_init(directory, ver):
    os.makedirs(directory, exist_ok=True)
    commit = "none"
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=directory, capture_output=True, text=True)
        if p.returncode == 0 and re.fullmatch(r"[0-9a-f]{7,40}", p.stdout.strip()):
            commit = p.stdout.strip()
    except OSError:
        pass
    for rel, tmpl in templates.SCAFFOLD.items():
        path = os.path.join(directory, rel)
        if os.path.exists(path):
            print(f"{'kept':<8}{rel}")
            continue
        text = tmpl
        if rel in ("index.md", "architecture/index.md"):
            text = tmpl.replace("{version}", ver)
        elif rel == "log.md":
            text = tmpl.replace("{date}", today()).replace("{commit}", commit)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"{'created':<8}{rel}")
    print("next: fill in repos.yaml, then run `catalogify meta sync`")
    return 0


def read_mounts(root):
    text = read(os.path.join(root, "okf-registry.yaml"))
    if not text or yaml is None:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}
    mounts = data.get("mounts") if isinstance(data, dict) else None
    return {k: v for k, v in mounts.items() if isinstance(v, dict)} if isinstance(mounts, dict) else {}


def write_mounts(root, mounts):
    lines = ["# Generated by catalogify meta sync. Do not edit: the next sync rewrites it.", "mounts:"]
    for key in sorted(mounts):
        m = mounts[key]
        lines.append(f"  {key}:")
        for field in ("source", "subpath", "ref", "synced"):
            lines.append(f"    {field}: {q(str(m.get(field)) if m.get(field) is not None else None)}")
    write_if_changed(os.path.join(root, "okf-registry.yaml"), "\n".join(lines) + "\n")


def cmd_sync(root, pairs, ver):
    reg = load_registry(root)
    repos = reg["repos"]
    targets = {}
    if pairs:
        for p in pairs:
            name, sep, d = p.partition("=")
            if not sep or not name or not d:
                raise Usage(f"malformed argument {p!r}: expected name=dir")
            if name not in repos:
                raise Usage(f"{name!r} is not a repo in repos.yaml")
            if repos[name]["bundle_path"] is None:
                raise Usage(f"{name!r} has bundle_path: null, so there is nothing to sync")
            targets[name] = os.path.abspath(d)
    else:
        for name, e in repos.items():
            if e["bundle_path"] is not None and e["local"]:
                local = e["local"] if os.path.isabs(e["local"]) else os.path.join(root, e["local"])
                targets[name] = os.path.normpath(os.path.join(local, e["bundle_path"]))
    if not targets:
        raise Usage("nothing to sync: give name=dir arguments, or set `local` on repos in repos.yaml")

    mounts = read_mounts(root)
    failed, done = False, 0
    for name in sorted(targets):
        e = repos[name]
        try:
            text, stats = build_summary(name, e, reg["contracts"], targets[name], ver)
        except NotBundle as exc:
            print(f"error: {name}: {exc}", file=sys.stderr)
            failed = True
            continue
        for msg in stats["problems"] + stats["ties"]:
            warn(msg)
        mount = os.path.join(root, "bundles", name)
        removed = False
        if os.path.isdir(mount):
            for entry_ in os.listdir(mount):
                if entry_ == "summary.md":
                    continue
                p = os.path.join(mount, entry_)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
                removed = True
        write_if_changed(os.path.join(mount, "summary.md"), text)
        if removed:
            print(f"removed copied bundle files from bundles/{name}/")
        key = f"bundles/{name}"
        new = {"source": e["remote"], "subpath": e["bundle_path"], "ref": stats["ref"], "synced": today()}
        old = mounts.get(key)
        if old and all(str(old.get(k)) == str(new[k]) for k in ("source", "subpath", "ref")):
            new["synced"] = str(old.get("synced") or new["synced"])
        mounts[key] = new
        done += 1
        extra = f" ({plural(stats['uncovered'], 'relation target')} not covered by a unit)" \
            if stats["uncovered"] else ""
        note = "  warning: no Commit: in log.md" if stats["ref"] == "unknown" else ""
        print(f"summarised {name} ref {stats['ref']}  {plural(stats['units'], 'unit')}, "
              f"{plural(stats['edges'], 'edge')}{extra}, {stats['provided']} provided{note}")
    write_mounts(root, mounts)
    print(f"synced {plural(done, 'repo')}")
    return 1 if failed else 0


# File names validate and verify never treat as concepts (AGENTS.md is matched
# case-insensitively), so a domain called "agents" can't be agents.md.
NOT_CONCEPT_STEMS = {n[:-3] for n in RESERVED | IGNORED_LOWER}


def slug(s):
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "unnamed"
    return out + "-domain" if out in NOT_CONCEPT_STEMS else out


class Page:
    def __init__(self, rel, kind, title, description, tags, sources, body, questions=()):
        self.rel, self.kind, self.title, self.description = rel, kind, title, description
        self.tags, self.sources, self.body, self.questions = tags, sources, body, list(questions)


def render(page, ver, existing):
    notes = previous_notes(existing)
    questions = merge_questions(previous_questions(existing), page.questions, notes)
    fields = [
        ("type", page.kind), ("title", page.title), ("description", page.description),
        ("tags", page.tags), ("timestamp", now()), ("generated_by", f"catalogify-meta/{ver}"),
        ("source_files", sorted(set(page.sources))), ("open_questions", questions),
    ]
    body = page.body.rstrip() + "\n"
    if notes:
        body += "\n" + notes
    return emit_frontmatter(fields) + "\n" + body


def cmd_derive(root, ver):
    reg = load_registry(root)
    repos, contracts = reg["repos"], reg["contracts"]
    code = 0
    summaries = {}
    for name in sorted(repos):
        e = repos[name]
        if e["bundle_path"] is None:
            continue
        s = read_summary(os.path.join(root, "bundles", name, "summary.md"))
        if s is None:
            warn(f"{name} has no summary; run catalogify meta sync")
            continue
        if str(s["fm"].get("config")) != config_hash(e, contracts):
            warn(f"{name}: summary built with an older repos.yaml; resync")
        summaries[name] = s

    # Domains. A slug collision excludes the whole repo from this run.
    domains = {}   # repo -> slug -> (domain name, [unit dicts])
    unit_domain = {}  # (repo, path) -> slug
    collided = set()
    for name, s in summaries.items():
        by_slug, names = {}, {}
        for u in s["units"]:
            sl = slug(u["domain"])
            if sl in names and names[sl] != u["domain"]:
                print(f"error: {name}: domains \"{names[sl]}\" and \"{u['domain']}\" both map to "
                      f"components/{name}/{sl}.md; rename one in the catalog or frontmatter",
                      file=sys.stderr)
                collided.add(name)
                break
            names[sl] = u["domain"]
            by_slug.setdefault(sl, (u["domain"], []))[1].append(u)
        if name not in collided:
            domains[name] = by_slug
            for sl, (_, us) in by_slug.items():
                for u in us:
                    unit_domain[(name, u["path"])] = sl
    if collided:
        code = 1
    live = {n: s for n, s in summaries.items() if n not in collided}

    def unit_link(repo, path):
        return link_for(repos[repo], live[repo]["fm"].get("ref"), path)

    titles = {(n, u["path"]): u["title"] for n, s in live.items() for u in s["units"]}

    # Cross-repo edges: a unit uses an identifier another repo's unit provides.
    providers = {}  # (contract, ident) -> [(repo, unit)]
    for n, s in live.items():
        for p in s["provides"]:
            if (n, p["unit"]) in unit_domain and p["contract"] in contracts:
                providers.setdefault((p["contract"], p["identifier"]), []).append((n, p["unit"]))
    rows = []  # (contract, prov repo, prov slug, prov unit, ident, cons repo, cons slug, cons unit, ambiguous)
    for n, s in live.items():
        for u in s["uses"]:
            if (n, u["unit"]) not in unit_domain or u["contract"] not in contracts:
                continue
            for ident in u["identifiers"]:
                provs = [pv for pv in providers.get((u["contract"], ident), []) if pv[0] != n]
                prov_repos = tuple(sorted({pv[0] for pv in providers.get((u["contract"], ident), [])}))
                for pr, pu in provs:
                    rows.append((u["contract"], pr, unit_domain[(pr, pu)], pu, ident, n,
                                 unit_domain[(n, u["unit"])], u["unit"], len(prov_repos) > 1, prov_repos))
    rows = sorted(set(rows))

    pages = []
    # Contract pages.
    by_page = {}
    for r in rows:
        by_page.setdefault((r[0], r[1], r[2]), []).append(r)
    for (c, pr, psl), rs in sorted(by_page.items()):
        dname = domains[pr][psl][0]
        cons_repos = sorted({r[5] for r in rs})
        qs = [(f"contract-approval:{c}/{pr}-{psl}",
               "Who approves a change to this contract, and how is compatibility with each consumer confirmed?")]
        for ident in sorted({r[4] for r in rs if r[8]}):
            others = sorted({x for r in rs if r[4] == ident for x in r[9]})
            qs.append((f"ambiguous-provider:{ident}",
                       f"`{ident}` is provided by {', '.join(others)}. Which one does each consumer here use?"))
        table_rows_ = []
        for r in rs:
            note = ""
            if r[8]:
                note = "ambiguous: also provided by " + ", ".join(x for x in r[9] if x != pr)
            table_rows_.append([
                f"[{cell(titles[(r[5], r[7])])}]({unit_link(r[5], r[7])})",
                f"{r[5]} / [{cell(domains[r[5]][r[6]][0])}](../../components/{r[5]}/{r[6]}.md)",
                f"`{cell(r[4])}`",
                f"[{cell(titles[(pr, r[3])])}]({unit_link(pr, r[3])})",
                note,
            ])
        n_cons = len({(r[5], r[7]) for r in rs})
        body = "\n".join([
            "# Summary", "",
            f"{contracts[c]['title']} provided by {repos[pr]['title']} **{dname}**, used by "
            f"{plural(n_cons, 'unit')} in {', '.join(cons_repos)}. Provider domain: "
            f"[{pr} {dname}](../../components/{pr}/{psl}.md).", "",
            "# Contract", "",
            table(["Consumer", "Consumer repo / domain", "Identifier", "Provider", "Note"], table_rows_), "",
            "# Evidence", "", EVIDENCE, "",
        ])
        pages.append(Page(
            f"edges/{c}/{pr}-{psl}.md", "Interface", f"{contracts[c]['title']}: {pr} {dname}",
            f"{contracts[c]['title']} provided by {repos[pr]['title']} {dname}, used by "
            f"{plural(n_cons, 'unit')} in other repos.",
            ["meta", c, pr], [f"bundles/{x}/summary.md" for x in [pr] + cons_repos], body, qs))

    # Component pages.
    n_within = 0
    for n in sorted(domains):
        s = live[n]
        n_within += len(s["edges"])
        for sl, (dname, us) in sorted(domains[n].items()):
            mine = {u["path"] for u in us}
            unit_rows = [[f"[{cell(u['title'])}]({unit_link(n, u['path'])})", cell(u["type"]), cell(u["description"])]
                         for u in sorted(us, key=lambda u: u["path"])]
            listed, same = [], 0
            for e in s["edges"]:
                a_in, b_in = e["from"] in mine, e["to"] in mine
                if not (a_in or b_in) or (n, e["from"]) not in unit_domain or (n, e["to"]) not in unit_domain:
                    continue
                if a_in and b_in:
                    same += 1
                    continue
                other = unit_domain[(n, e["to"] if a_in else e["from"])]
                listed.append([
                    f"[{cell(titles[(n, e['from'])])}]({unit_link(n, e['from'])})", e["kind"],
                    f"[{cell(titles[(n, e['to'])])}]({unit_link(n, e['to'])})",
                    f"[{cell(domains[n][other][0])}]({other}.md)"])
            within = []
            if listed:
                within.append(table(["From", "Kind", "To", "Other domain"], listed))
            else:
                within.append(f"No edges to other domains of {n} are declared.")
            if same:
                within.append(f"{plural(same, 'edge')} between units of this domain "
                              f"{'is' if same == 1 else 'are'} not listed.")
            # Cross-repo lines.
            cross, other_sources = [], set()
            prov_pages = {}
            for r in rows:
                if r[1] == n and r[2] == sl:
                    prov_pages.setdefault((r[0], r[1], r[2]), set()).add((r[5], r[6]))
            for (c, pr, psl), cons in sorted(prov_pages.items()):
                who = ", ".join(f"{cr} {domains[cr][cs][0]}" for cr, cs in sorted(cons))
                cross.append(f"- **Provides {contracts[c]['title']}** to {who}: see "
                             f"[{c}/{pr}-{psl}](../../edges/{c}/{pr}-{psl}.md)")
                other_sources |= {cr for cr, _ in cons}
            use_pages = {}
            for r in rows:
                if r[5] == n and r[6] == sl:
                    use_pages.setdefault((r[0], r[1], r[2]), set()).add(r[4])
            for (c, pr, psl), ids in sorted(use_pages.items()):
                cross.append(f"- **Uses {pr} {domains[pr][psl][0]}** ({contracts[c]['title']}): "
                             + ", ".join(f"`{i}`" for i in sorted(ids))
                             + f"; see [{c}/{pr}-{psl}](../../edges/{c}/{pr}-{psl}.md)")
                other_sources.add(pr)
            if not cross:
                cross = ["No cross-repo edges were found by the declared contracts."]
            first = ", ".join(u["title"] for u in sorted(us, key=lambda u: u["path"])[:5])
            body = "\n".join([
                "# Summary", "",
                f"{repos[n]['title']} domain **{dname}**: {plural(len(us), 'unit')}. "
                f"Route here when a feature touches {first}.", "",
                "# Units", "",
                table(["Unit", "Type", "Description"], unit_rows), "",
                f"# Edges within {n}", "",
                "\n\n".join(within), "",
                "# Cross-repo edges", "",
                "\n".join(cross), "",
            ])
            tags = ["meta", n] + sorted({r[0] for r in rows if (r[1] == n and r[2] == sl) or (r[5] == n and r[6] == sl)})
            pages.append(Page(
                f"components/{n}/{sl}.md", "Component", f"{repos[n]['title']}: {dname}",
                f"{plural(len(us), 'unit')} in the {dname} domain of {repos[n]['title']}.",
                tags, [f"bundles/{x}/summary.md" for x in {n} | other_sources], body))

    # Write derived pages; never overwrite a hand-owned file.
    produced = set()
    for p in pages:
        path = os.path.join(root, p.rel)
        existing = read(path)
        produced.add(p.rel)
        if existing is not None and not is_marked(existing):
            print(f"kept hand-owned {p.rel} (not regenerated)")
            continue
        write_if_changed(path, render(p, ver, existing))

    # External stubs: created once, unmarked.
    for name in sorted(repos):
        e = repos[name]
        if e["bundle_path"] is not None:
            continue
        path = os.path.join(root, "components", "external", f"{name}.md")
        if os.path.exists(path):
            continue
        text = emit_frontmatter([
            ("type", "Component"), ("title", e["title"]),
            ("description", f"{e['title']} has no catalogify bundle; this page is written by hand."),
            ("tags", ["meta", "external"]),
            ("open_questions", [f"[external-scope:{name}] What does {e['title']} provide to the estate, "
                                f"and who owns the contract with it?"]),
        ]) + "\n# Summary\n\n" + f"{e['title']} ({e['remote']}) has no catalogify bundle. Describe what " \
            "it provides and who uses it here. `catalogify meta derive` creates this page once and " \
            "never changes it.\n"
        write_if_changed(path, text)

    # Stale derived pages, except those of repos that collided.
    removed = 0
    for top in ("components", "edges"):
        base = os.path.join(root, top)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for f in filenames:
                if not f.endswith(".md") or f in RESERVED:
                    continue
                path = os.path.join(dirpath, f)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                if rel in produced:
                    continue
                text = read(path)
                if not is_marked(text):
                    continue
                fm, _ = split_frontmatter(text)
                srcs = str_list((parse_yaml(fm) or {}).get("source_files")) if fm else []
                if any(f"bundles/{c}/summary.md" in srcs for c in collided):
                    continue
                os.remove(path)
                removed += 1

    write_indexes(root, ver)
    n_comp = sum(1 for p in pages if p.kind == "Component")
    n_units = sum(len(s["units"]) for s in live.values())
    print(f"derived {plural(n_comp, 'component page')}, {plural(len(by_page), 'contract page')}; "
          f"{plural(n_units, 'unit')}, {plural(n_within, 'within-repo edge')}, "
          f"{plural(len(rows), 'cross-repo edge')}; removed {plural(removed, 'stale page')}")
    return code


def concept_meta(path):
    text = read(path) or ""
    fm, _ = split_frontmatter(text)
    data = (parse_yaml(fm) if fm else None) or {}
    return str(data.get("title") or os.path.basename(path)[:-3]), str(data.get("description") or "")


def write_indexes(root, ver):
    """An index.md per directory with concepts, below the meta root."""
    counts = {}  # rel dir -> concept count (recursive)
    listing = {}  # rel dir -> ([subdirs], [concept files])

    def scan(rel):
        full = os.path.join(root, rel) if rel else root
        try:
            names = sorted(os.listdir(full))
        except OSError:
            return 0
        subdirs, files = [], []
        total = 0
        for nm in names:
            p = os.path.join(full, nm)
            if os.path.isdir(p):
                if nm.startswith(".") or (not rel and nm in SKIP_DIRS):
                    continue
                child = f"{rel}/{nm}" if rel else nm
                c = scan(child)
                if c:
                    subdirs.append(nm)
                    total += c
            elif nm.endswith(".md") and nm not in RESERVED and nm.lower() not in IGNORED_LOWER:
                files.append(nm)
                total += 1
        counts[rel] = total
        listing[rel] = (subdirs, files)
        return total

    scan("")
    for rel in sorted(listing):
        subdirs, files = listing[rel]
        if rel and not counts[rel]:
            continue
        path = os.path.join(root, rel, "index.md") if rel else os.path.join(root, "index.md")
        existing = read(path)
        if existing is not None and not is_marked(existing):
            print(f"kept hand-owned {rel + '/' if rel else ''}index.md (may be stale)")
            continue
        title = "Meta bundle" if not rel else rel.split("/")[-1].replace("-", " ").capitalize()
        out = []
        if not rel:
            out += ["---", 'okf_version: "0.1"', "---", ""]
        out += [f"{INDEX_MARK}{ver} -->", f"# {title}", ""]
        if subdirs:
            out += ["## Directories", ""]
            out += [f"- [{d}/]({d}/index.md): {plural(counts[f'{rel}/{d}' if rel else d], 'concept')}"
                    for d in subdirs]
            out.append("")
        if files:
            out += ["## Concepts", ""]
            for f in files:
                t, d = concept_meta(os.path.join(root, rel, f))
                out.append(f"- [{cell(t)}]({f}): {cell(d)}" if d else f"- [{cell(t)}]({f})")
            out.append("")
        write_if_changed(path, "\n".join(out))
    # Marked indexes in directories that no longer hold concepts.
    for top in ("components", "edges"):
        for dirpath, _, filenames in os.walk(os.path.join(root, top), topdown=False):
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            if "index.md" in filenames and not counts.get(rel):
                p = os.path.join(dirpath, "index.md")
                if is_marked(read(p)):
                    os.remove(p)
            try:
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)
            except OSError:
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="catalogify meta",
        description="One routing index over many repos' catalogify bundles.")
    sub = ap.add_subparsers(dest="cmd")
    p_init = sub.add_parser("init", help="scaffold a meta repo",
                            description="Scaffold a meta repo. Existing files are kept.")
    p_init.add_argument("dir", nargs="?", default=".")
    p_sync = sub.add_parser("sync", help="summarise child bundles (read in place, never copied)",
                            description="Summarise each child bundle into bundles/<name>/summary.md. "
                                        "Reads local paths only; nothing is fetched or copied.")
    p_sync.add_argument("--root", default=".")
    p_sync.add_argument("pairs", nargs="*", metavar="name=dir",
                        help="sync these repos from these bundle directories")
    p_der = sub.add_parser("derive", help="rebuild components/, edges/ and the indexes",
                           description="Rebuild the derived pages from repos.yaml and the summaries.")
    p_der.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    if not args.cmd:
        print("usage: catalogify meta {init,sync,derive} ...\n\n"
              "  init [<dir>]                    scaffold a meta repo\n"
              "  sync [--root D] [name=dir ...]  summarise child bundles\n"
              "  derive [--root D]               rebuild components/, edges/ and indexes",
              file=sys.stderr)
        return 2
    ver = version()
    try:
        if args.cmd == "init":
            return cmd_init(args.dir, ver)
        if args.cmd == "sync":
            return cmd_sync(os.path.abspath(args.root), args.pairs, ver)
        return cmd_derive(os.path.abspath(args.root), ver)
    except Usage as exc:
        print(f"catalogify meta {args.cmd}: {exc}", file=sys.stderr)
        return 2
    except NotBundle as exc:
        print(f"catalogify meta {args.cmd}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
