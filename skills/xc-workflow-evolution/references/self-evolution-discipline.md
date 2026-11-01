# Self-Evolution Discipline

Method for a self-evolution/optimization line. The owning Skill carries routing and the canonical
one-owner/force rules; this reference is the checklist, not a second contract.

## 1. Startup and hypothesis

Before the first substantive action, reconstruct the line: prior round notes, architecture
debt/decisions (when the project has them), current version and sample state. State one falsifiable
hypothesis: defect class → lever → expected behavior change → evidence that would refute it. If no
hypothesis can be refuted, do not spend a round on it.

## 2. Divergence and convergence

Diverge on context (bridge, instructions, conventions, prior decisions, tests/CI, ownership, history)
and on solutions (do nothing, minimal fix, simplify, refactor, change metric/process). Converge with:

- the selected option and rejected alternatives;
- owner, scope, evidence surface and version impact;
- uncertainty, rollback and a stop/continue reason.

Option count is not a metric. A line that cannot name what would make it stop is not converged.

## 3. Ownership and placement

Keep stable contract/invariants in the owning `SKILL.md`; detailed method/checklists/record formats in
its references; stage actions in node instructions. One owner per rule. Before moving content, compare
meaning and update links/tests in the same change. Do not add a second reference to avoid deciding
which one owns the rule.

## 4. Evidence and review

- A task-class rule starts `proposed`; `validated-in-class` needs a second independent instance of
  that class; `promoted-universal` needs a different-class probe and a negative/not-applicable probe.
- A sample score is one signal; it cannot prove cross-class generality or architecture quality.
- Independent review must apply the rule to a non-originating class when universal promotion is
  claimed. Wording-only review is not generality evidence.
- A `must` gap fails/blocks or is accepted as a recorded risk; a `should` gap may be recorded. Never
  write a pass for an unexecuted probe.

## 5. Meta-review

Trigger at three completed iterations, a version boundary, or a direction/patch/architecture/
regression/generality/metric/user-report signal. Use a bounded independent review. Record, minimally:

| Field | Content |
| --- | --- |
| What changed | product and process |
| What was learned | about the system, not just the task |
| Keep / demote / retire | rules, profiles, mechanisms |
| Architecture signal | duplicate owner, patch chain, drift, test coupling |
| Decision | continue / promote / refactor / stop |
| Next trigger | date, event or version |

The review cannot make material changes unilaterally and is not recursively reviewed. "Defer to line
end" is not a decision; line end must record one. A line closure always records the table above, even
when no trigger fired; if no independent reviewer is available, record the fallback and limit the
claim to a self-review, never "independent acceptance".

## 6. Architecture health

Treat these as refactor signals, not reasons for another guard/profile:

- the same rule in a Skill, reference, table, verification and docs with different strength;
- an owner detail unreachable to its consumer, or cross-Skill private reads;
- a rule labeled universal but applied on only one path;
- tests that assert prose rather than behavior;
- protocol prose that no test reads and code already contradicts;
- version churn without a durable architecture decision.

Response: inventory the owner/source, choose keep / consolidate / split / remove, and state the target
shape. Deletion and ownership moves are valid outcomes. A refactor that changes public contracts is a
major version and follows normal analysis/review; a pure audit does not bump the version.

## 7. Line closure

End with one of: `continue`, `promote` (durable rule/profile), `refactor` (major iteration), `stop`
(reason). Record evidence, rejected options, residual risks, next trigger and version/sample
disposition. Update the project's architecture debt/decision registers when they exist; do not rely on
the current session.

## 8. Delegated gates

Only an explicit user grant for an autonomous multi-round line can delegate an otherwise user-owned
gate. The grant states its source, scope and iteration/expiry; expanding it needs a new grant. Run the
gate, do not skip it. Record grant, scope, alternatives, materiality, evidence, risk, rollback and
independent review; `result.md` carries an autonomous-decisions section. Material means a contract,
public behavior, architecture, security/permissions/data or irreversible decision. Non-delegable:
expanding the grant, security/permissions/secrets/compliance, destructive history/artifact deletion,
release/tag/publication, core values/explicit user constraints, host restrictions, out-of-grant or
irreversible decisions.

## 9. Force

Convention-only unless an existing mechanical check says otherwise. No new runtime command, state, node
type or configuration surface. This method applies to self-evolution lines; ordinary work orders are
unchanged.
