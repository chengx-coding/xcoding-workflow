# Decision Protocol

## Decision Classification

Classify each uncertainty before scheduling a Gate:

- `evidence-resolved`: code, tests, configuration, baselines, or supplied artifacts answer it. Record the evidence and do not ask the user.
- `human-decision`: a product, policy, scope, compatibility, irreversibility, or risk-acceptance choice needs user authority.
- `bounded-experiment`: implementation evidence can resolve it later if the hypothesis, owner, trigger, and acceptance condition are explicit.
- `accepted-assumption`: a non-material uncertainty is explicitly accepted with a recorded rationale.

Prioritize human decisions by user impact, security, compatibility, data loss, irreversibility, and blocking dependencies. Resolve upstream decisions before their dependent consequences.

## Session Bootstrap

After `map-decisions` completes, the main session executes `seed-questioning`. It reads the session artifact's decision map and uses `xc-orchestration-runtime add-node` under `question-group` to create one of:

- The first material decision Gate.
- A no-material-decision confirmation Gate.

The seed task must add that leaf before it completes. An empty dynamic group is not executable and does not close automatically.

## Gate Contract

Every dynamically added decision Gate:

- Uses `type=gate` and `executor=main`.
- Has one focused decision ID in its title and instructions.
- Includes source evidence, a recommendation, rationale, cost or risk, and at least one viable alternative.
- Does not contain more than one question.
- Declares that the user may choose another option, accept a risk, or choose a bounded experiment.

While the Gate is running, the main session appends the complete response to the session artifact. It then determines the next decision from the dependency map and adds the successor Gate before completing the current Gate. The successor depends on the current Gate so the question sequence remains explicit and resumable.

Do not ask a user to repeat information already present in supplied evidence. When an answer conflicts with earlier decisions, surface the conflict in the next Gate and require an explicit resolution.

## Budget Gates

The initial decision budget is `clarification.limit`, normally `12`. Before adding a decision whose ordinal exceeds the current budget, add a budget Gate instead.

The budget Gate presents these choices:

- Close: confirm that the recorded decisions are sufficient for solution selection.
- Defer: convert remaining uncertainty to accepted risk or a bounded experiment.
- Continue: increase `clarification.limit` by `12`, then add the next decision Gate.

No branch silently continues past a budget boundary. No branch treats a budget boundary as automatic closure.

## Closure

The main session adds a final confirmation Gate when:

- No material human decision remains unresolved.
- Every deferred item has an explicit disposition.
- The session artifact contains enough information for the caller to write an analysis and select a solution without hidden assumptions.

After that Gate succeeds, the dynamic group closes and `synthesize-session` appends a concise handoff summary. If the user declines to close, add the next Gate or a budget Gate according to the recorded disposition.
