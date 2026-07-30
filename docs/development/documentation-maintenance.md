# Documentation Maintenance

**Language:** **English** | [Simplified Chinese (简体中文)](../zh-CN/development/documentation-maintenance.md)

## Language Contract

English README and documentation pages are canonical. Every English page under `docs/` has an exact-path simplified Chinese mirror under `docs/zh-CN/`. The mirror must preserve the topic, factual boundary, navigation, and material information; line-by-line translation is not required.

Every page uses a prominent selector that lists all supported languages:

```markdown
**Language:** **English** | [Simplified Chinese (简体中文)](<mirror-path>)
```

On the Chinese mirror, make Simplified Chinese the current-language text and
link English instead. Do not leave a reader with only an unfamiliar native
language name.

Add, move, rename, or delete both language versions in one change. Update all affected navigation, links, anchors, and the documentation checker's approved topology at the same time. Never create a temporary empty mirror to satisfy structural checks.

## Evidence Policy

Describe current behavior only when it is supported by tracked canonical contracts, source, configuration, and tests. Recheck commands, defaults, paths, state semantics, failure behavior, and ownership boundaries against those sources during each edit. Historical or local notes are not evidence for a public claim.

Unimplemented ideas may appear only in the explicitly non-normative future section of the orchestration design page. They must not promise delivery, provide a schedule or roadmap commitment, or guarantee compatibility.

## Public Links

Public pages may link only to exact-case targets that exist in a clean checkout, are tracked or staged for the same release, and are not ignored or excluded. Do not link local maintenance assets, workshop state, private instructions, generated local adapters, or any other checkout-only context. Relative links and anchors must resolve in both languages.

## Review Evidence

Mechanical checks do not establish bilingual equivalence. An independent semantic review must record:

- the reviewer role and actual reviewer identity;
- the reviewed revision or a reproducible complete-diff identity;
- an accepted or rejected outcome, factual conclusion, and finding references for every documentation pair and the root README pair;
- cross-cutting checks for Skill coverage, current-versus-future wording, installation claims, compatibility gaps, and hidden-path leakage;
- remediation ownership and a new review result for every rejected or stale outcome;
- a final accepted or rejected conclusion with no unresolved, rejected, or stale pair when acceptance is claimed.

Any content change after review makes the affected outcome stale and requires re-review.

## Verification

During parallel page authoring, run focused checks for owned pairs, language switches, local links and anchors, exact case, relevant Skill names, and factual consistency. Do not force the full checker to pass by creating sibling-owned placeholders.

After all pages are integrated:

1. Run the documentation checker unit tests.
2. Run the checker against the complete repository.
3. Before release or commit, run its strict tracked mode.
4. Complete the independent bilingual semantic review.
5. Run the repository's full test suite, applicable generated-output checks, and `git diff --check`.

Record commands, outcomes, skipped checks, and residual risk in the owning work-order artifacts. A failed checker, stale review, or unresolved semantic finding blocks acceptance.
