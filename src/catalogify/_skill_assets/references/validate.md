# Validate — OKF conformance check

Run the OKF conformance checker against the bundle and interpret the
results for the user.

Scope hints: if the user named a bundle path, validate that one.

## Steps

1. Resolve `CONFIG` and `BUNDLE_DIR` as described in
   `SKILL.md`; a bundle path named by the user wins over the config.
2. Run:

   ```bash
   catalogify validate "$BUNDLE_DIR" --config "$CONFIG"   # drop --config if none was found
   ```

3. Interpret the output using OKF §9 semantics:
   - **ERRORs** make the bundle non-conformant (unparseable frontmatter,
     missing/empty `type`, malformed `index.md`/`log.md`, or a `log.md`
     date block missing its `Commit:` line — E4). Offer to fix them, and
     fix on confirmation.
   - **WARNINGs** are soft guidance a consumer must tolerate: broken
     cross-links (W2), missing `title`/`description` (W1), missing
     indexes (W3), empty concept bodies (W4), possible secrets (W5),
     dangling `source_files` entries (W6), possible duplicate concepts
     sharing a type+title (W7), and unresolved `open_questions` (W8).
     Report them grouped by kind; broken links may legitimately represent
     not-yet-written knowledge. For W8, point the user at
     the **clarify** workflow to resolve the questions. Do not re-derive
     W4/W5/W6/W7/W8 yourself — the validator already found them; just
     relay and prioritize.
4. Additionally spot-check quality the validator can't mechanically
   judge:
   - Indexes whose entries lack descriptions.
   - Stale `timestamp`s: for each concept (or, if the last **update**
     run's diff range is known, just the concepts it touched — otherwise
     spot-check up to 10), compare its `timestamp`
     against `git log -1 --format=%cI -- <path>` for each file in its
     `source_files`. Flag it if `timestamp` predates any of them — that
     means the doc claims to reflect an older version of the code than
     what's currently on disk.
5. Summarize with a conformant / non-conformant verdict and a short
   prioritized fix list.
