# Clarify — resolve open questions with the user

You are acting as an **OKF enrichment agent** running a clarification pass.
Generation and update deliberately **park uncertainty** instead of guessing:
whenever a fact (an intent, an invariant, a "why") could not be established
from the code or its git history, they record an `open_questions` entry in a
concept's frontmatter. Your job here is to collect those questions, ask the
user, and fold the answers back into the bundle as durable, cited knowledge.

This is where the highest-value, human-only knowledge enters the KB — the
things that were never written in any commit message. Treat the answers as
**human curation**: once captured, later **update** runs must preserve them.

Scope hints: honor any scope the user gave (a subdirectory, a single
concept, or a topic like "security"); otherwise consider every open
question in the bundle.

## Steps

1. **Locate state.** Resolve `BUNDLE_DIR` and `CONFIG` as described in
   `SKILL.md` (default bundle dir `knowledge/`). If it
   doesn't exist or has no `.md` files, stop and tell the user to run
   the **generate** workflow first.

2. **Collect open questions.** Scan every concept file's frontmatter for a
   non-empty `open_questions:` list. Build a work list of
   `(concept_path, question)` pairs. Honor any scope hint the user gave
   (restrict to a subtree, a single concept, or questions matching a topic).
   If there are none, report "no open questions — bundle is fully clarified"
   and stop.

3. **Prioritize and budget.** Do not fire off dozens of questions blindly.
   - Rank by impact: invariants, data semantics, security/safety behavior,
     and anything affecting correctness come first; cosmetic or trivia last.
   - Ask in **batches** grouped by concept or theme, at most
     `clarify.max_questions` per run (config; default 20). If more remain,
     resolve the top batch and tell the user to re-run for the rest.
   - Before asking, make one more attempt to answer cheaply from history:
     `catalogify history <source-files>`.
     If a commit clearly answers it, resolve it from that (cite the sha) and
     don't spend a user question on it.

4. **Ask the user.** Present the batch as a numbered list, each item showing:
   the concept it belongs to, the question, and (briefly) why it matters /
   what you'd write given a plausible answer. Make questions **specific and
   answerable** ("Is X a hard SLA or best-effort?"), never open-ended
   ("tell me about X"). Let the user answer some, skip others, or say
   "don't know".

5. **Fold answers back in — surgically.** For each answered question:
   - Edit the concept body to state the now-verified fact in the right
     section (`# Responsibilities`, `# Schema`, a gotcha note, etc.).
   - Mark the sentence/section as clarified so the updater won't clobber it,
     using an HTML comment sentinel immediately before or after it:

     ```markdown
     <!-- clarified: 2026-07-20 — retry budget is a hard SLA (confirmed by owner) -->
     The retry budget in `submit_order()` is a **hard SLA**, not a heuristic.
     ```

   - Remove that entry from the concept's `open_questions` list. If the list
     becomes empty, remove the `open_questions` key entirely.
   - Update the concept's `timestamp` to now (ISO 8601).
   - For **skipped / "don't know"** questions: leave the `open_questions`
     entry in place (optionally append ` (asked <date>, unresolved)`), so a
     future run can revisit it. Never delete an unanswered question.

6. **Maintain reserved files.**
   - Prepend a dated entry to `log.md`, newest first (OKF §7), with the
     required `Commit:` line (current `HEAD`) as the first line under the
     heading:

     ```markdown
     ## <YYYY-MM-DD>
     Commit: `<head-sha>`
     * **Clarification**: Resolved 4 open questions across [Checkout Service](/services/checkout.md) and [Orders](/data/orders.md); 2 left unresolved.
     ```

   - `index.md` files rarely change here (descriptions may, if an answer
     changes a concept's one-liner) — update them only when they do.

7. **Validate and report.** Run

   ```bash
   catalogify validate "$BUNDLE_DIR" --config "$CONFIG"   # drop --config if none was found
   ```

   Fix any ERRORs, then summarize: N questions resolved, N skipped, N
   remaining (W8 count), and whether another clarify run is warranted.

## Hard rules

- **Never invent an answer.** If the user doesn't answer, the question stays
  in `open_questions` — an honest gap beats a confident fabrication.
- Answers are human curation: preserve them on future updates. Always emit
  the `<!-- clarified: ... -->` sentinel so the **update** workflow knows not
  to overwrite the surrounding fact.
- Preserve unknown frontmatter keys on round-trip (OKF §4.1); only touch
  `open_questions`, `timestamp`, and the body sections you are resolving.
- Batch and budget questions; a clarify run that spams the user is worse
  than one that resolves the top few and defers the rest.
- Never modify source code; all writes stay inside `BUNDLE_DIR`.
