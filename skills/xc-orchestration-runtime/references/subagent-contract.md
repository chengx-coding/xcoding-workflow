# Subagent Contract

A subagent is a single-node worker, not an orchestrator.

## Input

The main session provides:

- `tree_ref`
- One node JSON returned by `next`
- Domain Skill references and artifact paths named by the node
- Required user decisions or blackboard values

## Rules

1. Do not directly read or edit orchestration XML.
2. Execute only the assigned node.
3. Do not change global control flow unless the node explicitly authorizes `add-node` or `embed-subtree`.
4. Write important outputs to the declared artifact path or target system; never leave them only in chat.
5. On completion, call the runtime public command with a concise summary, validation outcome, and artifact paths.
6. Artifact paths intended for an automatic checkpoint commit must be inside the context Git repository.

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

## Fail or Block

```powershell
python "$SKILL_DIR/scripts/orchestration.py" fail `
  --tree <tree_ref> `
  --node <node_id> `
  --reason "<attempted_action_and_failure>"
```

Use `block` rather than `fail` when progress requires user input, external access, or another recoverable prerequisite.
