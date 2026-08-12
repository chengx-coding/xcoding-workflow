# Template Design Method

Translate a prose workflow into a small set of deterministic control structures. The template defines scheduling and hands domain work to self-contained leaf tasks.

## 1. Establish Boundaries

Identify inputs, output artifacts, required user decisions, failure policy, and the short cross-node values that belong on the blackboard. Long reports must be artifacts, not XML text or blackboard values.

## 2. Identify Control Structure

Use:

- `composite mode=sequence` for ordered stages.
- `composite mode=parallel` for independent work without shared write risks.
- `composite mode=switch` with `switch.key`, `role=case`, and `case.value` for deterministic mode routing.
- `gate executor=main` for concentrated user confirmation.
- `loop` for bounded review/rework convergence.

Keep business labels in `role`: for example `role=research`, `role=review`, or `role=rework`. Do not add domain-specific runtime types.

## 3. Make Leaves Self-Contained

Every `executor=subagent` leaf requires:

- `instructions`
- `deliverables`
- `acceptance`

The leaf should have enough context to be delegated without exposing the entire workflow tree.

## 4. Define References and Loops

Use a stable kebab-case `template_id` for each template node. Dependencies are template-local:

```text
depends_on_template="local:prepare"
```

For loops, provide:

```text
loop.max_iterations
loop.break_when
loop.continue_when
loop.on_limit
```

The runtime checks these only when an iteration's children have all succeeded or been skipped. It does not support internal `break-loop` or `continue-loop` signals.

Use `when.policy=latched` for a loop child whose branch choice must remain
stable for the current iteration. The next iteration clears descendant
latches. A break, natural completion, or limit decision terminalizes the loop
and closes any descendant that becomes unreachable.

## 5. Validate and Smoke Test

Run `validate-spec`, then `build`, then `validate-template`. Finally instantiate the generated template with `xc-orchestration-runtime init` and confirm that `next` returns the intended first node or parallel batch.
