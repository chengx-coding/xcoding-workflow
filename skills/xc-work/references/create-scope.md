# Create Scope Fidelity and Capability Matrix

Load this reference for a `create` work order, before writing the goal and again when selecting the
solution. It keeps the product faithful to the requested experience without turning feature count
into a metric.

## Principle

A create task is judged by whether the user can do what they asked for, at the requested quality bar.
The goal must not silently narrow that experience, and the solution must not silently drop a
capability it declared. Breadth is a consequence of the requested experience, not a score: a small
task may need two capabilities, a large one may need twenty. Never add capabilities merely to make a
matrix look complete.

## Goal fidelity

The goal must contain:

- **Requested outcome** — the user's requested result, in the user's terms.
- **Intended capability scope** — what the user must be able to do, observe, or rely on.
- **Quality contract** — the user-facing quality bar and comparison target, when one exists.
- **Exclusions and constraints** — anything the goal excludes or adds, with its source.

For every material exclusion or additional constraint, record one source:

- `user` — explicit in the request or a confirmed user decision;
- `project` — required by the project bridge, platform, or applicable policy;
- `goal-authored` — the goal writer's own proposal. A material `goal-authored` exclusion requires
  user confirmation before it becomes binding. When no user is available, do not add a material
  exclusion; keep the requested scope and let analysis/solution prioritize must/should work instead.

When no user is available and there is no sourced material exclusion, state "no material exclusions"
explicitly rather than inventing a negative list. If a capability cannot be resolved without a user
decision, carry it as an open decision; an unresolved required capability blocks solution approval
and is not silently dropped.

A comparison target is a floor, not a ceiling. "At least as good as a reference" does not authorize
removing parts of the requested experience that the reference lacks.

## Capability map

Analysis produces a capability map. Each row is a user-observable capability, not an implementation
module. Keep it as short as the task allows.

| Field | Meaning |
| --- | --- |
| `capability` | What the user can do or rely on |
| `source` | Request, project constraint, domain reference, or goal-authored proposal |
| `priority` | `must`, `should`, or `non-goal` |
| `user_value` | Why it belongs to the requested experience; omit rows with no honest answer |
| `acceptance` | Observable condition that proves it works |
| `verification` | Test, check, inspection, or review evidence |

Priorities:

- **must** — without it the request or quality contract is not met. The approved solution must cover
  every must capability.
- **should** — materially improves the requested experience but can be deferred under a stated
  constraint. Record the reason and impact.
- **non-goal** — deliberately out of scope, with a source. A non-goal is not a silent omission.

The map is not a checklist to maximize. It exists to expose omissions and unilateral narrowing before
they become implementation.

## Reference-informed signature experience

When a credible reference exists — a product, experience, or genre exemplar in the task's domain —
use it to challenge the goal's ambition, not to copy it. The reference is evidence about what makes
the experience legible; it is not a feature checklist and not a breadth score.

A **signature capability** is one without which the result would feel like a subset of the domain
rather than a complete experience of the requested kind. Signature capabilities are a small,
argued set, not every capability the reference has.

For each candidate:

| Field | Meaning |
| --- | --- |
| `reference` | The product/experience and why it is relevant |
| `signature capability` | The user-observable capability that makes the genre/experience legible |
| `evidence` | What in the reference demonstrates it |
| `current goal` | Covered, partial, or absent in the goal's capability scope |
| `decision` | `must`, `should`, or `non-goal`, with user value and source |

Rules:

- add a signature capability only when its user value is honest; do not import the reference's
  unrelated, enterprise, or vanity features;
- a signature must or should capability joins the capability map and, when accepted, the solution
  matrix;
- a signature non-goal needs a source, just like any other non-goal;
- a reference does not authorize removing a requested capability; it can only raise or clarify
  ambition;
- if no credible reference exists, record "no reference applies" and continue; do not invent one;
- if a credible reference exists but the task is small, do not skip the challenge; use the smallest
  decision-changing signature set and record why the set is reduced;
- do not use the reference to set a minimum feature count, a coverage percentage, or a score.

Record why the reference is credible and where the evidence comes from. If no verifiable evidence is
available, mark the reference as proposed and do not bind its signatures; never invent a plausible
product.

A signature may **sharpen** a capability the request already names (for example, adding a filterable
lens to a requested favorites feature). In that case record the signature as a depth/quality
requirement on the existing capability, not as a duplicate row. The analysis capability/signature
map is the canonical record; the goal and solution reference its decisions rather than restating a
second copy.

A reference-observed feature that the request is silent about is not automatically a non-goal.
Classify it as a proposed should/non-goal with its reference evidence and obtain user confirmation
before it becomes binding; do not infer an exclusion from the request's silence.

Keep the signature set small: a row belongs only if it changes a decision or acceptance. There is no
row cap, but there is also no padding; if a row does not change a decision, drop it.

The goal's quality contract, when a reference exists, includes the signature-experience challenge:
the result must at least be recognizably a complete experience of the requested kind, not merely a
literal checklist of the prompt.

## Analysis comparison

Analysis must compare the goal with the original request:

- list requested outcomes and the goal's corresponding scope;
- flag any material capability missing from the goal, or any exclusion/constraint the goal added;
- classify each flag as resolved (has a source), needs user decision, or goal-authored narrowing;
- carry the accepted capability map into the solution.

A goal-authored narrowing is not accepted merely because the goal and solution agree with each other.
It needs a source, or it must be removed.

## Solution matrix

The solution records the accepted capability matrix and maps it to the implementation:

| Capability | Priority | Implementation unit | Verification |
| --- | --- | --- | --- |
| ... | must/should | ... | ... |

Rules:

- every must capability has an implementation unit and verification evidence;
- a should capability is either covered or explicitly deferred with reason and impact;
- a non-goal has a source;
- no capability is dropped between analysis and solution without a recorded decision;
- if implementation cannot cover an accepted must capability, block and return for a solution
  revision instead of silently shrinking the result.

## Verification and review

Verification maps evidence to each must/should capability. A passing test suite does not prove an
unverified capability; record the gap.

Review checks scope fidelity against the **original request plus the accepted capability matrix**:

- **under-scope** — a requested or accepted must capability is missing or materially weaker; a
  signature should capability is also under-scope unless the accepted matrix records its deferral
  with reason and impact;
- **over-scope** — work beyond the accepted matrix or unnecessary churn;
- **scope drift** — the implementation differs from the accepted matrix or the goal's stated scope;
- **unsourced narrowing** — an exclusion or constraint with no user/project source.

A review finding that a capability is missing is not excused by "the goal did not include it" when
the original request did, or when the goal added the exclusion itself.

## Proportionality

- Do not require a reference product; if none is credible, record that. A small task with a credible
  reference uses a reduced signature set with a recorded reason, not a blanket escape.
- For a small task, the capability map can be a few lines in the goal/analysis.
- For a large task, prioritize must work first; should work may be deferred; non-goals stay explicit.
- Do not turn the matrix into a score, a coverage percentage, or a reason to add unrelated features.
- Do not copy this reference's wording into the product; it is method guidance only.
