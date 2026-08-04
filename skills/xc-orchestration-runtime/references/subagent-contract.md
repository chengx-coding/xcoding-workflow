# Subagent Contract

A subagent is a single-node worker, not an orchestrator.

## Input

The main session provides:

- `tree_ref`
- One node JSON returned by `next`, or its explicitly declared
  `control-packet` projection
- The `revision` returned with that node batch when the caller requires an optimistic write precondition
- Domain Skill references and artifact paths named by the node
- Required user decisions or blackboard values, including `work_order.document_language` when the node writes a user-facing artifact

## Rules

1. Do not directly read or edit orchestration XML.
2. Execute only the assigned node.
3. Do not change global control flow unless the node explicitly authorizes `add-node` or `embed-subtree`.
4. Write important outputs to the declared artifact path or target system; never leave them only in chat.
5. On completion, call the runtime public command with a concise summary, validation outcome, and artifact paths.
6. Artifact paths intended for an automatic checkpoint commit must be inside the workshop Git repository.
7. Read `metadata.artifact.audience` and `metadata.artifact.content_language` from the supplied node. Default to `internal` and `en`; resolve `work_order.document_language` only for an explicitly declared user-facing artifact.
8. Complete, fail, or block only the supplied node after it has been started. Report `state_conflict` or `tree_sealed` to the main session instead of retrying an ambiguous mutation.
9. When completion metadata requires a check, run the declared validator,
   require its successful process exit and top-level success, extract only its
   normalized receipt, and pass that receipt through `--check-result-json`.
   Never pass a validator's legacy outer response.

## Worker Prompt Skeleton

```text
You are executing one orchestration node.

Tree reference: <tree_ref>
Node JSON:
<node_json>

Rules:
- Do not read or edit orchestration XML directly.
- Execute only this node.
- Use supplied blackboard values, references, and artifacts as inputs.
- Produce the requested deliverables.
- On success, call complete with a summary, validation outcome, and artifact paths.
- On failure, call fail or block with a specific reason and required recovery condition.
```

## Complete

```powershell
python "$SKILL_DIR/scripts/orchestration.py" complete `
  --tree <tree_ref> `
  --node <node_id> `
  --summary "<summary>" `
  --validation "<validation_outcome>" `
  --artifact <artifact_path>
```

Write short cross-node variables with `--set review.open_issues=false`.
For an opt-in structured gate, add `--gate-outcome <declared-value>` and the
required `--decision <text>`. For an opt-in completion check, add one
`--check-result-json '<normalized-receipt>'` per declared check. These receipts
are untrusted self-reports rather than proof that the validator ran.

## Fail or Block

```powershell
python "$SKILL_DIR/scripts/orchestration.py" fail `
  --tree <tree_ref> `
  --node <node_id> `
  --reason "<attempted_action_and_failure>" `
  --artifact <failure_evidence_path> `
  --artifact <additional_evidence_path>

python "$SKILL_DIR/scripts/orchestration.py" block `
  --tree <tree_ref> `
  --node <node_id> `
  --reason "<external_prerequisite>" `
  --artifact <blocker_evidence_path>
```

`--artifact` is optional and repeatable for `fail` and `block`. With
`auto_commit=true`, the terminal transition and all declarations enter one
path-scoped checkpoint. A failed checkpoint restores the prior tree and
returns `persisted_uncommitted`. With `auto_commit=false`, checkpoint path
validation remains disabled and the terminal declarations persist without a
workshop commit.

Use `block` rather than `fail` when progress requires user input, external access, or another recoverable prerequisite.

After a worker reports `fail`, it does not reset or rerun itself. The main
session may repeat the same approved leaf contract with
`retry-failed --reason <reason> [--expected-revision <revision>]`. Runtime
archives the prior failure evidence as an attempt before returning the leaf to
scheduling. Replacement work, revised acceptance, or a different solution
requires the owning lifecycle's recovery nodes or user gate instead.
