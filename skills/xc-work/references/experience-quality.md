# Experience-product quality

**Scope:** task-class. **Promotion status:** `proposed`. **Generality evidence:** the overall experience lens is proposed (one open-sample application);
section 3's visual-state backdrop is owned by the visual output-surface contract and is
validated-in-class only for **2D sandbox visual products** where content can be removed/covered or
mode/theme/time/viewport changes. **Applies when** the primary deliverable is a visual/interactive experience
product: a game, sandbox, simulation, or an interactive visual tool whose acceptance is experiential.
**Does not apply** to a pure library, CLI, data pipeline, data dashboard, documentation set, or other
primarily informational deliverable. Record the selection or a not-applicable reason; do not force
this lens on a non-experience product.

This is a review lens, not a feature checklist. It does not add a universal requirement and does not
authorize adding a feature that the request does not support.

## 1. First-run discoverability

For a 2D sandbox visual product, the first-run affordance is a **must** owned by the visual output-surface
contract: a visible button/tutorial/task/menu entry, not a passive key hint or README. Other
experience products use this as a proposed lens. Verify from a fresh state and record the visible
entry point; a discoverability gap is a quality finding, not by itself a high-severity finding.
## 2. Visual composition and review

For a primary visual surface, record the composition, character/world readability, UI hierarchy and
action feedback. A plain implementation is simpler; it is not a correctness failure.

Before result, obtain an **independent visual review** when an independent reviewer is available.
Record the reviewed before/after states and required findings, and re-check fixes. If no independent
reviewer is available, record a self-review with that limitation; do not claim independent review.

## 3. Visual-state backdrop (visual-product must)

This is owned by the visual output-surface contract, not duplicated here. For a visual product where
content can be removed, cleared, hidden or covered, or a mode/theme/time/viewport changes, the
state-dependent backdrop is a **visual-class must**; record before/after and execute the
transition. The visual class is `validated-in-class` by two independent visual products; the overall
experience lens remains `proposed`. Do not apply the must to a static document set, CLI output, data
pipeline or informational dashboard. See `references/output-surface-evidence.md`.
## 4. Reference signature and progression

When a credible reference exists, identify a small set of signature capabilities and the genre's
defining loop. Do not silently classify a defining loop as a non-goal. A reference-observed feature
that the request is silent about is a **proposed should**, not an automatic must: record the evidence,
the user value and the experience gap. A user or the request may make it binding; without a user,
record the proposed should and do not add it as a hidden requirement. If a no-user analysis chooses a
smaller scope, record the reason and the lost experience value.

Avoid feature-count thinking. A simple, task-appropriate progression is valid; it must be discoverable
and produce a real state change, not a decorative menu.

## 5. Verification

When the product is an experience product and the profile is used, record:

- a fresh first-run discoverability probe and the visible entry point;
- a visual review (independent when available) with findings and re-check;
- a progression/signature journey when one is included;
- the executed evidence and any gap/limit.

A quality gap is recorded; a broken core or unplayable state remains a high-severity finding under
the universal rules. Do not convert an experience gap into a high-severity finding, and do not use
this profile to require a specific feature set.

## 6. Force

Convention-only. No new runtime command, state, node type or configuration surface. The overall experience lens is
proposed; its visual-state backdrop is validated-in-class for the visual class, not universal. A second
independent experience-product instance is still needed for the overall lens.
