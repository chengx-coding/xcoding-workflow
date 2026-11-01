# Docs surface profile

**Scope:** task-class. **Owner:** `xc-work/references/profiles/docs.md`. **Promotion status:**
`proposed` (one contract probe: docs checker 46 docs / 0 errors; second instance still needed).
**Evidence surface:** source/rendered docs. **Generality evidence:** one executed docs checker; not a
universal rule. **Force:** convention-only.

**Applies when** the user/reader observes the artifact through source Markdown/
text or a rendered documentation page. **Does not apply** to a game/UI or CLI-only artifact with no
documentation surface.

## Required evidence

- The affected source/rendered page and the reader-observable before/after: section content, table/list,
  navigation, link/anchor, search result or cross-reference.
- Execute the relevant render/link/anchor/navigation check or an explicit manual reading; a source diff
  alone is not evidence for a rendered claim.
- For a docs-only task, no screenshot/game/UI check is required unless the task explicitly includes a
  rendered visual design surface; if it does, the visual profile applies in addition.
- A `must` docs gap fails/blocks verification until executed or accepted as a recorded risk; a
  `should` gap may remain recorded.

Do not import gameplay or CLI-only checks into a docs task. Do not treat a missing link as a visual
defect.
