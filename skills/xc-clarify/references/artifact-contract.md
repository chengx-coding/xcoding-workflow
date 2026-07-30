# Artifact Contract

## Session Artifact

Each embedded instance uses one session artifact:

```text
<workbench_path>/artifacts/<open-session-node-id>/decision-session.md
```

It is a validated `node-artifact` document owned by `open-session-record`. The opening worker creates it from the shared `xc-document` node-artifact template. Later fixed workers and main-session Gates append only their session-specific content.

The artifact frontmatter remains stable:

- `schema_version: 1`
- `document_kind: node-artifact`
- The active `work_order_id`
- The `open-session-record` runtime node ID
- Feature IDs from the enclosing work order
- The opaque runtime tree reference

## Required Content

Use these body sections in addition to the standard node-artifact headings:

```text
## Scope
Mode, subject, input boundaries, and decision budget.

## Evidence
Confirmed facts, sources, and evidence gaps.

## Findings
Decision map and ordered Gate entries. Each entry records the decision ID,
dependencies, evidence, recommendation, alternatives, user response,
disposition, and follow-up.

## Conclusion
Resolved decisions, bounded experiments, accepted risks, residual risks,
and handoff readiness.
```

Gate entries must preserve enough context to explain why the next Gate was created. Do not duplicate raw command transcripts or store blackboard snapshots in the artifact.

## Blackboard Boundary

Use short values only:

```text
clarification.status
clarification.question_count
clarification.limit
clarification.pending_material
clarification.outcome
clarification.next_decision_id
clarification.session_artifact
```

The blackboard must not contain question text, user answers, decision rationale, or the session summary.

## Caller Handoff

After `synthesize-session`, the caller reads the session artifact and writes only the accepted facts, decisions, deferred experiments, and residual risks into its managed `analysis.md`. The caller's solution document remains the authority for the selected implementation strategy.
