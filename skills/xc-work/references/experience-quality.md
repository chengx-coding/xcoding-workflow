# Experience-product quality

**Scope:** task-class. **Promotion status:** `proposed`. **Generality evidence:** the overall experience lens is proposed (one open-sample application);
section 3's visual-state backdrop is a separate, narrowly scoped validated-in-class rule for 2D
sandbox visual products. **Applies when** the primary deliverable is a visual/interactive experience
product: a game, sandbox, simulation, or an interactive visual tool whose acceptance is experiential.
**Does not apply** to a pure library, CLI, data pipeline, data dashboard, documentation set, or other
primarily informational deliverable. Record the selection or a not-applicable reason; do not force
this lens on a non-experience product.

This is a review lens, not a feature checklist. It does not add a universal requirement and does not
authorize adding a feature that the request does not support.

## 1. First-run discoverability

A user should be able to find the primary systems from the first-run UI: a visible affordance,
tutorial, task entry, menu, or equivalent. Indirect documentation or a key-only path is weaker
evidence; record how a fresh user finds the system and the visible entry point. A discoverability gap
is a quality finding, not by itself a high-severity finding.

## 2. Visual composition and review

For a primary visual surface, record the composition, character/world readability, UI hierarchy and
action feedback. A plain implementation is simpler; it is not a correctness failure.

Before result, obtain an **independent visual review** when an independent reviewer is available.
Record the reviewed before/after states and required findings, and re-check fixes. If no independent
reviewer is available, record a self-review with that limitation; do not claim independent review.

## 3. Visual-state backdrop (task-class must)

**Scope:** visually rendered products where content can be removed, cleared, hidden or covered, or a
mode/theme/time/viewport changes. **Does not apply** to a static document set, CLI output, data
pipeline, or a data dashboard whose acceptance is informational rather than experiential. **Promotion
status:** `validated-in-class` for 2D sandbox visual products only (two independent instances); a
broader visual-product claim is not made.

This is a **must** for that class: the state must show a coherent backdrop/empty/fallback, not an
unrelated default background or layer. Record before/after on the declared surface and execute the
state transition; a code reading or a single default frame is not evidence. A missing backdrop is a
must gap: fail/block verification or record a user-accepted risk. This is an application of universal
observable-state integrity, not a new mechanism.
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
- state-dependent backdrop before/after;
- a progression/signature journey when one is included;
- the executed evidence and any gap/limit.

A quality gap is recorded; a broken core or unplayable state remains a high-severity finding under
the universal rules. Do not convert an experience gap into a high-severity finding, and do not use
this profile to require a specific feature set.

## 6. Force

Convention-only. No new runtime command, state, node type or configuration surface. The profile is
proposed; a second independent experience-product instance is needed before it is treated as a
validated class contract.
