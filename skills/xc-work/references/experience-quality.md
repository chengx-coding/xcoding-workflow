# Experience-product quality

**Scope:** task-class. **Applies when** the deliverable is a visual/interactive experience product:
a game, sandbox, simulation, visual UI tool, or similar. **Does not apply** to a pure library, CLI,
data pipeline, or source-only documentation task. Record the selection or a not-applicable reason in
analysis; do not force this profile on a non-experience product.

This profile is additional to universal observable-state integrity and the selected output-surface
evidence. It is not a feature checklist.

## 1. First-run discoverability

A player/user must be able to find the primary systems from the first-run UI: visible buttons, a
short tutorial, a task/quest entry, or an equivalent affordance. A keyboard hint in a corner, a
README sentence, or in-game help alone is not full discoverability. Verify with a first-run probe:
start from a fresh state, identify how to open the primary system without prior knowledge, and record
the visible entry point.

If a primary system is reachable only through an undocumented/passive key, record a discoverability
gap; the feature may exist, but it is not full credit.

## 2. Visual composition and review

For a primary visual surface, the result needs a deliberate composition, readable character/world
elements, coherent UI hierarchy, and feedback that makes actions legible. A debug canvas or a plain
prototype is a lower experience tier, not a fail by itself.

Before result, run an **independent visual review** (a reviewer other than the implementer) against
the goal's experience bar. Record before/after states and fix every required finding, then re-check.
A single first frame is not evidence for an interactive experience.

## 3. State-dependent backdrop

When content is removed, cleared, hidden or covered, or a mode/theme/time/viewport changes, the
surface must show a coherent backdrop/empty/fallback for that state. Removed underground/world content
must not reveal an unrelated sky/void unless that is the intended visual state. Verify before/after on
the declared surface; do not accept a code reading or a static default frame.

This is a specific expression of universal observable-state integrity for visual surfaces; it is not
a new mechanism.

## 4. Reference signature and progression

When a credible domain reference exists, identify a small set of **signature capabilities** and the
genre's defining loop. Do not silently classify a defining loop as a non-goal. For a no-user analysis,
either include a minimal must/should version or record a sourced omission and its experience gap; a
silent omission is not a decision.

Avoid feature-count thinking: the signature set is small and decision-changing. A simple version of
the loop (for example a short list-based progression) is acceptable when it consumes inputs, produces
outputs and creates a progression; a decorative menu is not a loop.

## 5. Verification

The verification profile records:

- a fresh first-run discoverability probe with the visible entry point;
- an independent visual review with required findings and re-check;
- state-dependent backdrop before/after;
- a progression/signature journey when applicable;
- the executed evidence and any gap.

A `must` gap follows the universal fail/block-or-recorded-risk rule. A `should` gap may remain recorded
with reason/impact. Visual polish is scored, not a high integrity defect; a broken backdrop/state or
unplayable core is a high defect.

## 6. Force

Convention-only. No new runtime command, state, node type or configuration surface. The profile is a
task-class reference; do not apply it to a pure code/docs task.
