# Scope Policy

Implementation magnitude is a dynamic constraint, not a fixed minimum. The goal is the **minimum
sufficient change**: the smallest change that fully satisfies the legitimate need and the
task-appropriate quality bar, while preserving existing structure and consistency where that does
not conflict with the need. "Minimum" never means "smallest diff at any cost"; consistency is a
preference, not the objective.

## Task presets

| Task type | Minimality strength | Default | When to release / override | Task-appropriate quality bar |
| --- | --- | --- | --- | --- |
| `create` | none | Build the best artifact possible within the stated constraints and quality contract | Not applicable; there is no minimality presumption to release | User-facing quality, completeness and richness appropriate to the request |
| `change` | medium | Prefer the smallest coherent change that fully satisfies the need and quality bar, preserving consistency where possible | If the minimal change cannot meet the need or quality bar, lower the minimality preference and implement the change the need requires | Need satisfaction, consistency with the existing design, no regression |
| `repair` | strong | Assume a local fix in mature, coupled code; keep the change and behavior surface as small as the fix allows | Promote to `change` when the root cause or the correct fix requires changing a shared mechanism, a design decision or a requirement, or the change approaches feature scale | Correct fix, no regression, justified scope; not feature growth |
| `maintenance` | by nature | Apply the `change` or `repair` rules according to what the maintenance actually is | Same promotion rule as the chosen rule | The outcome the maintenance must preserve or restore |

`investigation` and `review` do not modify the reviewed product and have no implementation-scope
preset; they still decide how much evidence and depth the question needs.

## Dynamic factors

| Factor | Direction |
| --- | --- |
| The existing code is more mature and more coupled to the surrounding system | Stronger preference for the minimum sufficient change |
| The user-requested delta is smaller | Stronger preference for the minimum sufficient change |
| A minimal change cannot fully meet the need or quality bar | Release minimality and implement the change the need requires |
| Risk or uncertainty is higher | Add assessment, clarification or a gate; justify the scope; do not use "minimal" to avoid a necessary correctness change |
| Rollback is harder, or a public contract, user data or security is affected | Add a gate and verification; minimality is not a substitute for correctness |
| The task is `create` | No minimality presumption |

These are directions of judgement, not a numeric score. The policy is a decision norm with a default
presumption, contextual adjustments and explicit release triggers.

## Decision procedure

1. Classify the task as `create`, `change`, `repair` or `maintenance` (using the change/repair rules
   for maintenance).
2. Collect the evidence: code maturity and coupling, the size and intent of the requested delta,
   constraints, risk, reversibility and the task-appropriate quality bar.
3. State the viable options: minimal coherent, minimum sufficient, a larger design change, or a
   promotion from repair to change.
4. Judge each option against the need, the quality bar, correctness and risk; recommend one.
5. If the trade-off is materially ambiguous, or a repair would be promoted to change, ask the user
   through the existing clarification or approval gate with the concrete options. Do not decide a
   material human-owned trade-off silently.
6. Record the decision in the analysis (assessment) and solution (decision).
7. Implement only the accepted scope. If the accepted scope proves insufficient, stop and return to
   the caller; do not silently expand or shrink it.
8. Review scope fit: under-scope (the need or quality bar is not met), over-scope (unnecessary churn
   or changes beyond the approved scope) and scope drift (the implementation differs from the
   recorded decision).

## Records

- **Analysis scope assessment (change and repair):** task type; code maturity/coupling; the user's
  delta; whether a minimal coherent change fully satisfies the need and quality bar; the viable
  larger options; the recommendation; uncertainty; whether clarification or a gate is required.
- **Solution scope decision (change and repair; create):** for change and repair, the solution records
  the task type, minimality strength, chosen scope, release or promotion triggers, the user
  confirmation reference when one was required, and the boundary the implementation must not cross.
  For create, the goal's quality contract and constraints are the scope record when no solution is
  used; a solution records the same fields when one is selected.
- **Implementation:** the accepted scope is an input. The worker implements it, records changed
  paths and validation, and does not add unapproved scope. If the scope is insufficient, the worker
  stops and reports back rather than inventing a new scope.
- **Review:** scope fit as described above, in addition to correctness and quality findings.

## Quality bar by task

- `create`: a user-facing quality contract in the goal's acceptance conditions, including a concrete
  comparison target when one exists. The bar is about the product, not the number of stages.
- `change`: the legitimate need is met, the existing design stays coherent, and no regression is
  introduced.
- `repair`: the reported problem is correctly fixed, behavior outside the fix is preserved, and the
  scope is justified by the root cause.
- `investigation` / `review`: evidence quality and traceable findings; no product change is expected.

Do not apply a feature-richness quality bar to a repair or a small change; that creates scope creep
in the other direction. Do not apply a minimality presumption to a create; that caps the product.
