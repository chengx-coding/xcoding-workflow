# Self-Evolution Discipline

This reference is the detailed method for running a **self-evolution line**: a sequence of changes
that improves XC's own portable workflow assets or a project's managed workflow bridge. The phrase
"self-evolution/optimization line" means the same thing; "autonomous" describes the user grant for a
run, not a different kind of line. It is loaded when `xc-workflow-evolution` is used for such a
line. It does not apply to ordinary consumer work orders, and it does not add a runtime command,
state, node type, or configuration surface.

All rules here are **convention-only** unless a rule states that an existing mechanical check
enforces it. There is no new automatic enforcement. Existing runtime gates still execute normally;
the discipline governs when a self-evolution line pauses, what it records, and how a delegated gate
decision is made and reported.

## 1. Meta-Cognitive Checkpoint

A self-evolution line needs a second-order review of the line itself, not only a review of the last
artifact.

### 1.1 Countable units

- One **iteration** is one completed self-evolution change with its own result and version
  disposition.
- One **line** is the consecutive iterations since the last meta-review or refactor.
- Count iterations, not commits, messages, or nodes.

### 1.2 Triggers

Run a meta-review when the first of these occurs:

| Trigger | Rule |
| --- | --- |
| Iteration cap | 3 iterations in the line have completed since the last meta-review or refactor |
| Version boundary | The project's version policy defines a boundary that the line is about to cross |
| Direction evidence | The metric improves while user-visible quality does not, or vice versa |
| Patch evidence | The same class of patch recurs at least twice |
| Architecture evidence | Rules are duplicated or contradictory; rules/nodes/gates are growing without a corresponding judgement; an owner is unclear |
| Regression evidence | A regression, consecutive decline, or a defect that the metric missed |
| Generality evidence | The change works only for one sample/case, or a sample-specific shortcut appears |
| Metric change | The evaluation standard or metric is changed; review the line before continuing under the new metric |
| User report | A user reports a perceptible gap that the current metric does not represent |

Do not add a meta-review to every ordinary work order. A single small maintenance change does not
trigger one unless a signal above applies.

### 1.3 Independence, time-box and evidence

- The reviewer must not have authored the line. Use a separate reviewer or subagent.
- Time-box the review to 45–60 minutes. If the review cannot reach a decision in that window, record
  the unresolved uncertainty and the re-entry condition instead of expanding indefinitely.
- If an independent reviewer cannot be obtained, do not claim independence. Record the limitation;
  for a **material** decision, pause for a user gate or a fresh reviewer instead of self-approving.
- Do not recursively review the review. One meta level is enough.
- Cite the actual evidence: results, defects, metric history, diffs, rule counts/duplication,
  evaluation changes and user reports. Do not substitute narrative for evidence.

### 1.4 Review questions

At minimum:

1. Is the problem still the right problem, and is the metric still a valid proxy for the user value?
2. Is this a local patch or a systemic change? What would the systemic version look like?
3. What is duplicated, contradictory, stale, over-grown, or owned by the wrong file?
4. Are we adding mechanisms where an existing mechanism or a smaller repair would suffice?
5. Did we overfit one sample, case, or metric? What is the general evidence?
6. Should we continue, simplify, refactor, change the metric/process, pause, stop, or defer?
7. What evidence would overturn the current direction, and what remains unknown?

### 1.5 Output, authority and effects

Record one **meta-review artifact** containing:

- line/iteration range and trigger;
- reviewer identity/role and independence status;
- evidence reviewed;
- findings, including patch accumulation and content-placement issues;
- decision: `continue | simplify | refactor | change-metric | pause | stop | defer`;
- affected scope, next action, unresolved uncertainty and re-entry condition.

Effects:

- `continue`: the line may add the next iteration.
- `simplify`, `refactor`, `change-metric`, or `pause`: no new optimization iteration starts until the
  main session records the resolution; a material change still needs the normal user or delegated-gate
  decision.
- `stop`: the line ends; do not start a successor iteration without a new approved direction.
- `defer`: record the reason, evidence, impact and a re-entry trigger; the line may continue only on
  the parts not deferred.

The meta-review has **pause-and-require-decision** authority. It does not have unilateral authority
to make material changes. It cannot override a user decision, the core design, security rules or the
project bridge.

## 2. Content Placement

Use three owners:

| Owner | Content |
| --- | --- |
| `SKILL.md` | Stable intent, public contract, parameters, routing, invariants and scope |
| `references/` | Detailed method, checklists, examples, record formats and policy choices |
| Orchestration node instructions | Stage-specific actions, acceptance, attention focus and current context |

Rules:

- One owner per rule. A node references the Skill/reference; it does not copy the contract.
- Put attention-sensitive, stage-specific guidance in the node that executes that stage. Put durable
  contracts in the Skill. Put detailed method in the reference.
- When moving content, record an **equivalence check**: the meaning is unchanged, the relevant
  validation/tests still pass, and a reviewer has compared the moved text. A move that changes
  behavior is a contract change, not a placement cleanup.
- Do not duplicate a rule across Skill, reference and nodes. Duplication is a drift source.
- Every new rule states its force separately. If no mechanical check exists, write
  **convention-only**; do not imply enforcement by wording.

## 3. Divergence and Convergence

Thinking is a search: explore enough, then converge. The amount is adaptive, not a fixed number of
options.

### 3.1 Classify the work

Use confirmed facts:

- **Uncertainty**: are the problem, constraints and success criteria clear?
- **Impact/risk**: what happens if the decision is wrong?
- **Reversibility**: can it be rolled back losslessly?
- **Coupling**: does it cross contracts, modules, owners or workflow stages?
- **Novelty**: is there a precedent or a credible reference?

A specific task can still be high-impact or hard to reverse. A vague task can be low-impact and
fast to test; do not equate vagueness with required breadth.

### 3.2 Context divergence is mandatory

Even for a specific task, search the project context before executing:

- project bridge and instruction files;
- declared conventions, formatters, CI and test commands;
- prior decisions, deferred notes and historical failures;
- ownership and existing patterns;
- the current implementation and its tests.

Record what was read, the authority tier, and any conflict. A missing/unreadable source is a gap or a
fail-closed condition, not "no convention". Do not let a narrow solution search skip this step.

### 3.3 Solution divergence is adaptive

- For a low-risk, reversible, well-understood change, compare one or two viable options.
- For a novel, coupled or hard-to-reverse change, explore a broader set before converging.
- For self-evolution, always consider: **do nothing, minimal fix, simplify, refactor, change
  metric/process**. Adding a rule or mechanism is not the default answer.
- Include a credible reference only when it is relevant; do not import unrelated features.

### 3.4 Converge and record

Record:

- decision and scope;
- evidence and trade-offs;
- rejected options and why;
- unexplored areas and uncertainty;
- stopping reason and re-entry condition.

Stop when further exploration produces no new judgement or the decision threshold is met. Option
count, analysis length and node count are **not** metrics of quality. Do not manufacture completeness.

## 4. Delegated Gates

A delegated gate is not a skipped gate. It is a user-owned gate whose **decision** is delegated to the
agent by an explicit autonomous grant, with a record and a final report.

### 4.1 Grant

Only an explicit user request for an autonomous multi-round self-evolution run creates a delegation.
The grant must state:

- source (the user message/decision);
- scope (which line/change area);
- iteration/round limit or expiry;
- gate classes it covers;
- stop conditions.

Silence, "continue", a general approval, or an earlier unrelated approval is not a grant. The agent
cannot infer, widen or renew the grant. A new autonomous line needs a new grant.

### 4.2 Gate classes

| Class | Delegable? |
| --- | --- |
| Solution/approach approval; clarification/document gate | Yes, when named in the grant |
| Scope, refactor, simplify or delete decisions within the grant | Yes, when named |
| Evaluation-standard or metric revision | Yes, when named; still requires evidence and review |
| Version disposition | Only when the grant explicitly includes the exact version decision |
| Release, tag, publication or asset upload | No |
| Authorization/scope expansion, security, permissions, secrets, compliance | No |
| Destructive Git/history or historical-artifact deletion | No |
| Core values, explicit user constraints, host restrictions | No |
| Outside the grant, or irreversible without a rollback point | No; stop and report |

### 4.3 Materiality

A decision is **material** when it changes a public contract, core values, security/permissions/
compliance, the evaluation standard, the product version/release, a historical record, or has a broad
or hard-to-reverse blast radius. If uncertain, treat it as material. Material delegated decisions
require an independent review **input** even when the grant is explicit.

### 4.4 Run, never skip

- The existing gate node must execute with a non-empty decision and the normal gate outcome.
- Do not implement a delegated gate by leaving an optional gate unrun, by relying on the `xc-work`
  default `approved`-on-skip value, or by writing an approval-looking document without the gate.
- If the lifecycle contains no gate node for that decision, there is no gate to delegate. An
  existing optional gate must still run when the decision is delegated; "optional" means the
  lifecycle may omit it in another run, not that a present gate may be skipped.
- The main session is the only actor that may exercise the grant. Workers cannot.

### 4.5 Record

Keep one `delegated-gate-decisions` artifact per work order. For each decision record:

- gate id/class and why it normally needs the user;
- authorization source, scope and expiry/limit;
- options considered and evidence;
- decision and materiality assessment;
- risk and reversibility/rollback point;
- independent review for a material decision;
- what the user would have been asked;
- follow-up verification.

The record is written at decision time, not reconstructed after the fact.

### 4.6 Stop rule

If a decision exceeds the grant, lacks a rollback point, or touches a non-delegable boundary, stop and
report. Do not self-authorize a wider grant. A blocked decision is a legitimate outcome; a fabricated
approval is not.

### 4.7 Final report

`result.md` must contain a dedicated **autonomous decisions** section listing:

- what problem was encountered;
- what would have been asked of the user;
- what the agent decided and why;
- evidence, materiality, risk and rollback;
- residual risks and what the user may want to reverse.

The section is required even when the decisions were uncontroversial. It is not buried in a general
summary.

## 5. Force and Limits

| Rule area | Force |
| --- | --- |
| Meta-review cadence, independence, record and decision effects | convention-only |
| Content placement and equivalence check | convention-only |
| Divergence/convergence method and record | convention-only |
| Delegated-grant, gate-class, materiality, record and final-report obligations | convention-only |
| The underlying runtime gate state transition | mechanical (the existing gate, not this reference) |

No runtime check proves that a meta-review happened, that a reviewer was independent, or that a
delegated grant was valid. Those are documentation and review disciplines. Do not describe them as
mechanically enforced.

## 6. Node Usage Pattern

When a self-evolution work order needs this discipline:

1. Add a meta-review task or checkpoint to the existing work order using the normal node/artifact
   mechanism. Put the stage-specific questions and acceptance in that node's instructions.
2. Put the detailed method in this reference; do not copy it into the node or Skill.
3. Record the meta-review artifact and decision; if the decision pauses the line, do not start the
   next optimization node.
4. For a delegated gate, execute the existing gate node, record the decision in the delegated-gate
   artifact, and include the autonomous-decisions section in the result.
5. For an ordinary work order, do none of this unless the user explicitly asks for a self-evolution
   review; ordinary gates keep their normal user ownership.

This pattern reuses the existing runtime, node, artifact and gate contracts. It does not add a new
orchestration template or a new runtime mechanism.
