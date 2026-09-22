---
description: "Check that an OKF knowledge bundle's claims are supported by the repository"
---

# /speckit.okf.verify — Check the bundle's claims against the code

`/speckit.okf.validate` answers *is this bundle well-formed?*. This answers the
harder question: **is any of it true?**

Every check here resolves a statement in the prose back to something in the
repository, so a confident sentence with nothing behind it is caught by a tool
rather than by a reader. An agent auditing its own prose is the unreliable
case; git is not.

User input (optional bundle path):

$ARGUMENTS

## Steps

1. Resolve `bundle_dir` from `.specify/extensions/okf/okf-config.yml`
   (default `knowledge/`); a path named by the user wins.

2. Run:

   ```bash
   python3 .specify/extensions/okf/scripts/python/verify_okf.py <bundle_dir>
   ```

   Add `--json` for machine-readable output, or `--strict` to fail on notes
   as well as findings.

3. Interpret the result.

   **FINDINGS — the repository does not support the claim. Fix these.**

   | | What it means | What to do |
   | --- | --- | --- |
   | V1 | A cited commit does not exist here | Re-run `okf-history.sh` on the concept's own `source_files` and cite from that |
   | V2 | A cited commit touches none of this concept's `source_files` | The evidence belongs to another concept; move or replace it |
   | V3 | A commit cited under `# Gotchas` changed only test files | Delete the claim. Test hygiene is not a production invariant |
   | V4 | A symbol in `# Interfaces` is in no non-test source file | It was written from memory. Grep for the real name |
   | V5 | `# Gotchas` asserts invariants and cites nothing | Cite the commit, or delete the claim |
   | V8 | A `source_files` path is not tracked by git | Vendored or imported code. Delete the concept and say which subtree it came from |

   **NOTES — arguable, and needing judgement rather than obedience.**

   | | What it means |
   | --- | --- |
   | V6 | A `# Dependencies` link no import backs in either direction. Often a genuine runtime coupling — a queue, an RPC, shared storage. Say which in the prose, or remove the link |
   | V7 | The body claims an "import cycle" in Go. The compiler forbids them; what is meant is usually a shared leaf sub-package |

4. Apply the fixes, then re-run until findings reach zero. Report to the
   user: findings before and after, notes left standing with the reason each
   is legitimate, and how many `open_questions` remain for
   `/speckit.okf.clarify`.

## What zero findings does and does not mean

It means every cited commit exists and belongs to its concept, every named
symbol exists in non-test code, every source path is tracked, and no invariant
is asserted without evidence.

It does **not** mean the gotchas are the *right* gotchas, or that the prose is
correct. Nothing mechanical can establish that. What these checks remove is a
class of error, verifiably — the residue is what a human should read, starting
with the open questions.

## Requirements

Needs `git` and a git repository: every check resolves claims against history,
so outside a repository there is nothing to verify against and the script exits
cleanly with a notice.
