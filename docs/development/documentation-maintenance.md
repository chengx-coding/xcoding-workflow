# Documentation Maintenance

**Language:** **English** | [简体中文](../zh-CN/development/documentation-maintenance.md)

## Language Contract

English README and documentation pages are canonical. Every English page under `docs/` has an exact-path simplified Chinese mirror under `docs/zh-CN/`. The mirror must preserve the topic, factual boundary, navigation, and material information; line-by-line translation is not required.

Every page uses a prominent selector that lists all supported languages by
their canonical native names only:

```markdown
**Language:** **English** | [简体中文](<mirror-path>)
```

On the Chinese mirror, make 简体中文 the current-language text and link English
instead. Do not add translated aliases or parenthetical explanations to
language names.

Add, move, rename, or delete both language versions in one change. Update all affected navigation, links, anchors, and the documentation checker's approved topology at the same time. Never create a temporary empty mirror to satisfy structural checks.

## Evidence Policy

Describe current behavior only when it is supported by tracked canonical contracts, source, configuration, and tests. Recheck commands, defaults, paths, state semantics, failure behavior, and ownership boundaries against those sources during each edit. Historical or local notes are not evidence for a public claim.

Unimplemented ideas may appear only in the explicitly non-normative future section of the orchestration design page. They must not promise delivery, provide a schedule or roadmap commitment, or guarantee compatibility.

## Public Links

Public pages may link only to exact-case targets that exist in a clean checkout, are tracked or staged for the same release, and are not ignored or excluded. Do not link local maintenance assets, workshop state, generated local adapters, or any other checkout-only context. Relative links and anchors must resolve in both languages.

## Private Workshop Boundaries

Public pages are tracked and open-source-visible. They must not cite a concrete artifact inside a project's private workshop: not the core design, design documents, work orders, feature baselines, notes, runtime state, or knowledge guidance under `.xcoding/`, in any form -- a Markdown link, an inline code span, a bare path in prose, or a directory reference. Fixed contract names and structural paths remain allowed, because the public workflow contract must be able to name its own fixed paths and structures: the workshop directory `.xcoding/`, the bridges `.xcoding/WORKFLOW.md` and `.xcoding/KNOWLEDGE.md`, the engine's configuration filenames `.xcoding/xc-orchestration-runtime.json` and `.xcoding/xc-orchestration-runtime.toml`, the fixed structural orchestration-tree path `runtime/orchestration.xml`, and placeholder layout paths such as `.xcoding/work-orders/<work-order-id>/` and `.xcoding/features/<feature-id>/`. A bare `.xcoding/` prefix does not make what follows allowed: a concrete identifier beneath a fixed layout directory is a citation, not a layout path.

This rule governs the tracked `docs/` tree in both languages, the root `README.md` / `README.zh-CN.md` pair, and `skills/**`. The repository's governance test suite carries a mechanical guard for the citation boundary. That guard cannot decide the stricter reading below, which stays a review obligation rather than a machine-decidable rule.

Beyond the citation ban, public pages are held to a stricter reading. They are explanatory material, and they are what a reader has. They may restate and summarize the core design, and they must remain intelligible without any non-public source: a public page must not disclose development-process internals, must not state or imply that it was produced from or synchronized with a source outside the public documentation, and must not point a reader at one. The design is presented publicly, in the page's own voice.

The stricter reading applies to every tracked public page and to both language versions of each page, and it covers a page's framing and omissions as much as its explicit statements.

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
